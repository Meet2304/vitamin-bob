"""The fixed clinical protocol: symptoms, red flags, the questions Bob asks, and urgency tiers.

Everything here is deterministic and reviewable. The AI never invents a question or a tier;
it only fills in which of these flags the patient has already described.

DRAFT CONTENT: adapted from WHO IMCI general danger signs and common referral criteria for
fever, cough and diarrhoea. It must be reviewed by a clinician before any real use.
"""

from enum import IntEnum


class Tier(IntEnum):
    # Ordered by severity so max() picks the most urgent.
    LOW = 0
    MEDIUM = 1
    UNCERTAIN = 2
    HIGH = 3
    EMERGENCY = 4


# Keypad choice -> age group. Asked first, because red flags and thresholds depend on age.
AGE_GROUPS = {
    "1": "infant_under_2m",
    "2": "child_under_5",
    "3": "older_child_or_adult",
}
AGE_LABEL_EN = {
    "infant_under_2m": "Infant <2m",
    "child_under_5": "Child <5",
    "older_child_or_adult": "Adult/older child",
}

SYMPTOMS = ["fever", "cough", "diarrhea"]
SYMPTOM_LABEL_EN = {"fever": "Fever", "cough": "Cough", "diarrhea": "Diarrhea"}

# Red flags. `applies_to` is "any" or the symptom that makes the question relevant.
# `tier` is the tier the flag triggers; `tier_by_age` overrides it for specific age groups.
RED_FLAGS = {
    "convulsions": {
        "en": "Fits or convulsions",
        "applies_to": "any",
        "tier": Tier.EMERGENCY,
    },
    "altered_consciousness": {
        "en": "Unconscious, very drowsy or confused",
        "applies_to": "any",
        "tier": Tier.EMERGENCY,
    },
    "severe_breathing_difficulty": {
        "en": "Struggling to breathe",
        "applies_to": "any",
        "tier": Tier.EMERGENCY,
    },
    "unable_to_drink": {
        "en": "Cannot drink or breastfeed",
        "applies_to": "any",
        "tier": Tier.HIGH,
        "tier_by_age": {"infant_under_2m": Tier.EMERGENCY, "child_under_5": Tier.EMERGENCY},
    },
    "vomits_everything": {
        "en": "Vomits everything",
        "applies_to": "any",
        "tier": Tier.HIGH,
        "tier_by_age": {"infant_under_2m": Tier.EMERGENCY, "child_under_5": Tier.EMERGENCY},
    },
    "stiff_neck": {
        "en": "Stiff neck",
        "applies_to": "fever",
        "tier": Tier.HIGH,
    },
    "fast_breathing": {
        "en": "Fast breathing",
        "applies_to": "cough",
        "tier": Tier.HIGH,
    },
    "blood_in_stool": {
        "en": "Blood in stool",
        "applies_to": "diarrhea",
        "tier": Tier.HIGH,
    },
    "dehydration_signs": {
        "en": "Sunken eyes or very little urine",
        "applies_to": "diarrhea",
        "tier": Tier.HIGH,
    },
}

# Durations (days) at or above which a symptom alone becomes HIGH.
HIGH_DURATION_DAYS = {"fever": 7, "cough": 14, "diarrhea": 14}
# Durations at or above which a symptom alone becomes MEDIUM.
MEDIUM_DURATION_DAYS = {"fever": 2, "cough": 7, "diarrhea": 3}


# ---------------------------------------------------------------------------
# What Bob says. Fixed Hindi prompts, recorded once as audio. Never generated.
# Keypad convention for every yes/no question: 1 = haan, 2 = nahin, 3 = pata nahin.
# ---------------------------------------------------------------------------
PROMPTS_HI = {
    "welcome": "नमस्ते, मैं विटामिन बॉब हूँ। मैं आपको सही क्लिनिक तक पहुँचाने में मदद करूँगा। मैं डॉक्टर नहीं हूँ।",
    "age": "कौन बीमार है? दो महीने से छोटे बच्चे के लिए 1 दबाएँ, पाँच साल से छोटे बच्चे के लिए 2, और बड़े बच्चे या वयस्क के लिए 3 दबाएँ।",
    "describe": "बीप के बाद अपनी तकलीफ़ अपने शब्दों में बताइए। जैसे बुखार, खाँसी या दस्त, और कितने दिनों से है।",
    "yes_no_hint": "हाँ के लिए 1, नहीं के लिए 2, और पता नहीं के लिए 3 दबाएँ।",
    "days": "{symptom} कितने दिनों से है? दिनों की संख्या दबाएँ, फिर हैश दबाएँ। पता नहीं हो तो सिर्फ़ हैश दबाएँ।",
}

