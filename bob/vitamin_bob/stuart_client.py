"""Everything Bob asks of Stuart (contract 7.4, 7.5), through durable outboxes.

Bob writes an SMS or sync record to its own outbox first, then a background worker delivers it.
If Stuart is briefly down, nothing is lost: the worker retries, and both endpoints are idempotent
by id, so a retry can never double-send.
"""

import threading
import time

import httpx

from . import config, contract, db

HEADERS = {contract.HEADER: contract.VERSION}
_status_cache = {"reachable": False, "status": None, "at": None, "error": None}
_status_lock = threading.Lock()


def queue_sms(to: str, text: str, priority: str, purpose: str) -> str:
    """Bob never sends an SMS the patient must reply to; this is for clinicians and district staff."""
    message_id = db.new_id()
    contract.SmsRequest(message_id=message_id, to=to, text=text, priority=priority)  # validate now, not later
    db.ex("INSERT INTO sms_outbox VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?)",
          message_id, to, text, priority, purpose, db.iso(), db.iso())
    return message_id


def queue_sync(kind: str, payload: dict) -> str:
    problems = contract.sync_payload_problems(payload)
    if problems:
        raise ValueError(f"sync payload rejected before sending: {problems}")
    record_id = db.new_id()
    db.ex("INSERT INTO sync_outbox VALUES (?, ?, ?, 'pending', 0, ?, ?, NULL)",
          record_id, kind, contract.compact(payload), db.iso(), db.iso())
    return record_id


def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{config.STUART_URL}{path}", json=body, headers=HEADERS, timeout=3)
    r.raise_for_status()
    return r.json()


def flush_sms() -> None:
    order = "CASE priority WHEN 'urgent' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END"
    for m in db.q(f"SELECT * FROM sms_outbox WHERE status='pending' ORDER BY {order}, created_at LIMIT 20"):
        try:
            ok = _post("/v1/sms", {"message_id": m["message_id"], "to": m["to_phone"], "text": m["text"],
                                   "priority": m["priority"]}).get("queued")
            status = "queued" if ok else "pending"
        except Exception:  # noqa: BLE001 - Stuart down: retry on the next tick
            status = "pending"
        db.ex("UPDATE sms_outbox SET status=CASE WHEN status='pending' THEN ? ELSE status END, attempts=attempts+1, updated_at=? WHERE message_id=?",
              status, db.iso(), m["message_id"])
        if status == "pending":
            return


def flush_sync() -> None:
    rows = db.q("SELECT * FROM sync_outbox WHERE status='pending' ORDER BY created_at LIMIT 10")
    if not rows:
        return
    import json  # noqa: PLC0415
    records = [{"record_id": r["record_id"], "kind": r["kind"], "payload": json.loads(r["payload"])} for r in rows]
    try:
        ok = _post("/v1/sync", {"records": records}).get("queued")
    except Exception:  # noqa: BLE001
        ok = False
    for r in rows:
        db.ex("UPDATE sync_outbox SET status=CASE WHEN status='pending' THEN ? ELSE status END, attempts=attempts+1, updated_at=? WHERE record_id=?",
              "queued" if ok else "pending", db.iso(), r["record_id"])


def refresh_status() -> None:
    try:
        r = httpx.get(f"{config.STUART_URL}/v1/status", headers=HEADERS, timeout=1)
        r.raise_for_status()
        new = {"reachable": True, "status": r.json(), "at": db.iso(), "error": None}
    except Exception as e:  # noqa: BLE001
        new = {"reachable": False, "status": _status_cache["status"], "at": _status_cache["at"],
               "error": f"{type(e).__name__}"}
    with _status_lock:
        _status_cache.update(new)


def status() -> dict:
    with _status_lock:
        return dict(_status_cache)


def worker(stop: threading.Event) -> None:
    """Background loop: Stuart status ~1/s, deliver outboxes, escalate alerts."""
    from . import alerts  # noqa: PLC0415 - avoid import cycle
    while not stop.is_set():
        for job in (flush_sms, alerts.escalate_due, flush_sync, refresh_status):  # urgent work first
            try:
                job()
            except Exception as e:  # noqa: BLE001 - one failing job must not stop the others
                db.warn("worker", f"{job.__name__}: {type(e).__name__}: {e}"[:300])
        stop.wait(1.0)
