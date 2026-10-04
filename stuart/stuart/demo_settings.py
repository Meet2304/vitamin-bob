"""Demo setup: who is Kevin, who is the demonstration patient, who is the clinician.

Saving never changes the running demo. It writes a private *pending* revision under the profile's
runtime directory (git-ignored). The integrated launcher applies it at startup, before Stuart's
call and SMS workers or Bob's worker start:

  * Kevin's number      -> the profile's line_phone (the number people dial; it does NOT change the SIM)
  * patient + clinician -> Stuart's allowed_phones (previously managed numbers are replaced; other
                           peers, such as an SMS Central receiver, are preserved)
  * clinician           -> registered in Bob's database against the chosen clinic (idempotent upsert;
                           no reset, no reseed, history untouched)

If applying fails, calls and outgoing SMS stay disabled for that run and the error is reported.
"""
import json
import os
import re
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .runtime import Profile

E164 = re.compile(r"^\+[1-9]\d{6,14}$")
CLINICIAN_ID = "demo-clinician"  # the one clinician row this screen manages in bob.db
COUNTRIES = [
    {"code": "+1", "label": "United States / Canada (+1)"},
    {"code": "+91", "label": "India (+91)"},
    {"code": "+44", "label": "United Kingdom (+44)"},
    {"code": "+971", "label": "United Arab Emirates (+971)"},
    {"code": "+65", "label": "Singapore (+65)"},
    {"code": "+61", "label": "Australia (+61)"},
    {"code": "+82", "label": "South Korea (+82)"},
]


class ClinicianIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=4, max_length=24)
    clinic_id: str = Field(min_length=1, max_length=40)


class SettingsIn(BaseModel):
    """The fixed schema the setup screen may write. Nothing else: no paths, no env, no commands."""
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)  # the revision the browser last saw; stale writes are rejected
    country: str | None = Field(default=None, max_length=5)
    kevin_phone: str = Field(min_length=4, max_length=24)
    patient_phone: str = Field(min_length=4, max_length=24)
    clinician: ClinicianIn | None = None


