"""One call, start to finish. The CLI, the eval harness and the contract conversation
(conversation.py) all drive this same state machine, so what you evaluate is exactly what you demo.

Flow: age (keypad) -> free description (speech -> text -> extractor)
      -> only the follow-up questions still needed (keypad) -> tier -> messages.
"""

import secrets
from dataclasses import dataclass

from .protocol import (
    AGE_GROUPS,
    HIGH_DURATION_DAYS,
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
        # Digits only, so it can be read back from pre-recorded digit clips and typed on any keypad.
        self.code = f"{secrets.randbelow(10000):04d}"
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
        return self.apply(transcript, self.extractor(transcript))

    def apply(self, transcript: str, result: dict) -> dict:
        """Merge an extraction (from any extractor, including Gemma on audio) into the case."""
        self.case.transcript = transcript
        self.log.append(("patient", transcript))
        self.extraction = result
        confirm_days = []
        for s in SYMPTOMS:
            if result["symptoms"][s]["present"] != UNKNOWN:
                self.case.symptoms[s] = dict(result["symptoms"][s])
                self.case.source[s] = "description"
                days = self.case.symptoms[s]["days"]
                # Guardrail: a duration heard in the description may RAISE urgency (long enough
                # to be HIGH on its own) but never silently lower it. "17 days" misheard as
                # "7 days" would turn HIGH into MEDIUM, so shorter durations are confirmed on the keypad.
                if days is not None and days < HIGH_DURATION_DAYS[s]:
                    self.case.symptoms[s]["days"] = None
                    confirm_days.append(f"{s} {days}d")
                elif days is not None:
                    self.case.source[f"{s}_days"] = "description"
        if confirm_days:
            self.log.append(("bob", f"[will confirm duration on keypad] {', '.join(confirm_days)}"))
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


def session_to_dict(s: CallSession) -> dict:
    """Everything needed to resume a call between contract events."""
    c = s.case
    return {
        "phone": s.phone, "code": s.code, "asked": sorted(s.asked), "log": s.log,
        "extraction": s.extraction,
        "case": {"age_group": c.age_group, "symptoms": c.symptoms, "flags": c.flags,
                 "transcript": c.transcript, "source": c.source},
    }


def session_from_dict(d: dict, extractor=None) -> CallSession:
    s = CallSession(extractor, phone=d["phone"])
    s.code, s.asked, s.extraction = d["code"], set(d["asked"]), d["extraction"]
    s.log = [tuple(x) for x in d["log"]]
    c = d["case"]
    s.case = Case(age_group=c["age_group"], symptoms=c["symptoms"], flags=c["flags"],
                  transcript=c["transcript"], source=c["source"])
    return s
