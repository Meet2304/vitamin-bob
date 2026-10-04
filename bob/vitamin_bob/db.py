"""bob.db: Bob's own SQLite database (no other module reads it).

Principles: every row that could travel upward carries hub_id; ids are globally unique (uuid4 hex);
clinics, villages and routes are seeded from data (seed/demo_district.json), so a new clinic is
rows, not code; every triage records the protocol and model version that produced it.

    python -m vitamin_bob.db --reset     # recreate and reseed (deletes all calls and triages)
"""

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS hubs (hub_id TEXT PRIMARY KEY, name TEXT, contact_name TEXT, contact_phone TEXT);
CREATE TABLE IF NOT EXISTS villages (village_id TEXT PRIMARY KEY, hub_id TEXT, name TEXT);
CREATE TABLE IF NOT EXISTS clinics (
  clinic_id TEXT PRIMARY KEY, hub_id TEXT, label TEXT, name TEXT, hours TEXT, capacity_per_day INTEGER,
  referral INTEGER, status TEXT, status_source TEXT, status_at TEXT, reopen_at TEXT);
CREATE TABLE IF NOT EXISTS clinic_routes (village_id TEXT, clinic_id TEXT, rank INTEGER, travel_minutes INTEGER,
  PRIMARY KEY (village_id, clinic_id));
CREATE TABLE IF NOT EXISTS clinicians (clinician_id TEXT PRIMARY KEY, clinic_id TEXT, name TEXT, phone TEXT,
  on_duty_at TEXT);