def normalize(raw: str, country: str | None) -> str:
    """'+1 (412) 555-0100' or '412 555 0100' with country +1 -> '+14125550100'. Never assumes a country."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        if not country or not re.fullmatch(r"\+[1-9]\d{0,3}", country):
            raise ValueError(f"“{raw}” has no country code: choose a country or start with +")
        s = country + s.lstrip("0")
    if not E164.fullmatch(s):
        raise ValueError(f"“{raw}” is not a valid international number")
    return s


def settings_path(profile: Profile) -> Path:
    return profile.runtime_dir / "demo-settings.json"


def read_state(profile: Profile) -> dict:
    p = settings_path(profile)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # First use: describe what the active profile already contains, without inventing anything.
    patient = next((x for x in profile.allowed_phones if x != profile.central_phone), None)
    return {"revision": 0, "applied_revision": 0, "pending": None, "error": None,
            "applied": {"kevin_phone": profile.line_phone, "patient_phone": patient, "clinician": None},
            "managed_phones": [patient] if patient else []}


def _write_state(profile: Profile, state: dict) -> None:
    p = settings_path(profile)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(p)


def validate(body: SettingsIn, clinics: dict[str, str], clinician_phones: dict[str, str], district_phone: str | None) -> tuple[dict, list[str]]:
    """Normalise and check the whole configuration. Returns (settings, errors)."""
    errors: list[str] = []
    out: dict = {"country": body.country, "clinician": None}
    for key, label in (("kevin_phone", "Kevin"), ("patient_phone", "Patient")):
        try:
            out[key] = normalize(getattr(body, key), body.country)
        except ValueError as e:
            errors.append(f"{label}: {e}")
    if body.clinician:
        c = body.clinician
        try:
            phone = normalize(c.phone, body.country)
            out["clinician"] = {"name": c.name.strip(), "phone": phone, "clinic_id": c.clinic_id}
        except ValueError as e:
            errors.append(f"Clinician: {e}")
        if c.clinic_id not in clinics:
            errors.append("Clinician: choose one of the existing clinics")
    phones = [out.get("kevin_phone"), out.get("patient_phone"), (out["clinician"] or {}).get("phone")]
    present = [p for p in phones if p]
    if len(present) != len(set(present)):
        errors.append("Kevin, patient and clinician must be three different numbers")
    patient = out.get("patient_phone")
    if patient:
        # Bob treats a registered clinician's missed call as a check-in, never as a patient callback.
        other = {p: n for p, n in clinician_phones.items() if n != CLINICIAN_ID}
        if patient in other:
            errors.append("Patient: this number is registered as a clinician; their missed calls would be check-ins")
        if district_phone and patient == district_phone:
            errors.append("Patient: this number is the district contact")
    return out, errors


def save_pending(profile: Profile, body: SettingsIn, settings: dict) -> dict:
    state = read_state(profile)
    if body.revision != state["revision"]:
        raise RuntimeError("These settings changed in another tab; reload before saving")
    state["revision"] += 1
    state["pending"] = settings | {"revision": state["revision"], "saved_at": time.time()}
    _write_state(profile, state)
    return state


def apply_pending(config_path: Path, profile: Profile) -> tuple[Profile, dict]:
    """At startup, before any worker: write the pending revision into the launcher's own profile.

    Returns the profile to run with. On any inconsistency, calls and outgoing SMS are disabled for this
    run and the error is recorded for the setup screen.
    """
    state = read_state(profile)
    pending = state.get("pending")
    if not pending or pending["revision"] <= state.get("applied_revision", 0):
        return profile, state
    try:
        state["applying"] = pending["revision"]
        _write_state(profile, state)
        managed = set(state.get("managed_phones") or [])
        new_managed = {pending["patient_phone"]} | ({pending["clinician"]["phone"]} if pending.get("clinician") else set())
        keep = (set(profile.allowed_phones) - managed) | ({profile.central_phone} if profile.central_phone else set())
        updated = Profile.model_validate(profile.model_dump(mode="json") | {
            "line_phone": pending["kevin_phone"], "allowed_phones": sorted(keep | new_managed)})
        raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
        raw.update(line_phone=updated.line_phone, allowed_phones=updated.allowed_phones)
        tmp = config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        tmp.replace(config_path)
        state.update(applied={k: pending.get(k) for k in ("kevin_phone", "patient_phone", "clinician", "country")},
                     managed_phones=sorted(new_managed), error=None)
        # applied_revision is set only after Bob's clinician registration succeeds (finish_apply).
        _write_state(profile, state)
        return updated, state
    except Exception as e:  # noqa: BLE001 - never start half-configured
        state["error"] = f"Could not apply revision {pending['revision']}: {e}"
        state.pop("applying", None)
        _write_state(profile, state)
        return profile.model_copy(update={"calls_enabled": False, "sms_send_enabled": False}), state


def register_clinician(clinician: dict | None) -> None:
    """Idempotent: the demo clinician row is replaced, removed, or left alone. Cases and alerts are untouched."""
    from vitamin_bob import db  # imported here: Bob is configured by the launcher before this runs
    from vitamin_bob.privacy import norm_phone
    with db.tx() as c:
        c.execute("DELETE FROM clinicians WHERE clinician_id=?", (CLINICIAN_ID,))
        if clinician:
            c.execute("INSERT INTO clinicians VALUES (?, ?, ?, ?, NULL)",
                      (CLINICIAN_ID, clinician["clinic_id"], clinician["name"], norm_phone(clinician["phone"])))


def finish_apply(profile: Profile, state: dict) -> dict:
    """Second half of applying, once Bob is importable. On failure, the caller disables calls and SMS."""
    target = state.get("applying")
    if target is None:
        return state
    try:
        register_clinician(state["applied"].get("clinician"))
        state["applied_revision"] = target
        state["pending"] = None
        state["error"] = None
    except Exception as e:  # noqa: BLE001
        state["error"] = f"Could not register the clinician in Bob for revision {target}: {e}"
    state.pop("applying", None)
    _write_state(profile, state)
    return state


def add_settings_routes(bob_app, profile: Profile, running: Profile):
    """Private operator routes on the local Bob server. Not part of the public website."""
    from fastapi import HTTPException, Request
    from fastapi.responses import FileResponse

    from vitamin_bob import db

    def local(request: Request):
        if request.headers.get("X-VB-Demo") != "1" or request.headers.get("origin", "http://127.0.0.1:8100") != "http://127.0.0.1:8100":
            raise HTTPException(403, "Use the local setup screen")

    def bob_facts():
        clinics = {r["clinic_id"]: r["name"] for r in db.q("SELECT clinic_id, name FROM clinics ORDER BY referral, label")}
        clinicians = {r["phone"]: r["clinician_id"] for r in db.q("SELECT phone, clinician_id FROM clinicians")}
        recipients = db.q("SELECT clinic_id, clinician_id, phone FROM clinicians")
        return clinics, clinicians, recipients, db.hub()["contact_phone"]

    @bob_app.get("/dashboard/setup")
    def setup_page():
        return FileResponse(Path(__file__).with_name("setup.html"), media_type="text/html")

    @bob_app.get("/api/demo/settings")
    def get_settings():
        state = read_state(profile)
        clinics, _, recipients, _ = bob_facts()
        demo = [r for r in recipients if r["clinician_id"] == CLINICIAN_ID]
        return {
            "revision": state["revision"], "applied_revision": state.get("applied_revision", 0),
            "applied": state.get("applied"), "pending": state.get("pending"), "error": state.get("error"),
            "clinics": [{"id": k, "name": v,
                         "real_recipient": any(r["clinic_id"] == k for r in demo)} for k, v in clinics.items()],
            "countries": COUNTRIES,
            "running": {"kevin_phone": running.line_phone, "calls_enabled": running.calls_enabled,
                        "sms_send_enabled": running.sms_send_enabled},
            "capabilities": {
                "outgoing_sms": running.sms_send_enabled,
                "urgent_clinician_alerts": "built: HIGH, EMERGENCY and UNCERTAIN cases (needs outgoing SMS)",
                "patient_completion_summary": None,
                "clinician_consultation_summary": None,
                "push_notifications": None,
                "sms_acknowledgement_verified": False,
            },
            "restart": [r".\Stop-IntegratedDemo.ps1 -Mode phone", r".\Start-IntegratedDemo.ps1 -Mode phone"],
        }

    @bob_app.put("/api/demo/settings")
    async def put_settings(request: Request):
        local(request)
        try:
            body = SettingsIn.model_validate(await request.json())
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Invalid settings: {e}") from None
        clinics, clinician_phones, _, district = bob_facts()
        settings, errors = validate(body, clinics, clinician_phones, district)
        if errors:
            raise HTTPException(422, {"errors": errors})
        try:
            state = save_pending(profile, body, settings)
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from None
        return {"saved": True, "revision": state["revision"], "restart_required": True}


def env_overrides(running: Profile) -> dict:
    """Environment values that must follow the profile actually used for this run."""
    return {"VB_ANDROID_CALLS_ENABLED": str(int(running.calls_enabled)),
            "VB_SMS_SEND_ENABLED": str(int(running.sms_send_enabled)),
            **({"VB_LINE_PHONE": running.line_phone} if running.line_phone else {})}


def disable_workers(running: Profile) -> Profile:
    os.environ.update(VB_ANDROID_CALLS_ENABLED="0", VB_SMS_SEND_ENABLED="0")
    return running.model_copy(update={"calls_enabled": False, "sms_send_enabled": False})
