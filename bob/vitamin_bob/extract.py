"""Turn the patient's free Hindi description into the fixed form (yes / no / unknown per item).

Two extractors share one interface:
  * LLMExtractor     - a small local model via Ollama, forced to output JSON matching a schema.
  * KeywordExtractor - a plain keyword matcher. It is the "simpler tool" baseline the brief
                        asks about; the eval compares both so the value of the AI is measured,
                        not asserted.

Anti-hallucination guard: every yes/no the LLM returns must quote evidence that literally
appears in the transcript. If the quote is not found, the value is dropped to 'unknown',
which later forces a keypad question or an UNCERTAIN tier. The model can stay silent; it
cannot invent.
"""

import json
import os
import re
import unicodedata

from .protocol import RED_FLAGS, SYMPTOMS
from .rules import NO, UNKNOWN, YES

DEFAULT_MODEL = os.environ.get("VB_MODEL", "gemma3:4b")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    # Drop punctuation and symbols only. Python's \w does NOT match Devanagari vowel signs,
    # so a [^\w] filter would shred Hindi words; filter by Unicode category instead.
    text = "".join(" " if unicodedata.category(ch)[0] in "PS" else ch for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def evidence_ok(evidence: str | None, transcript: str) -> bool:
    if not evidence or not evidence.strip():
        return False
    return _norm(evidence) in _norm(transcript)


# ---------------------------------------------------------------------------
# Output shape shared by both extractors
# ---------------------------------------------------------------------------
def empty_result() -> dict:
    return {
        "symptoms": {s: {"present": UNKNOWN, "days": None} for s in SYMPTOMS},
        "flags": {f: UNKNOWN for f in RED_FLAGS},
        "rejected": [],  # items the model asserted without valid evidence
    }


# ---------------------------------------------------------------------------
# LLM extractor
# ---------------------------------------------------------------------------
_TRI = {"type": "string", "enum": [YES, NO, UNKNOWN]}
_EVID = {"type": "string"}


def _schema() -> dict:
    symptom_props = {
        s: {
            "type": "object",
            "properties": {
                "present": _TRI,
                "days": {"type": ["integer", "null"]},
                "evidence": _EVID,
            },
            "required": ["present", "days", "evidence"],
        }
        for s in SYMPTOMS
    }
    flag_props = {
        f: {
            "type": "object",
            "properties": {"value": _TRI, "evidence": _EVID},
            "required": ["value", "evidence"],
        }
        for f in RED_FLAGS
    }
    return {
        "type": "object",
        "properties": {
            "symptoms": {"type": "object", "properties": symptom_props, "required": SYMPTOMS},
            "flags": {"type": "object", "properties": flag_props, "required": list(RED_FLAGS)},
        },
        "required": ["symptoms", "flags"],
    }


def _system_prompt() -> str:
    flag_lines = "\n".join(f"- {name}: {f['en']}" for name, f in RED_FLAGS.items())
    return f"""You fill in a fixed form from a patient's spoken description, transcribed in Hindi
(possibly mixed with English, possibly with transcription errors). You do NOT diagnose
and you do NOT give advice.

Symptoms: fever, cough, diarrhea. For each, give:
- present: "yes" only if the patient clearly says they have it; "no" only if they clearly say
  they do not; otherwise "unknown".
- days: how many days it has lasted, only if stated; otherwise null.
- evidence: the exact words from the transcript that support your answer, copied verbatim.
  Use "" when present is "unknown".

Red flags:
{flag_lines}
For each, give value ("yes"/"no"/"unknown") and verbatim evidence, with the same rules.

Rules:
- When in doubt, answer "unknown". Never guess. Unknown is always safe.
- Evidence must be copied character for character from the transcript.
- Convert Hindi number words to digits for days (e.g. "तीन दिन" -> 3, "एक हफ़्ता" -> 7)."""


class LLMExtractor:
    name = "llm"

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def __call__(self, transcript: str) -> dict:
        import ollama  # imported lazily so the rest runs without it installed

        resp = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": f"Transcript:\n{transcript}"},
            ],
            format=_schema(),
            options={"temperature": 0},
        )
        raw = json.loads(resp["message"]["content"])
        return validate(raw, transcript)


