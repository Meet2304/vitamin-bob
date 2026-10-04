"""Bob's voice. Every sentence Bob says is a list of pre-recorded clips, which maps directly onto
the contract's "zero or more `play` actions".

Clip text lives in `bob/prompts/<lang>.json` (one key per clip); audio lives in
`<VB_DATA_DIR>/prompts/<lang>/<key>.wav`, generated before the demo by tools/gen_prompts.py.
Dynamic parts (clinic name, appointment time, case code digits) are separate clips placed at the
END of a sentence ("Please go now to this clinic: <clinic>"), so a new language needs only
translated rows, never word-order logic in code.
"""

import json
import os
from functools import cache
from pathlib import Path

from .protocol import RED_FLAGS, SYMPTOMS, Tier

BOB_DIR = Path(__file__).resolve().parents[1]
CATALOG_DIR = BOB_DIR / "prompts"
SYSTEM = "system"  # language-neutral clips: lang_menu, fallback, beep

# Keys every language must provide. Clinic, day and hour clips are checked for consistency
# across languages instead, because they follow the clinic data rather than the protocol.
REQUIRED_KEYS = (
    [
        "lang_select", "welcome", "who_is_sick", "describe", "describe_retry", "please_wait",
        "yes_no_hint", "invalid_key", "no_input",
        "out_emergency", "out_high", "out_uncertain", "out_doctor_will_call", "out_appointment",
        "out_time", "case_number", "out_if_worse", "goodbye", "fallback",
    ]
    + [f"q_symptom_{s}" for s in SYMPTOMS]
    + [f"q_days_{s}" for s in SYMPTOMS]
    + [f"q_flag_{f}" for f in RED_FLAGS]
    + [f"digit_{d}" for d in range(10)]
)


def data_dir() -> Path:
    return Path(os.environ.get("VB_DATA_DIR", BOB_DIR.parent / "data")).resolve()


def prompts_dir() -> Path:
    return data_dir() / "prompts"


@cache
def config() -> dict:
    return json.loads((CATALOG_DIR / "languages.json").read_text(encoding="utf-8"))


def languages(enabled_only: bool = True) -> list[dict]:
    langs = [lang for lang in config()["languages"] if lang["enabled"] or not enabled_only]
    return sorted(langs, key=lambda lang: lang["menu_key"])


@cache
def catalog(lang: str) -> dict[str, str]:
    return json.loads((CATALOG_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def clip_path(lang: str, key: str) -> Path:
    return prompts_dir() / lang / f"{key}.wav"


def text_of(lang: str, keys: list[str]) -> str:
    """The words behind a clip list, for logs and the dashboard."""
    return " ".join(catalog(lang).get(k, f"[{k}]") for k in keys)


def lang_for_key(digit: str) -> str | None:
    return next((lang["code"] for lang in languages() if lang["menu_key"] == digit), None)


def question_keys(qid: str) -> list[str]:
    """Clips for a CallSession question id ("symptom:fever", "days:cough", "flag:stiff_neck")."""
    kind, item = qid.split(":", 1)
    if kind == "days":
        return [f"q_days_{item}"]
    return [f"q_{kind}_{item}", "yes_no_hint"]


def digit_keys(code: str) -> list[str]:
    return [f"digit_{c}" for c in code if c.isdigit()]


def outcome_keys(tier: Tier, clinic_id: str, day: str, hour: int, code: str) -> list[str]:
    """The closing sentence for a tier. EMERGENCY never names a clinic: it is always 108."""
    case = ["case_number", *digit_keys(code)]
    if tier == Tier.EMERGENCY:
        return ["out_emergency", *case, "goodbye"]
    clinic = f"clinic_{clinic_id}"
    if tier in (Tier.HIGH, Tier.UNCERTAIN):
        lead = "out_high" if tier == Tier.HIGH else "out_uncertain"
        return [lead, clinic, "out_doctor_will_call", *case, "goodbye"]
    return ["out_appointment", clinic, "out_time", f"day_{day}", f"hour_{hour:02d}",
            *case, "out_if_worse", "goodbye"]


def validate_catalogs() -> list[str]:
    """Problems that would make a call play a missing clip. Empty list means all good."""
    problems = []
    langs = languages(enabled_only=False)
    keysets = {lang["code"]: set(catalog(lang["code"])) for lang in langs}
    for code, keys in keysets.items():
        for k in REQUIRED_KEYS:
            if k not in keys:
                problems.append(f"{code}: missing required key {k}")
        for other, other_keys in keysets.items():
            for k in sorted(other_keys - keys):
                problems.append(f"{code}: missing {k} (present in {other})")
        if f" {next(lang['menu_key'] for lang in langs if lang['code'] == code)} " not in \
                f" {catalog(code)['lang_select']} ":
            problems.append(f"{code}: lang_select text does not mention its menu_key")
    return problems