SYMPTOM_HI = {"fever": "बुखार", "cough": "खाँसी", "diarrhea": "दस्त"}

# Asked only when the symptom's presence was not clear from the description.
SYMPTOM_QUESTION_HI = {
    "fever": "क्या मरीज़ को बुखार है?",
    "cough": "क्या मरीज़ को खाँसी है?",
    "diarrhea": "क्या मरीज़ को दस्त हो रहे हैं?",
}

RED_FLAG_QUESTION_HI = {
    "convulsions": "क्या मरीज़ को दौरे या झटके आए हैं?",
    "altered_consciousness": "क्या मरीज़ बहुत सुस्त है, बेहोश है, या उलझन में है?",
    "severe_breathing_difficulty": "क्या मरीज़ को साँस लेने में बहुत तकलीफ़ हो रही है?",
    "unable_to_drink": "क्या मरीज़ कुछ भी पी नहीं पा रहा है, या बच्चा दूध नहीं पी पा रहा है?",
    "vomits_everything": "क्या मरीज़ जो भी खाता या पीता है, सब उल्टी कर देता है?",
    "stiff_neck": "क्या मरीज़ की गर्दन अकड़ी हुई है?",
    "fast_breathing": "क्या मरीज़ की साँस सामान्य से तेज़ चल रही है?",
    "blood_in_stool": "क्या दस्त में खून आ रहा है?",
    "dehydration_signs": "क्या मरीज़ की आँखें धँसी हुई हैं, या पेशाब बहुत कम आ रहा है?",
}

# What the patient hears at the end. {clinic}, {time}, {code} are filled from the queue.
OUTCOME_HI = {
    Tier.EMERGENCY: "यह आपातकाल हो सकता है। अभी 108 पर कॉल करें। डॉक्टर को आपकी जानकारी भेज दी गई है।",
    Tier.HIGH: "कृपया अभी {clinic} जाएँ। डॉक्टर को आपकी जानकारी भेज दी गई है, वे आपको कॉल करेंगे। केस नंबर {code}।",
    Tier.UNCERTAIN: "मुझे पक्का पता नहीं है, इसलिए एक डॉक्टर फ़ैसला करेंगे। कृपया अभी {clinic} जाएँ, डॉक्टर आपको कॉल करेंगे। केस नंबर {code}।",
    Tier.MEDIUM: "आपका समय {time}, {clinic} में है। केस नंबर {code}। हालत बिगड़े तो दोबारा मिस्ड कॉल दें।",
    Tier.LOW: "आपका समय {time}, {clinic} में है। केस नंबर {code}। हालत बिगड़े तो दोबारा मिस्ड कॉल दें।",
}

# Patient SMS: no symptoms, because the household phone may be shared.
PATIENT_SMS_HI = "विटामिन बॉब: केस {code}। {clinic}, {time}।"


def applicable_red_flags(age_group: str, present_symptoms: set[str]) -> list[str]:
    """Red flags worth asking about, given age and which symptoms are present.

    Universal flags ("any") are always asked. Emergency flags come first.
    """
    flags = [
        name
        for name, f in RED_FLAGS.items()
        if f["applies_to"] == "any" or f["applies_to"] in present_symptoms
    ]
    return sorted(flags, key=lambda n: -flag_tier(n, age_group))


def flag_tier(flag: str, age_group: str) -> Tier:
    f = RED_FLAGS[flag]
    return f.get("tier_by_age", {}).get(age_group, f["tier"])
