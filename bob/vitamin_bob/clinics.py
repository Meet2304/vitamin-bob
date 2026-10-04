"""Clinic registry, status, routing with failover, and appointment booking.

Status comes from three free or cheap inputs: a clinician's SMS command, a clinician's free missed
call ("on duty now"), or the dashboard toggle. A status nobody has confirmed recently counts as
"unknown", and Bob never sends a patient to a clinic it is unsure about.

Routing: each village has clinics ordered by travel time. Bob takes the first that is open, has
capacity, has a recent confirmation and is within reach; otherwise the referral (district) hospital.
EMERGENCY always means 108; the nearest open clinic is only told about the case.
"""

import json
from datetime import timedelta

from . import config, db
from .protocol import Tier

STATUSES = ("open", "closed", "full", "unknown")
SLOT_HOURS = range(9, 18)  # appointment arrival hours; each has a pre-recorded clip (hour_09..hour_17)


def effective_status(c: dict) -> tuple[str, str]:
    """(status, why) for a clinic row, applying 'BACK hh:mm' and the freshness rule."""
    status, at = c["status"], db.parse(c["status_at"])
    if status == "closed" and c["reopen_at"] and db.now() >= db.parse(c["reopen_at"]):
        return "open", f"reopened at {db.parse(c['reopen_at']):%H:%M} as announced"
    age_h = (db.now() - at).total_seconds() / 3600
    if status in ("open", "full") and age_h > config.STATUS_FRESH_HOURS:
        return "unknown", f"last confirmed {age_h:.0f} h ago"
    src = {"sms": "SMS from clinician", "missed_call": "clinician missed-call check-in",
           "dashboard": "dashboard", "seed": "start of day"}.get(c["status_source"], c["status_source"])
    when = f"{at:%H:%M}"
    if status == "closed" and c["reopen_at"]:
        return "closed", f"{src} at {when}, back at {db.parse(c['reopen_at']):%H:%M}"
    return status, f"{src} at {when}"


def set_status(clinic_id: str, status: str, source: str, reopen_at: str | None = None, detail: str = "") -> dict:
    assert status in STATUSES, status
    at = db.iso()
    with db.tx() as c:
        c.execute("UPDATE clinics SET status=?, status_source=?, status_at=?, reopen_at=? WHERE clinic_id=?",
                  (status, source, at, reopen_at, clinic_id))
        c.execute("INSERT INTO clinic_status_log VALUES (?, ?, ?, ?, ?, ?)",
                  (db.new_id(), clinic_id, status, source, at, detail))
    from . import sync  # noqa: PLC0415 - sync depends on clinics for names
    sync.queue_clinic_status(clinic_id, status, source)
    return db.one("SELECT * FROM clinics WHERE clinic_id=?", clinic_id)


def booked_today(clinic_id: str, day) -> int:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.q("SELECT slot_start FROM appointments WHERE clinic_id=? AND status != 'cancelled'", clinic_id)
    return sum(1 for r in rows if start <= db.parse(r["slot_start"]) < start + timedelta(days=1))


def has_capacity(c: dict) -> bool:
    return booked_today(c["clinic_id"], db.now()) < c["capacity_per_day"]


def route_for(village_id: str | None) -> list[dict]:
    village_id = village_id or db.default_village_id()
    return db.q("""SELECT c.*, r.travel_minutes, r.rank FROM clinic_routes r JOIN clinics c USING (clinic_id)
                   WHERE r.village_id=? ORDER BY r.rank""", village_id)


def referral() -> dict:
    return db.one("SELECT * FROM clinics WHERE referral=1 LIMIT 1")