CREATE TABLE IF NOT EXISTS clinic_status_log (id TEXT PRIMARY KEY, clinic_id TEXT, status TEXT, source TEXT,
  at TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS patients (patient_id TEXT PRIMARY KEY, hub_id TEXT, patient_key TEXT UNIQUE, phone TEXT,
  preferred_lang TEXT, village_id TEXT, last_clinic_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS protocols (version TEXT PRIMARY KEY, approved_by TEXT, approved_at TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, type TEXT, call_id TEXT, received_at TEXT,
  response TEXT);
CREATE TABLE IF NOT EXISTS missed_calls (missed_call_id TEXT PRIMARY KEY, phone TEXT, line_id TEXT, at TEXT,
  callback INTEGER, reason TEXT);
CREATE TABLE IF NOT EXISTS sessions (call_id TEXT PRIMARY KEY, hub_id TEXT, missed_call_id TEXT, patient_id TEXT,
  phone TEXT, line_id TEXT, lang TEXT, step TEXT, state TEXT, started_at TEXT, ended_at TEXT, end_reason TEXT);
CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, at TEXT, who TEXT,
  kind TEXT, text TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS triages (triage_id TEXT PRIMARY KEY, hub_id TEXT, call_id TEXT, code TEXT,
  protocol_version TEXT, model_version TEXT, lang TEXT, age_group TEXT, tier TEXT, reasons TEXT, unknowns TEXT,
  answers TEXT, transcript TEXT, routed_clinic_id TEXT, skipped TEXT, outcome TEXT, questions INTEGER,
  understand_ms INTEGER, created_at TEXT, forced_uncertain INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS appointments (appointment_id TEXT PRIMARY KEY, triage_id TEXT, clinic_id TEXT,
  code TEXT, tier TEXT, slot_start TEXT, priority INTEGER, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS alerts (alert_id TEXT PRIMARY KEY, hub_id TEXT, triage_id TEXT, call_id TEXT, code TEXT,
  clinic_id TEXT, tier TEXT, kind TEXT, summary TEXT, phone TEXT, created_at TEXT, last_sent_at TEXT,
  level INTEGER DEFAULT 0, escalated_to TEXT, acked_by TEXT, acked_at TEXT);
CREATE TABLE IF NOT EXISTS sms_outbox (message_id TEXT PRIMARY KEY, to_phone TEXT, text TEXT, priority TEXT,
  purpose TEXT, status TEXT, attempts INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS sms_inbox (message_id TEXT PRIMARY KEY, phone TEXT, text TEXT, at TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS sync_outbox (record_id TEXT PRIMARY KEY, kind TEXT, payload TEXT, status TEXT,
  attempts INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, acked_at TEXT);
CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, source TEXT, text TEXT);
"""

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def now() -> datetime:
    return datetime.now().astimezone()


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat(timespec="seconds")


def parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
            if not _conn.execute("SELECT 1 FROM hubs").fetchone():
                # All or nothing: a half-seeded database would silently lose clinicians.
                _conn.execute("BEGIN IMMEDIATE")
                try:
                    seed(_conn)
                    _conn.execute("COMMIT")
                except BaseException:
                    _conn.execute("ROLLBACK")
                    raise
        return _conn


@contextmanager
def tx():
    """One transaction under the process-wide lock. SQLite is fast; holding the lock is cheap."""
    with _lock:
        c = conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise


def q(sql: str, *args) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def one(sql: str, *args) -> dict | None:
    rows = q(sql, *args)
    return rows[0] if rows else None


def ex(sql: str, *args) -> None:
    with _lock:
        conn().execute(sql, args)


def warn(source: str, text: str) -> None:
    ex("INSERT INTO warnings (at, source, text) VALUES (?, ?, ?)", iso(), source, text)


def hub() -> dict:
    return one("SELECT * FROM hubs LIMIT 1")


def seed(c: sqlite3.Connection) -> None:
    """One phone may serve several clinics (in the demo, Meet's phone is every clinician)."""
    from .privacy import norm_phone, patient_key  # noqa: PLC0415 - avoid an import cycle at module load
    data = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))
    h = data["hub"]
    hub_id, at = h["hub_id"], iso()
    c.execute("INSERT INTO hubs VALUES (?, ?, ?, ?)",
              (hub_id, h["name"], h["district_contact"]["name"], norm_phone(h["district_contact"]["phone"])))
    for v in data["villages"]:
        c.execute("INSERT INTO villages VALUES (?, ?, ?)", (v["village_id"], hub_id, v["name"]))
    for cl in data["clinics"]:
        # Seeded as open and confirmed now, so the demo starts from a known state.
        c.execute("INSERT INTO clinics VALUES (?, ?, ?, ?, ?, ?, ?, 'open', 'seed', ?, NULL)",
                  (cl["clinic_id"], hub_id, cl["label"], cl["name"], cl["hours"], cl["capacity_per_day"],
                   int(cl["referral"]), at))
    for village_id, route in data["routes"].items():
        for rank, (clinic_id, minutes) in enumerate(route):
            c.execute("INSERT INTO clinic_routes VALUES (?, ?, ?, ?)", (village_id, clinic_id, rank, minutes))
    for cn in data["clinicians"]:
        c.execute("INSERT INTO clinicians VALUES (?, ?, ?, ?, NULL)",
                  (new_id(), cn["clinic_id"], cn["name"], norm_phone(cn["phone"])))
    for p in data.get("patients", []):
        phone = norm_phone(p["phone"])
        c.execute("INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                  (new_id(), hub_id, patient_key(phone), phone, p.get("preferred_lang"),
                   p.get("village_id"), at))
    c.execute("INSERT INTO protocols VALUES (?, NULL, NULL, ?)",
              (config.PROTOCOL_VERSION, "Drafted from WHO IMCI danger signs; NOT yet clinician-reviewed."))


def default_village_id() -> str:
    return json.loads(config.SEED_FILE.read_text(encoding="utf-8"))["default_village_id"]


def reset() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        for suffix in ("", "-wal", "-shm"):
            p = config.DB_PATH.with_name(config.DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
        conn()


if __name__ == "__main__":
    import sys

    if any(a.startswith("--reset") for a in sys.argv[1:]):
        reset()
        print(f"Recreated and seeded {config.DB_PATH}")
    else:
        conn()
        print(f"{config.DB_PATH}: {len(q('SELECT * FROM clinics'))} clinics")
