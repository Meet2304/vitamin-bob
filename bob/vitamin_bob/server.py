"""Bob's HTTP service on Kevin (contract 7.1): events in, action lists out, plus the dashboard.

    python -m vitamin_bob.server          # http://127.0.0.1:8100, dashboard at /dashboard

Guarantees:
  * A repeated event_id gets the exact same response (stored in bob.db before replying).
  * Events for one call are handled one at a time, in arrival order.
  * Every action list is validated against the contract before it leaves; if Bob ever produced an
    invalid one, it sends the bilingual fallback and a hangup instead, and the call becomes UNCERTAIN.
"""

import json
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from . import alerts, clinics, config, contract, conversation, db, sms_commands, stuart_client, sync, understand
from .privacy import mask
from .prompts import SYSTEM, clip_path, prompts_dir

_call_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()
_model_cache = {"at": 0.0, "available": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.conn()
    if not clip_path(SYSTEM, "fallback").exists():
        db.warn("startup", f"{clip_path(SYSTEM, 'fallback')} missing: run tools/gen_prompts.py")
    stop = threading.Event()
    t = threading.Thread(target=stuart_client.worker, args=(stop,), daemon=True, name="bob-worker")
    t.start()
    yield
    stop.set()


app = FastAPI(title="Vitamin Bob", lifespan=lifespan)


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        return _call_locks[key]


@app.get("/v1/health")
def health():
    return {"ok": True, "module": "bob"}


@app.post("/v1/events")
def events(request: Request, body: dict = Body(...)):
    if request.headers.get(contract.HEADER) != contract.VERSION:
        db.warn("contract", f"event without {contract.HEADER}: {contract.VERSION} "
                            f"(got {request.headers.get(contract.HEADER)!r})")
    try:
        ev = contract.EVENT.validate_python(body).model_dump()
    except ValidationError as e:
        db.warn("contract", f"invalid event rejected: {e.errors()[0]['msg']} {e.errors()[0]['loc']}")
        return JSONResponse({"error": "invalid event", "detail": e.errors()[:3]}, status_code=400)

    key = ev.get("call_id") or ev.get("missed_call_id") or "misc"
    with _lock_for(key):
        prior = db.one("SELECT response FROM events WHERE event_id=?", ev["event_id"])
        if prior:
            return json.loads(prior["response"])  # duplicate: identical answer, no side effects
        response = dispatch(ev)
        db.ex("INSERT INTO events VALUES (?, ?, ?, ?, ?)", ev["event_id"], ev["type"], ev.get("call_id"), db.iso(),
              json.dumps(response, ensure_ascii=False))
    return response


def dispatch(ev: dict) -> dict:
    t = ev["type"]
    if t == "missed_call":
        return on_missed_call(ev)
    if t in ("call_started", "action_result"):
        try:
            resp = (conversation.on_call_started if t == "call_started" else conversation.on_action_result)(ev)
        except Exception as e:  # noqa: BLE001 - a bug must never leave a patient in silence
            db.warn("conversation", f"{ev.get('call_id')}: {type(e).__name__}: {e}"[:300])
            resp = {"actions": []}
        problems = contract.action_list_problems(resp)
        if problems:
            db.warn("contract", f"{ev.get('call_id')}: invalid action list replaced by fallback: {problems[:2]}")
            resp = {"actions": conversation.plays(SYSTEM, ["fallback"]) + [conversation.hangup()]}
            conversation.log(ev["call_id"], "system", "error", "Bob error: fallback played; clinician will follow up")
        return resp
    if t == "call_ended":
        return conversation.on_call_ended(ev)
    if t == "callback_failed":
        return conversation.on_callback_failed(ev)
    if t == "sms_received":
        result = sms_commands.handle(ev["phone"], ev["text"])
        db.ex("INSERT OR IGNORE INTO sms_inbox VALUES (?, ?, ?, ?, ?)",
              ev["message_id"], ev["phone"], ev["text"], db.iso(), result)
        return {"ack": True}
    if t == "sms_status":
        db.ex("UPDATE sms_outbox SET status=?, updated_at=? WHERE message_id=?", ev["status"], db.iso(),
              ev["message_id"])
        return {"ack": True}
    if t == "sync_status":
        db.ex("UPDATE sync_outbox SET status=?, updated_at=?, acked_at=CASE WHEN ?='acked' THEN ? ELSE acked_at END "
              "WHERE record_id=?", ev["status"], db.iso(), ev["status"], db.iso(), ev["record_id"])
        return {"ack": True}
    return {"ack": True}


def on_missed_call(ev: dict) -> dict:
    """Decide who gets a callback. A registered clinician's missed call is a free check-in instead."""
    phone = ev["phone"]
    if clinic := sms_commands.checkin(phone):
        callback, reason = False, f"clinician check-in: {clinic['name']} on duty"
    elif phone == db.hub()["contact_phone"]:
        callback, reason = False, "district contact"
    else:
        callback, reason = True, "patient"
    db.ex("INSERT OR IGNORE INTO missed_calls VALUES (?, ?, ?, ?, ?, ?)",
          ev["missed_call_id"], phone, ev["line_id"], db.iso(), int(callback), reason)
    return {"ack": True, "callback": callback}


# --- dashboard --------------------------------------------------------------------------------
DASHBOARD = Path(__file__).with_name("dashboard.html")


@app.get("/")
def root():
    return RedirectResponse("/dashboard")


@app.get("/dashboard")
def dashboard():
    return FileResponse(DASHBOARD, media_type="text/html")


def _model_available() -> bool:
    if time.time() - _model_cache["at"] > 5:
        _model_cache.update(at=time.time(), available=understand.model_available(timeout=0.3))
    return _model_cache["available"]


def _masked_stuart() -> dict:
    s = stuart_client.status()
    st = json.loads(json.dumps(s.get("status") or {}))
    for line in st.get("lines", []):
        line["msisdn"] = mask(line.get("msisdn"))
    for group in ("queue", "active_calls"):
        for item in st.get(group, []):
            item["phone"] = mask(item.get("phone"))
    return {"reachable": s["reachable"], "at": s["at"], "error": s["error"], "status": st}


def _calls(limit: int = 12) -> list[dict]:
    out = []
    for r in db.q("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", limit):
        st = json.loads(r["state"] or "{}")
        turns = db.q("SELECT at, who, kind, text, detail FROM turns WHERE call_id=? ORDER BY id", r["call_id"])
        for t in turns:
            t["detail"] = json.loads(t["detail"] or "{}")
        tri = db.one("SELECT t.*, c.name AS clinic_name FROM triages t LEFT JOIN clinics c "
                     "ON c.clinic_id=t.routed_clinic_id WHERE call_id=?", r["call_id"])
        if tri:
            for k in ("reasons", "unknowns", "answers", "skipped"):
                tri[k] = json.loads(tri[k] or "null")
            tri["appointment"] = db.one("SELECT slot_start, priority, status FROM appointments WHERE triage_id=?",
                                        tri["triage_id"])
        out.append({"call_id": r["call_id"], "phone": mask(r["phone"]), "lang": r["lang"], "step": r["step"],
                    "started_at": r["started_at"], "ended_at": r["ended_at"], "end_reason": r["end_reason"],
                    "live": r["ended_at"] is None, "understanding": st.get("understanding"), "turns": turns,
                    "triage": tri})
    return out


def _costs(stuart: dict) -> dict:
    today = db.now().strftime("%Y-%m-%d")
    cases = db.one("SELECT COUNT(*) AS n FROM triages WHERE created_at LIKE ?", today + "%")["n"]
    secs = 0
    for r in db.q("SELECT started_at, ended_at FROM sessions WHERE started_at LIKE ? AND ended_at IS NOT NULL",
                  today + "%"):
        secs += (db.parse(r["ended_at"]) - db.parse(r["started_at"])).total_seconds()
    sms = (stuart.get("status") or {}).get("sms", {})
    segments = sms.get("segments_today")
    if segments is None:  # Stuart unreachable: estimate from Bob's own outbox (1 segment per 70 chars, Unicode-safe)
        segments = sum(-(-len(m["text"]) // 153) for m in db.q("SELECT text FROM sms_outbox WHERE created_at LIKE ?",
                                                                today + "%"))
    sms_inr = segments * config.SMS_SEGMENT_INR
    call_inr = (secs / 60) * config.CALL_MINUTE_INR
    return {"cases_today": cases, "sms_sent_today": sms.get("sent_today"), "segments_today": segments,
            "call_minutes_today": round(secs / 60, 1), "sms_inr": round(sms_inr, 2), "call_inr": round(call_inr, 2),
            "per_case_inr": round((sms_inr + call_inr) / cases, 2) if cases else None,
            "prices": {"sms_segment_inr": config.SMS_SEGMENT_INR, "call_minute_inr": config.CALL_MINUTE_INR},
            "patient_pays": 0}


@app.get("/api/state")
def state():
    stuart = _masked_stuart()
    eval_path = Path(__file__).resolve().parents[1] / "eval" / "results_summary.json"
    return {
        "now": db.iso(), "hub": db.hub() | {"contact_phone": mask(db.hub()["contact_phone"])},
        "contract": contract.VERSION, "bob_url": config.BOB_URL, "stuart_url": config.STUART_URL,
        "model": {"mode": config.UNDERSTAND, "name": config.MODEL_NAME, "available": _model_available(),
                  "url": urlparse(config.LLM_URL).netloc},
        "protocol": db.one("SELECT * FROM protocols LIMIT 1"),
        "stuart": stuart,
        "missed_calls": [dict(m, phone=mask(m["phone"])) for m in
                         db.q("SELECT * FROM missed_calls ORDER BY at DESC LIMIT 12")],
        "calls": _calls(),
        "clinics": clinics.snapshot(),
        "alerts": alerts.snapshot(),
        "sync": sync.snapshot(),
        "sms": [dict(m, to_phone=mask(m["to_phone"])) for m in
                db.q("SELECT * FROM sms_outbox ORDER BY created_at DESC LIMIT 15")],
        "sms_inbox": [dict(m, phone=mask(m["phone"])) for m in
                      db.q("SELECT * FROM sms_inbox ORDER BY at DESC LIMIT 10")],
        "costs": _costs(stuart),
        "warnings": db.q("SELECT * FROM warnings ORDER BY id DESC LIMIT 8"),
        "eval": json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.exists() else None,
        "prompts_ready": (prompts_dir() / "system" / "fallback.wav").exists(),
    }


@app.post("/api/clinics/{clinic_id}/status")
def set_clinic_status(clinic_id: str, body: dict = Body(...)):
    status = body.get("status")
    if status not in clinics.STATUSES or not db.one("SELECT 1 FROM clinics WHERE clinic_id=?", clinic_id):
        return JSONResponse({"error": "bad clinic or status"}, status_code=400)
    clinics.set_status(clinic_id, status, "dashboard", detail="dashboard toggle")
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/ack")
def ack_alert(alert_id: str, body: dict = Body(default={})):
    a = alerts.ack(alert_id, by=body.get("by") or "Dashboard")
    return {"ok": bool(a)}


@app.post("/api/sync/daily_summary")
def daily_summary():
    return {"record_id": sync.queue_daily_summary()}


def main() -> None:
    import uvicorn

    u = urlparse(config.BOB_URL)
    uvicorn.run(app, host=u.hostname or "127.0.0.1", port=u.port or 8100, log_level="warning")


if __name__ == "__main__":
    main()
