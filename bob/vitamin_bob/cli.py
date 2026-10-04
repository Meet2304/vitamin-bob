"""Text-only end-to-end call, for testing the brain before voice and UI exist.

    python -m vitamin_bob.cli                    # LLM extractor (needs Ollama running)
    python -m vitamin_bob.cli --extractor keyword
"""

import argparse

from .extract import get_extractor
from .session import CallSession


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", choices=["llm", "keyword"], default=None)
    args = ap.parse_args()

    s = CallSession(get_extractor(args.extractor))
    for line in s.opening():
        print(f"BOB: {line}")
    while not s.set_age(input("[keypad] > ").strip()):
        print("BOB: 1, 2 या 3 दबाएँ।")

    print("BOB: बीप के बाद अपनी तकलीफ़ बताइए।")
    s.describe(input("[describe, Hindi] > "))
    print(f"  (understood: {s.extraction['symptoms']} | flags: "
          f"{ {k: v for k, v in s.extraction['flags'].items() if v != 'unknown'} })")

    while (q := s.next_question()) is not None:
        print(f"BOB: {q.text_hi}")
        s.answer(q, input("[keypad] > "))

    out = s.finish()
    print("\n===== RESULT =====")
    print(f"Tier: {out['tier']}   (questions asked: {out['questions_asked']})")
    for r in out["reasons"]:
        print(f"  - {r}")
    print(f"\nBOB says: {out['patient_message_hi']}")
    print(f"Patient SMS: {out['patient_sms_hi']}")
    print(f"Clinician SMS ({len(out['clinician_sms'])} chars): {out['clinician_sms']}")


if __name__ == "__main__":
    main()
