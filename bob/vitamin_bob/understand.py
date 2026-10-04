"""Understanding the patient's description on-device with Gemma 4 (via llama-server), in two passes:

  1. audio -> transcript   (Gemma's audio encoder; thinking disabled; plain text out)
  2. transcript -> form    (text only; output locked by a grammar; evidence guard applied)

Two passes rather than one so that (a) the transcript is not distorted by forcing JSON while
listening, and (b) pass 2 is exactly what the text evaluation measures on the vignettes.

The model only fills the fixed form. Every yes/no must quote words found in the transcript
(extract.validate), otherwise it becomes "unknown" and Bob asks on the keypad instead.
If the model is slow, down or returns junk, Bob falls back to the keyword baseline on whatever
transcript it has: worse understanding means more keypad questions, never a skipped safety check.
"""

import base64
import time
from pathlib import Path

import httpx

from . import config
from .extract import KeywordExtractor, empty_result, validate
from .protocol import RED_FLAGS, SYMPTOMS

LANG_NAMES = {"hi": "Hindi", "gu": "Gujarati"}
ITEMS = SYMPTOMS + list(RED_FLAGS)

# Pass 2 output is locked by a grammar to at most 6 lines of "item|yes/no|days|evidence", then END.
# As strict as a JSON schema (only known items and values can be written) at a fraction of the
# tokens: ~4 s instead of ~14 s on the demo laptop, which keeps a call inside the 20 s budget.
MAX_FINDINGS = 6
_item_alts = " | ".join(f'"{i}"' for i in ITEMS)
_lines = "line? " * MAX_FINDINGS
FORM_GRAMMAR = f"""root ::= {_lines}"END"
line ::= item "|" val "|" days "|" ev "\n"
item ::= {_item_alts}
val ::= "yes" | "no"
days ::= [0-9] [0-9]? [0-9]? | "-"
ev ::= [^|\n]+
"""

# Words callers actually use, so a small model links them to the right item (Hindi / Gujarati).
HINTS = {
    "fever": "बुखार, तपना / તાવ", "cough": "खाँसी / ઉધરસ, ખાંસી", "diarrhea": "दस्त, पतले दस्त, loose motion / ઝાડા",
    "convulsions": "दौरा, झटके, मिर्गी / આંચકી, ખેંચ", "altered_consciousness": "बेहोश, सुस्त, पहचान नहीं रहा / બેભાન, સુસ્ત",
    "severe_breathing_difficulty": "साँस लेने में बहुत तकलीफ़ / શ્વાસ લેવામાં તકલીફ",
    "unable_to_drink": "कुछ पी नहीं पा रहा, दूध नहीं पी रहा / પી શકતું નથી",
    "vomits_everything": "सब उल्टी कर देता / બધું ઊલટી કરી નાખે", "stiff_neck": "गर्दन अकड़ / ગરદન અકડાઈ",
    "fast_breathing": "साँस तेज़ चल रही / શ્વાસ ઝડપી", "blood_in_stool": "दस्त में खून / ઝાડામાં લોહી",
    "dehydration_signs": "आँखें धँसी, पेशाब कम / આંખો ઊંડી, પેશાબ ઓછો",
}


def _form_prompt(lang: str) -> str:
    items = "\n".join(f"- {i}: {RED_FLAGS[i]['en'] if i in RED_FLAGS else i} ({HINTS[i]})" for i in ITEMS)
    name = LANG_NAMES.get(lang, "Hindi")
    return f"""You fill in a fixed form from a patient's description, transcribed from a phone call in {name}
(possibly mixed with English, possibly with transcription errors). You do NOT diagnose or advise.

Items (with words patients use):
{items}

Write one line for each item the patient clearly mentions (at most {MAX_FINDINGS}), then END:
item|yes or no|days or -|evidence
- yes if they say the patient has it; no only if they clearly say the patient does not.
- days: for fever, cough, diarrhea only: the number of days if stated ("three days" -> 3,
  "a week" -> 7, "two weeks" -> 14, "since yesterday" -> 1), else -.
- evidence: the shortest exact words (2 to 6) copied character for character from the transcript.
Do NOT write lines for items that are not mentioned. When in doubt, leave it out: that is always safe."""


def parse_form(text: str) -> list[dict]:
    findings = []
    for line in text.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4 and parts[0] in ITEMS:
            days = int(parts[2]) if parts[2].isdigit() else None
            findings.append({"item": parts[0], "value": parts[1], "days": days, "evidence": parts[3].strip()})
    return findings


class Understanding:
    """Result of understanding one description, with what the dashboard needs to explain it."""

    def __init__(self, transcript: str, extraction: dict, engine: str, ms: int, notes: list[str]):
        self.transcript, self.extraction, self.engine, self.ms, self.notes = transcript, extraction, engine, ms, notes


