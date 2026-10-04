"""Urgent alerts: every EMERGENCY, HIGH or UNCERTAIN case reaches a person, and an alert nobody
acknowledges is escalated, never silently dropped.

Delivery: the dashboard, plus an `urgent` SMS to the routed clinic's clinicians. If nobody
acknowledges within ESCALATE_AFTER_S, the alert goes to the next qualifying clinic on the
patient's route, then to the district contact, and stays red on the dashboard until acknowledged.
Acknowledge from the dashboard or by SMS: "ACK <code>".
"""

import json

from . import clinics, config, db, stuart_client
from .privacy import mask


def raise_alert(*, tier: str, kind: str, code: str, clinic_id: str | None, summary: str, phone: str | None,
                triage_id: str | None = None, call_id: str | None = None) -> dict:
    alert = {"alert_id": db.new_id(), "hub_id": db.hub()["hub_id"], "triage_id": triage_id, "call_id": call_id,
             "code": code, "clinic_id": clinic_id, "tier": tier, "kind": kind, "summary": summary, "phone": phone,
             "created_at": db.iso(), "last_sent_at": db.iso(), "level": 0, "escalated_to": "[]",
             "acked_by": None, "acked_at": None}
    with db.tx() as c:
        c.execute("""INSERT INTO alerts VALUES (:alert_id, :hub_id, :triage_id, :call_id, :code, :clinic_id, :tier,
                     :kind, :summary, :phone, :created_at, :last_sent_at, :level, :escalated_to, :acked_by,
                     :acked_at)""", alert)
    _notify(alert, clinic_id)
    return alert


def _sms_text(alert: dict, escalated: bool = False) -> str:
    """Fixed template, never generated. The clinician needs the number to call the patient back."""
    head = f"VB {alert['code']} {alert['tier']}" + (" ESCALATED" if escalated else "")
    text = f"{head} | {alert['summary']} | Call {alert['phone'] or '?'} | Reply ACK {alert['code']}"
    return text if len(text) <= 300 else text[:297] + "..."


def _notify(alert: dict, clinic_id: str | None, escalated: bool = False) -> list[str]:
    phones = [c["phone"] for c in clinics.clinicians_of(clinic_id)] if clinic_id else []
    if not phones:
        phones = [db.hub()["contact_phone"]]
    return [stuart_client.queue_sms(p, _sms_text(alert, escalated), "urgent", f"alert:{alert['alert_id']}")
            for p in phones]


def ack(code_or_id: str, by: str) -> dict | None:
    a = db.one("SELECT * FROM alerts WHERE (code=? OR alert_id=?) AND acked_at IS NULL ORDER BY created_at DESC",
               code_or_id, code_or_id)
    if not a:
        return None
    db.ex("UPDATE alerts SET acked_by=?, acked_at=? WHERE alert_id=?", by, db.iso(), a["alert_id"])
    return db.one("SELECT * FROM alerts WHERE alert_id=?", a["alert_id"])


def _next_target(a: dict, tried: list[str]) -> str | None:
    """Next clinic on the patient's route that qualifies, else the referral hospital, else district contact."""
    village = None
    if a["call_id"]:
        s = db.one("SELECT p.village_id FROM sessions s LEFT JOIN patients p USING (patient_id) WHERE s.call_id=?",
                   a["call_id"])
        village = s["village_id"] if s else None
    for c in clinics.route_for(village):
        if c["clinic_id"] not in tried and clinics.effective_status(c)[0] == "open":
            return c["clinic_id"]
    ref = clinics.referral()
    if ref and ref["clinic_id"] not in tried:
        return ref["clinic_id"]
    return "district_contact" if "district_contact" not in tried else None


def escalate_due() -> None:
    now = db.now()
    for a in db.q("SELECT * FROM alerts WHERE acked_at IS NULL"):
        if (now - db.parse(a["last_sent_at"])).total_seconds() < config.ESCALATE_AFTER_S:
            continue
        tried = [a["clinic_id"]] + json.loads(a["escalated_to"])
        target = _next_target(a, tried)
        if target is None:
            db.ex("UPDATE alerts SET last_sent_at=? WHERE alert_id=?", db.iso(), a["alert_id"])
            continue  # everyone tried; it stays red on the dashboard
        if target == "district_contact":
            stuart_client.queue_sms(db.hub()["contact_phone"], _sms_text(a, escalated=True), "urgent",
                                    f"alert:{a['alert_id']}")
        else:
            _notify(a, target, escalated=True)
        db.ex("UPDATE alerts SET level=level+1, last_sent_at=?, escalated_to=? WHERE alert_id=?",
              db.iso(), json.dumps(tried[1:] + [target]), a["alert_id"])


def snapshot(limit: int = 30) -> list[dict]:
    rows = db.q("SELECT a.*, c.name AS clinic_name FROM alerts a LEFT JOIN clinics c USING (clinic_id) "
                "ORDER BY (a.acked_at IS NULL) DESC, a.created_at DESC LIMIT ?", limit)
    names = {c["clinic_id"]: c["name"] for c in db.q("SELECT clinic_id, name FROM clinics")}
    names["district_contact"] = "District contact"
    for r in rows:
        r["phone"] = mask(r["phone"])
        r["escalated_to"] = [names.get(x, x) for x in json.loads(r["escalated_to"])]
        r["age_s"] = int((db.now() - db.parse(r["created_at"])).total_seconds())
    return rows
