"""Demo setup: validation, pending revisions, startup application, Bob clinician registration.

    python tests/test_demo_settings.py      (or pytest)

Uses temporary profiles and a temporary bob.db seeded from bob/tests/seed_test.json; made-up numbers only.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp())
os.environ["VB_BOB_DB"] = str(TMP / "bob.db")
os.environ["VB_SEED_FILE"] = str(ROOT / "bob/tests/seed_test.json")
os.environ["VB_DATA_DIR"] = str(TMP)
sys.path[:0] = [str(ROOT / "stuart"), str(ROOT / "bob")]

from stuart.demo_settings import (  # noqa: E402
    CLINICIAN_ID, SettingsIn, apply_pending, finish_apply, normalize, read_state, save_pending, validate,
)
from stuart.runtime import load_profile  # noqa: E402
from vitamin_bob import db, sms_commands  # noqa: E402

KEVIN, PATIENT, CLIN, CENTRAL, OLD = "+15550100001", "+15550100002", "+15550100003", "+15550100009", "+15550100008"


def make_profile(name: str, allowed: list[str], central: str | None = None) -> Path:
    d = TMP / name
    (d / "runtime").mkdir(parents=True, exist_ok=True)
    raw = {"mode": "simulator", "data_dir": str(d / "data"), "runtime_dir": str(d / "runtime"),
           "allowed_phones": allowed, "line_phone": "+15550100099", "calls_enabled": True}
    if central:
        raw.update(central_phone=central, sync_transport="sms")
    path = d / "demo-phone.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def facts():
    clinics = {r["clinic_id"]: r["name"] for r in db.q("SELECT clinic_id, name FROM clinics")}
    clinicians = {r["phone"]: r["clinician_id"] for r in db.q("SELECT phone, clinician_id FROM clinicians")}
    return clinics, clinicians, db.hub()["contact_phone"]


def body(**kw):
    base = {"revision": 0, "country": None, "kevin_phone": KEVIN, "patient_phone": PATIENT,
            "clinician": {"name": "Dr Demo", "phone": CLIN, "clinic_id": "devgaon"}}
    return SettingsIn.model_validate(base | kw)


def test_normalize():
    assert normalize("+1 (555) 010-0001", None) == KEVIN
    assert normalize("555 010 0001", "+1") == KEVIN
    assert normalize("0091 98765 43210", None) == "+919876543210"
    for bad, country in [("555 010 0001", None), ("12", "+1"), ("+0123456789", None)]:
        try:
            normalize(bad, country)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass


def test_validation_rejects_conflicts():
    db.conn()
    clinics, clinicians, district = facts()
    _, errs = validate(body(patient_phone=KEVIN), clinics, clinicians, district)
    assert any("three different" in e for e in errs), errs
    _, errs = validate(body(clinician={"name": "X", "phone": CLIN, "clinic_id": "nowhere"}), clinics, clinicians, district)
    assert any("existing clinics" in e for e in errs), errs
    _, errs = validate(body(patient_phone="+919000000001"), clinics, clinicians, district)  # a seeded clinician
    assert any("registered as a clinician" in e for e in errs), errs
    _, errs = validate(body(patient_phone=district), clinics, clinicians, district)
    assert any("district contact" in e for e in errs), errs
    settings, errs = validate(body(clinician=None), clinics, clinicians, district)
    assert not errs and settings["clinician"] is None  # the demo still works without a clinician


def test_save_apply_and_history():
    db.conn()
    cfg = make_profile("p1", [OLD, CENTRAL], central=CENTRAL)
    prof = load_profile(cfg)
    # Pretend OLD was the previously managed patient; CENTRAL must survive.
    state = read_state(prof)
    state["managed_phones"] = [OLD]
    (prof.runtime_dir / "demo-settings.json").write_text(json.dumps(state))
    db.ex("INSERT INTO triages (triage_id, call_id, tier, created_at) VALUES ('t-history', 'c', 'LOW', '2026-10-04T00:00:00')")

    clinics, clinicians, district = facts()
    settings, errs = validate(body(), clinics, clinicians, district)
    assert not errs, errs
    save_pending(prof, body(), settings)
    try:
        save_pending(prof, body(), settings)  # same base revision again: stale
        raise AssertionError("stale save accepted")
    except RuntimeError:
        pass
    # Saving alone does not touch the profile the running demo uses.
    assert load_profile(cfg).line_phone == "+15550100099"

    running, state = apply_pending(cfg, load_profile(cfg))
    state = finish_apply(running, state)
    after = load_profile(cfg)
    assert after.line_phone == KEVIN
    assert set(after.allowed_phones) == {PATIENT, CLIN, CENTRAL}, after.allowed_phones  # OLD removed, CENTRAL kept
    assert state["applied_revision"] == 1 and state["pending"] is None and not state.get("error")
    row = db.one("SELECT * FROM clinicians WHERE clinician_id=?", CLINICIAN_ID)
    assert row["phone"] == CLIN and row["clinic_id"] == "devgaon"
    assert db.one("SELECT 1 AS ok FROM triages WHERE triage_id='t-history'")  # history untouched
    # A clinician's missed call is a check-in, not a patient callback.
    assert sms_commands.checkin(CLIN)["clinic_id"] == "devgaon"
    # Restarting with nothing pending changes nothing (idempotent), and numbers persist.
    running2, state2 = apply_pending(cfg, load_profile(cfg))
    assert running2.line_phone == KEVIN and state2["applied_revision"] == 1
    assert db.one("SELECT COUNT(*) AS n FROM clinicians WHERE clinician_id=?", CLINICIAN_ID)["n"] == 1


def test_failed_apply_disables_workers():
    db.conn()
    cfg = make_profile("p2", [OLD])
    prof = load_profile(cfg)
    state = read_state(prof)
    state.update(revision=1, pending={"revision": 1, "kevin_phone": "not-a-number", "patient_phone": PATIENT,
                                      "clinician": None, "country": None})
    (prof.runtime_dir / "demo-settings.json").write_text(json.dumps(state))
    running, state = apply_pending(cfg, prof)
    assert state["error"] and not running.calls_enabled and not running.sms_send_enabled
    assert load_profile(cfg).line_phone == "+15550100099"  # profile left as it was


if __name__ == "__main__":
    for t in (test_normalize, test_validation_rejects_conflicts, test_save_apply_and_history, test_failed_apply_disables_workers):
        t()
        print("ok ", t.__name__)
    print("ALL PASSED")
