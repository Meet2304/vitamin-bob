"""Hear the questionnaire on this laptop: speakers stand in for the call, the keyboard for the keypad.

    python tools/try_questionnaire.py              # play the generated prompt audio
    python tools/try_questionnaire.py --text       # no audio, print what Bob would say

It runs the real triage logic (CallSession + rules) with the same clips the phone call will use,
so it proves the concept end to end before Stuart, the dashboard or the model exist:
language menu -> who is sick -> describe (typed here; spoken + Gemma on the real call)
-> only the follow-up questions still needed -> tier -> outcome with clinic, time and case code.

Keys: press digits as on a phone keypad (1 yes, 2 no, 3 don't know; '#' ends a number).
"""

import argparse
import msvcrt
import secrets
import sys
import time
import winsound
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vitamin_bob.extract import KeywordExtractor  # noqa: E402
from vitamin_bob.prompts import (  # noqa: E402
    SYSTEM, catalog, clip_path, lang_for_key, languages, outcome_keys, question_keys, text_of,
)
from vitamin_bob.protocol import AGE_GROUPS  # noqa: E402
from vitamin_bob.session import CallSession  # noqa: E402

KEY_TIMEOUT_S = 8
TEXT_ONLY = False


def say(lang: str, keys: list[str]) -> None:
    """Play a clip list, exactly as Bob will send it to Stuart as `play` actions."""
    for key in keys:
        path = clip_path(lang, key)
        words = "(bilingual clip)" if lang == SYSTEM else catalog(lang).get(key, "")
        print(f"  BOB ▶ {lang}/{key:28} {words}")
        if TEXT_ONLY:
            continue
        if path.exists():
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
        else:
            print(f"        (missing {path}; run tools/gen_prompts.py)")


def read_keys(max_digits: int = 1, terminator: str | None = None) -> str | None:
    """Collect keypad presses like Stuart's `keypad` action. None means timeout with no input."""
    buf, deadline = "", time.time() + KEY_TIMEOUT_S
    while time.time() < deadline:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in "0123456789*#":
                deadline = time.time() + KEY_TIMEOUT_S
                if terminator and ch == terminator:
                    print(f"  YOU ⌨ {buf}{ch}")
                    return buf + ch
                buf += ch
                if not terminator and len(buf) >= max_digits:
                    print(f"  YOU ⌨ {buf}")
                    return buf
        time.sleep(0.02)
    if buf:
        print(f"  YOU ⌨ {buf} (timeout)")
    return buf or None


def ask(lang: str, keys: list[str], valid: set[str], tries: int = 3) -> str | None:
    """Ask, re-asking on no input or a wrong key. Returns None if the caller never answers."""
    for _ in range(tries):
        say(lang, keys)
        got = read_keys()
        if got in valid:
            return got
        say(lang, ["invalid_key"] if got else ["no_input"])
    return None


def main() -> int:
    global TEXT_ONLY
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="store_true", help="print prompts instead of playing audio")
    TEXT_ONLY = ap.parse_args().text
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    print("\n=== Vitamin Bob: questionnaire on the laptop (keyboard = keypad) ===\n")

    # 1. Bilingual language menu. Repeats until a key is pressed, because Stuart cannot tell
    #    exactly when the patient picked up and the first seconds may be missed.
    lang = None
    menu_keys = {lang["menu_key"] for lang in languages()}
    for _ in range(5):
        say(SYSTEM, ["lang_menu"])
        got = read_keys()
        if got in menu_keys:
            lang = lang_for_key(got)
            break
    if lang is None:
        say(SYSTEM, ["fallback"])
        print("\nNo language chosen: on the real call this ends as UNCERTAIN with a clinician alert.")
        return 0

    session = CallSession(KeywordExtractor())
    session.code = f"{secrets.randbelow(10000):04d}"  # digits only: read back from digit clips
    say(lang, ["welcome"])

    # 2. Who is sick.
    age = ask(lang, ["who_is_sick"], set(AGE_GROUPS))
    if age is None:
        say(lang, ["fallback"])
        return 0
    session.set_age(age)

    # 3. Describe. On the real call: `listen` up to 25 s, then Gemma transcribes and fills the form.
    say(lang, ["describe"])
    say(SYSTEM, ["beep"])
    print("\n  (Stand-in for speech: type what the patient says, then Enter.")
    print("   The keyword baseline here understands Hindi only; Enter alone skips.)")
    transcript = input("  PATIENT 🗣 ").strip()
    say(lang, ["please_wait"])
    session.describe(transcript)
    understood = [k for k, v in session.case.source.items() if v == "description"]
    print(f"\n  understood from the description: {', '.join(understood) or 'nothing'}\n")

    # 4. Only the follow-up questions still needed.
    while (q := session.next_question()) is not None:
        if q.kind == "days":
            say(lang, question_keys(q.qid))
            got = read_keys(max_digits=3, terminator="#") or "#"
        else:
            got = ask(lang, question_keys(q.qid), {"1", "2", "3"}) or "3"  # silence = don't know
        session.answer(q, got)

    # 5. Tier and outcome. Clinic and slot are fixed here; routing and booking come with bob.db.
    out = session.finish()
    from vitamin_bob.protocol import Tier  # noqa: PLC0415
    tier = Tier[out["tier"]]
    keys = outcome_keys(tier, clinic_id="rampur", day="tomorrow", hour=10, code=session.code)
    print()
    say(lang, keys)

    print("\n=== Result ===")
    print(f"  Tier: {out['tier']}    keypad questions: {out['questions_asked']}    case: {session.code}")
    for r in out["reasons"]:
        print(f"   - {r}")
    print(f"  Alert a clinician: {'YES' if out['alert_clinician'] else 'no'}")
    print(f"  Patient heard: {text_of(lang, keys)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n(caller hung up) On the real call this ends as UNCERTAIN with a clinician alert.")
        sys.exit(0)
