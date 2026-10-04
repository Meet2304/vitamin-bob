"""One call, start to finish. The CLI, the eval harness and (later) the Gradio demo all drive
this same state machine, so what you evaluate is exactly what you demo.

Flow: age (keypad) -> free description (speech -> text -> extractor)
      -> only the follow-up questions still needed (keypad) -> tier -> messages.
"""

import secrets
from dataclasses import dataclass

from .protocol import (
    AGE_GROUPS,
    AGE_LABEL_EN,
    OUTCOME_HI,
    PATIENT_SMS_HI,
    PROMPTS_HI,
    RED_FLAG_QUESTION_HI,
    RED_FLAGS,
    SYMPTOM_HI,
    SYMPTOM_LABEL_EN,
    SYMPTOM_QUESTION_HI,
    SYMPTOMS,
    Tier,
    applicable_red_flags,
    flag_tier,
)
from .rules import NO, UNKNOWN, YES, Case, Classification, classify

KEY_TO_ANSWER = {"1": YES, "2": NO, "3": UNKNOWN}


@dataclass
class Question:
    qid: str  # "symptom:fever", "days:cough", "flag:stiff_neck"
    text_hi: str
    kind: str  # "yes_no" or "days"


class CallSession:
    def __init__(self, extractor, phone: str = "+91XXXXXXXXXX"):
        self.extractor = extractor
        self.phone = phone
        self.case = Case()
        self.code = secrets.token_hex(2).upper()
        self.asked: set[str] = set()
        self.log: list[tuple[str, str]] = []  # (speaker, text) for the demo's Bob log
        self.extraction: dict | None = None

    # -- step 1 ------------------------------------------------------------
    def opening(self) -> list[str]:
        return [PROMPTS_HI["welcome"], PROMPTS_HI["age"]]

    def set_age(self, key: str) -> bool:
        if key not in AGE_GROUPS:
            return False
        self.case.age_group = AGE_GROUPS[key]
        self.log.append(("patient", f"[keypad {key}] {AGE_LABEL_EN[self.case.age_group]}"))
        return True

    # -- step 2 ------------------------------------------------------------
    def describe(self, transcript: str) -> dict:
        self.case.transcript = transcript
        self.log.append(("patient", transcript))
        result = self.extractor(transcript)
        self.extraction = result
        for s in SYMPTOMS:
            if result["symptoms"][s]["present"] != UNKNOWN:
                self.case.symptoms[s] = dict(result["symptoms"][s])
                self.case.source[s] = "description"
        confirm = []
        for f in RED_FLAGS:
            value = result["flags"][f]
            if value == UNKNOWN:
                continue
            # Guardrail: the description may RAISE urgency, never silently lower it.
            # A "no" on an emergency-level sign is left unknown so the patient confirms it.
            if value == NO and flag_tier(f, self.case.age_group) >= Tier.EMERGENCY:
                confirm.append(f)
                continue
            self.case.flags[f] = value
            self.case.source[f] = "description"
        if confirm:
            self.log.append(("bob", f"[will confirm on keypad] {', '.join(confirm)}"))
        understood = [k for k, v in self.case.source.items() if v == "description"]
        self.log.append(("bob", f"[understood from description] {', '.join(understood) or 'nothing'}"))
        if result["rejected"]:
            self.log.append(("bob", f"[dropped, no evidence in transcript] {', '.join(result['rejected'])}"))
        return result

    # -- step 3 ------------------------------------------------------------
    def next_question(self) -> Question | None:
        current = classify(self.case).tier
        if current == Tier.EMERGENCY:
            return None  # don't keep an emergency caller on the line

        present = self.case.present_symptoms()

        if current < Tier.HIGH:
            for s in SYMPTOMS:
                qid = f"symptom:{s}"
                if self.case.symptoms[s]["present"] == UNKNOWN and qid not in self.asked:
                    return Question(qid, f"{SYMPTOM_QUESTION_HI[s]} {PROMPTS_HI['yes_no_hint']}", "yes_no")
            for s in SYMPTOMS:
                qid = f"days:{s}"
                if s in present and self.case.symptoms[s]["days"] is None and qid not in self.asked:
                    return Question(qid, PROMPTS_HI["days"].format(symptom=SYMPTOM_HI[s]), "days")

        possibly = present | {s for s in SYMPTOMS if self.case.symptoms[s]["present"] == UNKNOWN}
        for f in applicable_red_flags(self.case.age_group, possibly):
            qid = f"flag:{f}"
            if self.case.flags[f] != UNKNOWN or qid in self.asked:
                continue
            # Once HIGH is established, only ask what could still make it an EMERGENCY.
            if current >= Tier.HIGH and flag_tier(f, self.case.age_group) < Tier.EMERGENCY:
                continue
            return Question(qid, f"{RED_FLAG_QUESTION_HI[f]} {PROMPTS_HI['yes_no_hint']}", "yes_no")
        return None

    def answer(self, q: Question, key: str) -> None:
        self.asked.add(q.qid)
        kind, item = q.qid.split(":", 1)
        key = key.strip()
        self.log.append(("patient", f"[keypad {key}] {q.qid}"))
        if kind == "days":
            digits = key.rstrip("#")
            if digits.isdigit() and 0 < int(digits) < 365:
                self.case.symptoms[item]["days"] = int(digits)
            self.case.source[f"{item}_days"] = "keypad"
            return
        value = KEY_TO_ANSWER.get(key, UNKNOWN)
        if kind == "symptom":
            self.case.symptoms[item]["present"] = value
        else:
            self.case.flags[item] = value
        self.case.source[item] = "keypad"

    # -- step 4 ------------------------------------------------------------
    def finish(self, clinic: str = "PHC Rampur", time: str = "कल सुबह 10 बजे") -> dict:
        result: Classification = classify(self.case)
        patient_msg = OUTCOME_HI[result.tier].format(clinic=clinic, time=time, code=self.code)
        out = {
            "code": self.code,
            "tier": result.tier.name,
            "reasons": result.reasons,
            "unknowns": result.unknowns,
            "patient_message_hi": patient_msg,
            "patient_sms_hi": None
            if result.tier == Tier.EMERGENCY
            else PATIENT_SMS_HI.format(code=self.code, clinic=clinic, time="अभी" if result.tier >= Tier.UNCERTAIN else time),
            "clinician_sms": clinician_sms(self, result),
            "alert_clinician": result.tier >= Tier.UNCERTAIN,
            "questions_asked": len(self.asked),
        }
        self.log.append(("bob", f"[{out['tier']}] {patient_msg}"))
        return out


def clinician_sms(session: CallSession, result: Classification) -> str:
    """Fixed template, never generated. Kept under 160 characters (one SMS)."""
    c = session.case
    parts = [f"VB {session.code} {result.tier.name}", AGE_LABEL_EN.get(c.age_group, "Age?")]
    syms = []
    for s in SYMPTOMS:
        v = c.symptoms[s]
        if v["present"] == YES:
            syms.append(SYMPTOM_LABEL_EN[s] + (f" {v['days']}d" if v["days"] else " ?d"))
    if syms:
        parts.append(",".join(syms))
    red = [RED_FLAGS[f]["en"] for f, v in c.flags.items() if v == YES]
    if red:
        parts.append("RED:" + ",".join(red))
    if result.unknowns:
        parts.append("UNSURE:" + ",".join(result.unknowns))
    parts.append(f"Call {session.phone}")
    sms = " | ".join(parts)
    if len(sms) > 160:
        tail = f" | Call {session.phone}"
        sms = sms[: 160 - len(tail) - 1] + "~" + tail
    return sms