def choose(village_id: str | None) -> tuple[dict, list[dict]]:
    """First qualifying clinic and the reasons earlier ones were skipped."""
    skipped = []
    for c in route_for(village_id):
        status, why = effective_status(c)
        if c["travel_minutes"] > config.MAX_TRAVEL_MIN:
            skipped.append({"clinic_id": c["clinic_id"], "name": c["name"],
                            "reason": f"{c['travel_minutes']} min away (limit {config.MAX_TRAVEL_MIN})"})
        elif status != "open":
            skipped.append({"clinic_id": c["clinic_id"], "name": c["name"], "reason": f"{status}: {why}"})
        elif not has_capacity(c):
            skipped.append({"clinic_id": c["clinic_id"], "name": c["name"],
                            "reason": f"no capacity left today ({c['capacity_per_day']} booked)"})
        else:
            return c, skipped
    return referral(), skipped


def next_slot(clinic: dict, tier: Tier) -> tuple[str, int]:
    """(day, hour) for MEDIUM (today or tomorrow) and LOW (next free slot)."""
    open_h, close_h = (int(x.split(":")[0]) for x in clinic["hours"].split("-"))
    hours = [h for h in SLOT_HOURS if open_h <= h < close_h] or list(SLOT_HOURS)
    per_hour = max(1, clinic["capacity_per_day"] // len(hours))
    now = db.now()
    for day_offset in (0, 1):
        day = now + timedelta(days=day_offset)
        for h in hours:
            start = day.replace(hour=h, minute=0, second=0, microsecond=0)
            if start < now + timedelta(minutes=45):
                continue
            n = sum(1 for r in db.q("SELECT slot_start FROM appointments WHERE clinic_id=? AND status!='cancelled'",
                                    clinic["clinic_id"]) if db.parse(r["slot_start"]) == start)
            if n < per_hour:
                return ("today" if day_offset == 0 else "tomorrow"), h
    return "tomorrow", hours[-1]  # overbook the last slot rather than turn a patient away; a human sees it


PRIORITY = {Tier.EMERGENCY: 0, Tier.HIGH: 1, Tier.UNCERTAIN: 2, Tier.MEDIUM: 3, Tier.LOW: 4}


def book(triage_id: str, clinic: dict, tier: Tier, code: str) -> dict:
    """Urgent tiers become a 'come now' entry at the top of the queue; others get a slot."""
    now = db.now()
    if tier >= Tier.UNCERTAIN:
        start, day, hour = now, "now", None
    else:
        day, hour = next_slot(clinic, tier)
        start = (now + timedelta(days=0 if day == "today" else 1)).replace(hour=hour, minute=0, second=0, microsecond=0)
    appt = {"appointment_id": db.new_id(), "triage_id": triage_id, "clinic_id": clinic["clinic_id"], "code": code,
            "tier": tier.name, "slot_start": db.iso(start), "priority": PRIORITY[tier], "status": "booked",
            "created_at": db.iso()}
    with db.tx() as c:
        c.execute("INSERT INTO appointments VALUES (:appointment_id, :triage_id, :clinic_id, :code, :tier, "
                  ":slot_start, :priority, :status, :created_at)", appt)
    appt["day"], appt["hour"] = day, hour
    return appt


def queue(clinic_id: str) -> list[dict]:
    """A clinic's queue: urgent first, then by slot time."""
    return db.q("""SELECT a.*, t.reasons, t.lang FROM appointments a LEFT JOIN triages t USING (triage_id)
                   WHERE a.clinic_id=? AND a.status='booked' ORDER BY a.priority, a.slot_start""", clinic_id)


def clinician_clinic(phone: str) -> dict | None:
    return db.one("""SELECT c.*, k.name AS clinician_name, k.clinician_id FROM clinicians k
                     JOIN clinics c USING (clinic_id) WHERE k.phone=?""", phone)


def clinicians_of(clinic_id: str) -> list[dict]:
    return db.q("SELECT * FROM clinicians WHERE clinic_id=?", clinic_id)


def snapshot() -> list[dict]:
    out = []
    for c in db.q("SELECT * FROM clinics ORDER BY referral, label"):
        status, why = effective_status(c)
        out.append({**c, "effective_status": status, "why": why, "booked_today": booked_today(c["clinic_id"], db.now()),
                    "queue": [dict(a, reasons=json.loads(a["reasons"] or "[]")) for a in queue(c["clinic_id"])]})
    return out
