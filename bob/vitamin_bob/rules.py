"""Deterministic urgency rules. No model is involved here: given the filled-in case, the tier
is fully explainable, and every 'unknown' on a question that matters forces UNCERTAIN.
"""

from dataclasses import dataclass, field

from .protocol import (
    HIGH_DURATION_DAYS,
    MEDIUM_DURATION_DAYS,
    RED_FLAGS,
    SYMPTOMS,
    SYMPTOM_LABEL_EN,
    Tier,
    applicable_red_flags,
    flag_tier,
)

YES, NO, UNKNOWN = "yes", "no", "unknown"


@dataclass
class Case:
    """Everything Bob knows about one call. Values are 'yes' / 'no' / 'unknown'."""

    age_group: str | None = None
    symptoms: dict = field(
        default_factory=lambda: {s: {"present": UNKNOWN, "days": None} for s in SYMPTOMS}
    )
    flags: dict = field(default_factory=lambda: {f: UNKNOWN for f in RED_FLAGS})
    transcript: str = ""
    # Where each value came from: "description" (AI extraction) or "keypad" (patient answer).
    source: dict = field(default_factory=dict)

    def present_symptoms(self) -> set[str]:
        return {s for s, v in self.symptoms.items() if v["present"] == YES}


@dataclass
class Classification:
    tier: Tier
    reasons: list[str]
    unknowns: list[str]


def classify(case: Case) -> Classification:
    reasons: list[str] = []
    tier = Tier.LOW
    present = case.present_symptoms()

    # 1. Red flags the patient confirmed. These win regardless of anything unknown.
    for flag, value in case.flags.items():
        if value == YES:
            t = flag_tier(flag, case.age_group)
            tier = max(tier, t)
            reasons.append(f"{RED_FLAGS[flag]['en']} ({t.name})")

    # 2. A young infant with fever is always an emergency referral (IMCI young-infant rule).
    if case.age_group == "infant_under_2m" and "fever" in present:
        tier = max(tier, Tier.EMERGENCY)
        reasons.append("Fever in infant under 2 months (EMERGENCY)")

    # 3. Long-running symptoms.
    for s in present:
        days = case.symptoms[s]["days"]
        if days is not None and days >= HIGH_DURATION_DAYS[s]:
            tier = max(tier, Tier.HIGH)
            reasons.append(f"{SYMPTOM_LABEL_EN[s]} for {days} days (HIGH)")

    if tier >= Tier.HIGH:
        return Classification(tier, reasons, unknowns=_unknowns(case, present))

    # 4. Anything that could still hide a HIGH or EMERGENCY means a human decides.
    unknowns = _unknowns(case, present)
    if unknowns:
        reasons.append("Not sure about: " + ", ".join(unknowns))
        return Classification(Tier.UNCERTAIN, reasons, unknowns)

    if not present:
        # Nothing in scope (fever, cough, diarrhoea) was described. Out of scope -> a person decides.
        reasons.append("No fever, cough or diarrhea reported; outside Bob's scope")
        return Classification(Tier.UNCERTAIN, reasons, ["scope"])

    # 5. Routine cases.
    for s in present:
        days = case.symptoms[s]["days"]
        if days is not None and days >= MEDIUM_DURATION_DAYS[s]:
            tier = max(tier, Tier.MEDIUM)
            reasons.append(f"{SYMPTOM_LABEL_EN[s]} for {days} days (MEDIUM)")
    if case.age_group == "child_under_5" and "fever" in present:
        tier = max(tier, Tier.MEDIUM)
        reasons.append("Fever in child under 5 (MEDIUM)")

    if tier == Tier.LOW:
        reasons.append("Recent, mild, no red flags (LOW)")
    return Classification(tier, reasons, [])


def _unknowns(case: Case, present: set[str]) -> list[str]:
    """Questions whose answer is still unknown but could change the tier upward."""
    out = []
    if case.age_group is None:
        out.append("age group")
    for s, v in case.symptoms.items():
        if v["present"] == UNKNOWN:
            out.append(f"{s} present")
        elif v["present"] == YES and v["days"] is None:
            out.append(f"{s} duration")
    # Symptoms that might be present still make their flags relevant.
    possibly_present = present | {s for s, v in case.symptoms.items() if v["present"] == UNKNOWN}
    for flag in applicable_red_flags(case.age_group, possibly_present):
        if case.flags[flag] == UNKNOWN:
            out.append(flag)
    return out
