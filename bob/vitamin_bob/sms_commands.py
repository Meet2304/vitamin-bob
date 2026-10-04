"""Clinician SMS commands, in Latin letters so any phone can type them. Case-insensitive.

    OPEN | CLOSED (or CLOSE) | FULL | BACK 14:00 (or BACK 1400, BACK 2PM) | ACK <code> | STATUS | HELP

A phone registered for several clinics may name one at the end: "CLOSED B", "OPEN devgaon".
Without a name, the command applies to its first clinic (Clinic A first).

Only registered clinician (or district contact) numbers are obeyed; anything else is logged and
ignored without a reply, so strangers cannot change routing or run up SMS costs. Every accepted
command is confirmed with a short reply.
"""

import re
from datetime import timedelta

from . import alerts, clinics, db, stuart_client
from .privacy import norm_phone

HELP = "VB commands: OPEN, CLOSED, FULL, BACK 14:00, ACK <code>, STATUS"


def _parse_time(text: str):
    m = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?\s*(AM|PM)?", text.strip().upper())
    if not m:
        return None
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm == "PM" and h < 12:
        h += 12
    if ampm == "AM" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= mins < 60):
        return None
    t = db.now().replace(hour=h, minute=mins, second=0, microsecond=0)
    return t if t > db.now() else t + timedelta(days=1)


def _pick(mine: list[dict], words: list[str]) -> tuple[dict | None, list[str]]:
    """Choose which of the sender's clinics a command is about; strip a trailing clinic name."""
    if not mine:
        return None, words
    if len(words) >= 2 and len(mine) > 1 and words[0].upper() != "ACK":
        key = words[-1].lower()
        for c in mine:
            if key in (c["clinic_id"].lower(), c["label"].split()[-1].lower(), c["name"].split()[0].lower()):
                return c, words[:-1]
    return mine[0], words


def handle(phone: str, text: str) -> str:
    """Apply a command; returns what happened (also stored in sms_inbox.result)."""
    phone = norm_phone(phone)
    mine = clinics.clinician_clinics(phone)
    is_district = phone == db.hub()["contact_phone"]
    if not mine and not is_district:
        return "ignored: unregistered sender"

    clinic, words = _pick(mine, text.strip().split())
    cmd = words[0].upper().strip(".!") if words else ""
    reply, result = None, None

    if cmd == "ACK" and len(words) >= 2:
        who = clinic["clinician_name"] if clinic else "District contact"
        a = alerts.ack(words[1], by=f"{who} (SMS)")
        reply = f"VB: case {words[1]} acknowledged. Thank you." if a else f"VB: no open alert {words[1]}."
        result = f"ack {words[1]}: {'ok' if a else 'not found'}"
    elif not clinic:
        reply, result = HELP, "district contact: only ACK applies"
    elif cmd in ("OPEN", "CLOSED", "CLOSE", "FULL"):
        status = {"CLOSE": "closed"}.get(cmd, cmd.lower())
        clinics.set_status(clinic["clinic_id"], status, "sms", detail=f"SMS: {text.strip()}")
        result = f"{clinic['name']} -> {status}"
        if status == "open":
            reply = f"VB: {clinic['name']} marked OPEN at {db.now():%H:%M}. Thank you."
        else:
            alt, _ = clinics.choose(_village_of(clinic["clinic_id"]))
            reply = (f"VB: {clinic['name']} marked {status.upper()} at {db.now():%H:%M}. "
                     f"New patients go to {alt['name']}. Send OPEN when ready.")
    elif cmd == "BACK" and len(words) >= 2 and (t := _parse_time(" ".join(words[1:]))):
        clinics.set_status(clinic["clinic_id"], "closed", "sms", reopen_at=db.iso(t), detail=f"SMS: {text.strip()}")
        result = f"{clinic['name']} -> closed until {t:%H:%M}"
        reply = f"VB: {clinic['name']} closed, back at {t:%H:%M}. Patients rerouted until then."
    elif cmd == "STATUS":
        status, why = clinics.effective_status(clinic)
        n = len(clinics.queue(clinic["clinic_id"]))
        reply, result = f"VB: {clinic['name']} is {status.upper()} ({why}). {n} in queue.", "status sent"
    else:
        reply, result = f"VB: not understood. {HELP}", "unknown command"

    if reply:
        stuart_client.queue_sms(phone, reply, "normal", "command_reply")
    return result


def _village_of(clinic_id: str) -> str | None:
    """The village this clinic serves first, to show where its patients will go instead."""
    r = db.one("SELECT village_id FROM clinic_routes WHERE clinic_id=? ORDER BY rank LIMIT 1", clinic_id)
    return r["village_id"] if r else None


def checkin(phone: str) -> dict | None:
    """A free missed call from a registered clinician means 'on duty now'."""
    phone = norm_phone(phone)
    clinic = clinics.clinician_clinic(phone)
    if not clinic:
        return None
    db.ex("UPDATE clinicians SET on_duty_at=? WHERE phone=?", db.iso(), phone)
    clinics.set_status(clinic["clinic_id"], "open", "missed_call", detail=f"check-in by {clinic['clinician_name']}")
    from . import config  # noqa: PLC0415
    if config.CHECKIN_REPLY_SMS:
        stuart_client.queue_sms(phone, f"VB: {clinic['name']} on duty from {db.now():%H:%M}. Thank you.",
                                "normal", "checkin_reply")
    return clinic