def validate(raw: dict, transcript: str) -> dict:
    """Keep only answers backed by evidence found in the transcript."""
    out = empty_result()
    for s in SYMPTOMS:
        item = (raw.get("symptoms") or {}).get(s) or {}
        present = item.get("present", UNKNOWN)
        if present in (YES, NO):
            if evidence_ok(item.get("evidence"), transcript):
                out["symptoms"][s]["present"] = present
                days = item.get("days")
                if present == YES and isinstance(days, int) and 0 < days < 365:
                    out["symptoms"][s]["days"] = days
            else:
                out["rejected"].append(s)
    for f in RED_FLAGS:
        item = (raw.get("flags") or {}).get(f) or {}
        value = item.get("value", UNKNOWN)
        if value in (YES, NO):
            if evidence_ok(item.get("evidence"), transcript):
                out["flags"][f] = value
            else:
                out["rejected"].append(f)
    return out


# ---------------------------------------------------------------------------
# Keyword baseline
# ---------------------------------------------------------------------------
KEYWORDS = {
    "fever": ["बुखार", "बुख़ार", "ज्वर", "bukhar", "fever", "तपना", "तप रहा", "तप रही"],
    "cough": ["खांसी", "खाँसी", "khansi", "cough"],
    "diarrhea": ["दस्त", "पतले दस्त", "loose motion", "dast", "पेट चल"],
    "convulsions": ["दौरा", "दौरे", "झटके", "झटका", "मिर्गी"],
    "altered_consciousness": ["बेहोश", "होश नहीं", "सुस्त", "उलझन"],
    "severe_breathing_difficulty": ["साँस लेने में तकलीफ", "सांस लेने में तकलीफ", "साँस नहीं", "सांस नहीं", "दम घुट", "हाँफ"],
    "unable_to_drink": ["पी नहीं पा", "पानी नहीं पी", "दूध नहीं पी"],
    "vomits_everything": ["सब उल्टी", "सब कुछ उल्टी", "हर चीज़ उल्टी", "उल्टी कर देता", "उल्टी कर देती"],
    "stiff_neck": ["गर्दन अकड़", "गर्दन जकड़", "गर्दन में अकड़न"],
    "fast_breathing": ["तेज़ साँस", "तेज साँस", "तेज़ सांस", "तेज सांस", "जल्दी जल्दी साँस", "जल्दी जल्दी सांस"],
    "blood_in_stool": ["खून", "ख़ून", "blood"],
    "dehydration_signs": ["आँखें धँस", "आंखें धंस", "पेशाब कम", "पेशाब नहीं"],
}
NEGATIONS = ["नहीं", "नही", "ना ", "nahi", "no "]
HINDI_NUMBERS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6,
    "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "पंद्रह": 15, "बीस": 20,
}


def _days_near(text: str, start: int) -> int | None:
    window = text[max(0, start - 40): start + 60]
    m = re.search(r"(\d+)\s*(दिन|din|day)", window)
    if m:
        return int(m.group(1))
    week = r"\s*(हफ़्ते|हफ्ते|हफ़्ता|हफ्ता|सप्ताह)"
    m = re.search(r"(\d+)" + week, window)
    if m:
        return int(m.group(1)) * 7
    for word, n in HINDI_NUMBERS.items():
        if re.search(r"(?<!\w)" + word + week, window):
            return n * 7
    for word, n in HINDI_NUMBERS.items():
        if re.search(r"(?<!\w)" + word + r"\s*(दिन|din)", window):
            return n
    if re.search(week, window):
        return 7
    return None


class KeywordExtractor:
    name = "keyword"

    def __call__(self, transcript: str) -> dict:
        out = empty_result()
        text = unicodedata.normalize("NFC", transcript).lower()
        for item, words in KEYWORDS.items():
            for w in words:
                i = text.find(w.lower())
                if i < 0:
                    continue
                after = text[i + len(w): i + len(w) + 15]
                value = NO if any(n in after for n in NEGATIONS) else YES
                if item in SYMPTOMS:
                    out["symptoms"][item]["present"] = value
                    if value == YES:
                        out["symptoms"][item]["days"] = _days_near(text, i)
                else:
                    out["flags"][item] = value
                break
        return out


def get_extractor(kind: str | None = None):
    kind = kind or os.environ.get("VB_EXTRACTOR", "llm")
    return KeywordExtractor() if kind == "keyword" else LLMExtractor()
