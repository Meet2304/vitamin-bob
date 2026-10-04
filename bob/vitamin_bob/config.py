"""Runtime settings, all overridable by environment variables. No setting needs the internet."""

import os
import secrets
from pathlib import Path

from .prompts import BOB_DIR, data_dir


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


BOB_URL = _env("VB_BOB_URL", "http://127.0.0.1:8100")
STUART_URL = _env("VB_STUART_URL", "http://127.0.0.1:8200")
LLM_URL = _env("VB_LLM_URL", "http://127.0.0.1:8300")  # llama-server with Gemma 4 (tools/start_model.cmd)

# "auto": Gemma if llama-server answers, else the keyword baseline. "gemma" or "keyword" to force.
UNDERSTAND = _env("VB_UNDERSTAND", "auto")
MODEL_NAME = _env("VB_MODEL_NAME", "gemma-4-e2b-it-q8_0")
UNDERSTAND_BUDGET_S = float(_env("VB_UNDERSTAND_BUDGET_S", "17"))  # contract allows 20 s after listen

# Real phone numbers go in seed/demo_district.local.json (git-ignored), which wins when present,
# so personal numbers never reach the public repository. VB_SEED_FILE overrides both.
_LOCAL_SEED = BOB_DIR / "seed" / "demo_district.local.json"
SEED_FILE = Path(_env("VB_SEED_FILE", str(_LOCAL_SEED if _LOCAL_SEED.exists() else BOB_DIR / "seed" / "demo_district.json")))
DB_PATH = Path(_env("VB_BOB_DB", str(data_dir() / "bob.db")))

PROTOCOL_VERSION = "imci-draft-0.3"  # not yet clinician-reviewed
STATUS_FRESH_HOURS = float(_env("VB_STATUS_FRESH_HOURS", "12"))  # older confirmation -> status "unknown"
MAX_TRAVEL_MIN = int(_env("VB_MAX_TRAVEL_MIN", "60"))
ESCALATE_AFTER_S = int(_env("VB_ESCALATE_AFTER_S", "180"))  # unacknowledged urgent alert -> escalate
CHECKIN_REPLY_SMS = _env("VB_CHECKIN_REPLY_SMS", "1") == "1"  # confirm a clinician's missed-call check-in

# Cost estimates shown on the dashboard (rupees). Stuart reports counts; Bob prices them.
SMS_SEGMENT_INR = float(_env("VB_SMS_SEGMENT_INR", "0.20"))
CALL_MINUTE_INR = float(_env("VB_CALL_MINUTE_INR", "0.40"))


def patient_key_secret() -> bytes:
    """Per-hub secret for the privacy-preserving patient key (HMAC of the phone number).

    A plain hash of a phone number is weak (few possible numbers); a keyed hash is only as strong
    as this secret, which stays on Kevin and Central. Long term the key should be ABHA-based.
    """
    if s := os.environ.get("VB_PATIENT_KEY_SECRET"):
        return s.encode()
    path = data_dir() / "bob_patient_key.secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip().encode()
