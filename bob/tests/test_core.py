"""Fast checks of Bob's logic that the scripted calls don't reach. No model, no Stuart, no network.

    python tests/test_core.py
"""

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

os.environ["VB_BOB_DB"] = str(Path(tempfile.mkdtemp()) / "bob_test.db")
os.environ["VB_STUART_URL"] = "http://127.0.0.1:9"  # nothing listens: outboxes must keep messages
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vitamin_bob import alerts, clinics, config, contract, db, sms_commands, stuart_client, sync  # noqa: E402
from vitamin_bob.protocol import Tier  # noqa: E402

failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok ' if ok else 'XX '} {name}" + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def test_escalation():
    a = alerts.raise_alert(tier="HIGH", kind="triage", code="1234", clinic_id="rampur", summary="test",
                           phone="+919811000099")
    old = db.iso(db.now() - timedelta(seconds=config.ESCALATE_AFTER_S + 5))
    db.ex("UPDATE alerts SET last_sent_at=? WHERE alert_id=?", old, a["alert_id"])
    alerts.escalate_due()
    row = db.one("SELECT * FROM alerts WHERE alert_id=?", a["alert_id"])
    check("unacknowledged alert escalates to the next clinic", row["level"] == 1 and "devgaon" in row["escalated_to"],
          row["escalated_to"])
    sms = db.q("SELECT * FROM sms_outbox WHERE purpose=? AND to_phone='+919000000002'", f"alert:{a['alert_id']}")
    check("escalation SMS queued as urgent", bool(sms) and sms[0]["priority"] == "urgent" and "ESCALATED" in sms[0]["text"])
    alerts.ack("1234", by="test")
    db.ex("UPDATE alerts SET last_sent_at=? WHERE alert_id=?", old, a["alert_id"])
    alerts.escalate_due()
    check("acknowledged alert stops escalating", db.one("SELECT level FROM alerts WHERE alert_id=?", a["alert_id"])["level"] == 1)


def test_back_command_and_freshness():
    result = sms_commands.handle("+919000000001", "BACK 23:59")
    c = db.one("SELECT * FROM clinics WHERE clinic_id='rampur'")
    check("BACK hh:mm closes the clinic with a reopen time", c["status"] == "closed" and c["reopen_at"], result)
    chosen, skipped = clinics.choose("V-RAM")
    check("closed clinic is skipped with a reason", chosen["clinic_id"] == "devgaon" and "back at" in skipped[0]["reason"],
          skipped[0]["reason"])
    db.ex("UPDATE clinics SET reopen_at=? WHERE clinic_id='rampur'", db.iso(db.now() - timedelta(minutes=1)))
    check("clinic reopens when the announced time passes", clinics.choose("V-RAM")[0]["clinic_id"] == "rampur")
    stale = db.iso(db.now() - timedelta(hours=config.STATUS_FRESH_HOURS + 1))
    db.ex("UPDATE clinics SET status='open', reopen_at=NULL, status_at=? WHERE clinic_id IN ('rampur','devgaon','lakhpur')", stale)
    chosen, skipped = clinics.choose("V-RAM")
    check("stale confirmations count as unknown; falls back to the referral hospital",
          chosen["referral"] == 1 and all(s["reason"].startswith("unknown") for s in skipped), chosen["name"])
    clinics.set_status("rampur", "open", "dashboard")


def test_unregistered_and_unknown_commands():
    check("stranger's command is ignored", sms_commands.handle("+919811555555", "CLOSED") == "ignored: unregistered sender")
    check("unknown command gets help", sms_commands.handle("+919000000001", "PLEASE") == "unknown command")


def test_sync_privacy():
    payload = sync.triage_payload(case={"age_group": "child_under_5",
                                        "symptoms": {"fever": {"present": "yes", "days": 3},
                                                     "cough": {"present": "yes", "days": 21},
                                                     "diarrhea": {"present": "yes", "days": None}},
                                        "flags": {f: "yes" for f in sync.FLAG}},
                                  tier=Tier.EMERGENCY, clinic_id="lakhpur", questions=12, call_s=245, lang="gu",
                                  unknowns=3, engine="gemma", patient_key="abcdefghijklm", forced=True)
    check("worst-case triage payload fits in 200 bytes", not contract.sync_payload_problems(payload),
          f"{len(contract.compact(payload).encode())} bytes")
    try:
        stuart_client.queue_sync("triage", {"phone": "+919811000001"})
        check("payload with a phone number is refused", False)
    except ValueError:
        check("payload with a phone number is refused", True)


def test_evidence_is_asymmetric():
    from vitamin_bob.extract import evidence_supports
    from vitamin_bob.understand import _echoes_instruction
    tr = "मुझे तीन दिन से बुखार है, सिर में दर्द भी है। खाँसी नहीं है।"
    check("a 'no' that names the item and a negation passes", evidence_supports("cough", "no", "खाँसी नहीं है", tr))
    check("a 'no' quoting a stray word is rejected", not evidence_supports("fever", "no", "है", tr))
    check("a 'no' without the item's name is rejected", not evidence_supports("convulsions", "no", "नहीं है", tr))
    check("a one-word 'yes' must name the item", evidence_supports("fever", "yes", "बुखार", tr)
          and not evidence_supports("fever", "yes", "है", tr))
    check("a transcript echoing the instruction is treated as no speech",
          _echoes_instruction("તમે આ ફોન ઓડિયો ટ્રાન્સક્રાઇબ કરો.") and not _echoes_instruction(tr))


def test_outbox_survives_stuart_down():
    mid = stuart_client.queue_sms("+919000000001", "test", "normal", "test")
    stuart_client.flush_sms()
    row = db.one("SELECT status, attempts FROM sms_outbox WHERE message_id=?", mid)
    check("SMS stays pending (not lost) while Stuart is down", row["status"] == "pending", str(row))


if __name__ == "__main__":
    db.conn()
    for t in (test_escalation, test_back_command_and_freshness, test_unregistered_and_unknown_commands,
              test_sync_privacy, test_evidence_is_asymmetric, test_outbox_survives_stuart_down):
        print(t.__name__)
        t()
    print(f"\n{'ALL PASSED' if not failures else 'FAILED: ' + ', '.join(failures)}")
    sys.exit(1 if failures else 0)