def _chat(messages: list, timeout: float, grammar: str | None = None, max_tokens: int = 300) -> str:
    body = {
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},  # Gemma 4 thinks by default; we can't afford it
    }
    if grammar:
        body["grammar"] = grammar
    r = httpx.post(f"{config.LLM_URL}/v1/chat/completions", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def model_available(timeout: float = 0.5) -> bool:
    try:
        return httpx.get(f"{config.LLM_URL}/health", timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


def use_gemma() -> bool:
    return config.UNDERSTAND == "gemma" or (config.UNDERSTAND == "auto" and model_available())


def transcribe(wav: Path, lang: str, timeout: float) -> str:
    name = LANG_NAMES.get(lang, "Hindi")
    b64 = base64.b64encode(wav.read_bytes()).decode()
    return _chat(
        [{"role": "user", "content": [
            {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}},
            {"type": "text", "text": f"Transcribe this {name} phone audio exactly, in {name} script "
                                     "(keep English words as spoken). Output only the transcript."},
        ]}],
        timeout=timeout, max_tokens=250,
    )


def findings_to_raw(findings: list[dict]) -> dict:
    """Compact model output -> the extractor format that extract.validate checks."""
    raw = {"symptoms": {}, "flags": {}}
    for f in findings:
        item = f.get("item")
        if item in SYMPTOMS:
            raw["symptoms"][item] = {"present": f.get("value"), "days": f.get("days"), "evidence": f.get("evidence")}
        elif item in RED_FLAGS:
            raw["flags"][item] = {"value": f.get("value"), "evidence": f.get("evidence")}
    return raw


def merge_raise_only(primary: dict, backup: dict) -> list[str]:
    """Add the backup's YES findings where the primary said nothing. Never takes a backup NO.

    The model sometimes misses a red flag that is plainly in the transcript (a Gujarati "ખેંચ", fit);
    the keyword list catches those. Adding a YES can only raise urgency, which is the safe direction.
    """
    added = []
    for s, v in backup["symptoms"].items():
        if v["present"] == "yes" and primary["symptoms"][s]["present"] == "unknown":
            primary["symptoms"][s] = dict(v)
            added.append(s)
    for f, v in backup["flags"].items():
        if v == "yes" and primary["flags"][f] == "unknown":
            primary["flags"][f] = "yes"
            added.append(f)
    return added


class GemmaExtractor:
    """Pass 2 on its own: transcript -> validated form, plus raise-only keyword additions.
    Used by the call flow and by the eval, so the eval measures what is deployed."""

    name = "gemma"

    def __init__(self, lang: str = "hi", timeout: float = 30):
        self.lang, self.timeout = lang, timeout

    def __call__(self, transcript: str) -> dict:
        if not transcript.strip():
            return empty_result()
        content = _chat(
            [{"role": "system", "content": _form_prompt(self.lang)},
             {"role": "user", "content": f"Transcript:\n{transcript}"}],
            timeout=self.timeout, grammar=FORM_GRAMMAR, max_tokens=160,
        )
        result = validate(findings_to_raw(parse_form(content)), transcript)
        result["added_by_keyword"] = merge_raise_only(result, KeywordExtractor()(transcript))
        return result


_ECHO_MARKERS = ("transcrib", "ट्रांसक्राइब", "ट्रान्सक्राइब", "ટ્રાન્સક્રાઇબ", "ઓડિયો", "ऑडियो", "phone audio")


def _echoes_instruction(transcript: str) -> bool:
    """On silence or noise, a small model may 'transcribe' the instruction itself. Treat that as no speech."""
    t = transcript.lower()
    return any(m in t for m in _ECHO_MARKERS)


def understand(wav: Path | None, lang: str, sidecar_transcript: str | None = None) -> Understanding:
    """Recording -> transcript + validated form, within the contract's time budget.

    `sidecar_transcript` is a TEST hook: the fake Stuart can place the text the synthetic patient
    said next to the WAV, so the call flow can be tested without the model.
    """
    t0, notes = time.time(), []
    budget = config.UNDERSTAND_BUDGET_S
    transcript, engine = "", "keyword"

    if use_gemma() and wav is not None and wav.exists():
        try:
            transcript = transcribe(wav, lang, timeout=budget * 0.6)
            engine = f"gemma ({config.MODEL_NAME})"
        except Exception as e:  # noqa: BLE001 - any failure falls back safely
            notes.append(f"transcription failed: {type(e).__name__}: {e}"[:200])
    if transcript and _echoes_instruction(transcript):
        notes.append(f"model echoed the instruction instead of speech ({transcript[:40]}...); ignored")
        transcript, engine = "", "keyword"
    if not transcript and sidecar_transcript is not None:
        transcript = sidecar_transcript
        notes.append("transcript from test sidecar (fake Stuart), not from audio")

    extraction = None
    if engine.startswith("gemma") and transcript:
        remaining = budget - (time.time() - t0)
        if remaining > 3:
            try:
                extraction = GemmaExtractor(lang, timeout=remaining)(transcript)
                if extraction.get("added_by_keyword"):
                    notes.append("keyword list added: " + ", ".join(extraction["added_by_keyword"]))
            except Exception as e:  # noqa: BLE001
                notes.append(f"form filling failed: {type(e).__name__}: {e}"[:200])
        else:
            notes.append("no time left for form filling")
    if extraction is None:
        extraction = KeywordExtractor()(transcript) if transcript else empty_result()
        engine = "keyword" if not engine.startswith("gemma") else f"{engine} + keyword form"
    return Understanding(transcript, extraction, engine, int((time.time() - t0) * 1000), notes)
