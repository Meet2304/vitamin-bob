"""Generate Bob's prompt audio BEFORE the demo. This is the only step that uses the internet;
at runtime Bob just plays the files, nothing is synthesised during a call.

    python tools/gen_prompts.py --dry-run          # list what would be generated, with character counts
    python tools/gen_prompts.py --placeholder      # tones instead of speech: tests the pipeline offline
    python tools/gen_prompts.py                    # generate missing or changed clips with Sarvam
    python tools/gen_prompts.py --lang gu --only welcome --speaker ritu --force   # audition a voice

Needs SARVAM_API_KEY in bob/.env (see .env.example). Output: <VB_DATA_DIR>/prompts/<lang>/<key>.wav,
16 kHz mono 16-bit (contract 7.1), plus system/lang_menu.wav, system/fallback.wav, system/beep.wav.

A clip is regenerated only when its text, voice or settings change (tracked in manifest.json),
so re-running costs nothing and editing one sentence re-synthesises one clip.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vitamin_bob import audio  # noqa: E402
from vitamin_bob.prompts import (  # noqa: E402
    BOB_DIR, SYSTEM, catalog, clip_path, config, languages, prompts_dir, validate_catalogs,
)

SARVAM_URL = "https://api.sarvam.ai/text-to-speech"


def load_env(path: Path) -> None:
    """Minimal .env reader (KEY=value lines), so no extra dependency is needed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def sarvam_tts(text: str, lang_tts: dict, tts: dict, key: str) -> bytes:
    body = {
        "text": text,
        "language_code": lang_tts["language_code"],
        "speaker": lang_tts["speaker"],
        "model": tts["model"],
        "pace": tts["pace"],
        "speech_sample_rate": audio.RATE,
    }
    req = urllib.request.Request(
        SARVAM_URL,
        data=json.dumps(body).encode(),
        headers={"api-subscription-key": key, "Content-Type": "application/json"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                clips = json.load(resp)["audios"]
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Sarvam HTTP {e.code}: {detail}") from None
    # Long texts may come back in several chunks; join them in order.
    samples = audio.silence(0)
    for c in clips:
        samples += audio.to_contract(base64.b64decode(c), pad_ms=0)
    return samples + audio.silence(150)


def placeholder(text: str, lang_index: int):
    """A tone roughly as long as the sentence would be, so timings in the demo feel realistic."""
    ms = max(300, min(8000, 70 * len(text)))
    return audio.tone(440 + 110 * lang_index, ms, volume=0.15) + audio.silence(150)


def signature(provider: str, text: str, lang_tts: dict, tts: dict) -> str:
    raw = json.dumps([provider, text, lang_tts, tts], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def build_system_clips(langs: list[dict]) -> list[str]:
    """Language-neutral clips assembled from per-language ones (no API calls)."""
    sysdir = prompts_dir() / SYSTEM
    made = []
    # Bilingual menu: every enabled language offers itself in its own voice. Stuart plays it, then
    # Bob asks for one key; the conversation repeats it until a key is pressed.
    menu = [clip_path(lang["code"], "lang_select") for lang in langs]
    if all(p.exists() for p in menu):
        audio.write(sysdir / "lang_menu.wav", audio.concat(menu, gap_ms=400))
        made.append("lang_menu")
    # Contract 7.3: Stuart plays this if Bob is unreachable, then hangs up.
    fallback = [clip_path(lang["code"], "fallback") for lang in langs]
    if all(p.exists() for p in fallback):
        audio.write(sysdir / "fallback.wav", audio.concat(fallback, gap_ms=400))
        made.append("fallback")
    # The beep before `listen`: synthesised locally, no API needed.
    audio.write(sysdir / "beep.wav", audio.silence(150) + audio.tone(1000, 350) + audio.silence(100))
    made.append("beep")
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", help="only this language code (default: all enabled)")
    ap.add_argument("--only", nargs="+", metavar="KEY", help="only these clip keys")
    ap.add_argument("--speaker", help="override the voice for this run (audition)")
    ap.add_argument("--force", action="store_true", help="regenerate even if unchanged")
    ap.add_argument("--dry-run", action="store_true", help="show what would be generated; no API calls")
    ap.add_argument("--placeholder", action="store_true", help="write tones instead of speech (offline)")
    args = ap.parse_args()

    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    problems = validate_catalogs()
    if problems:
        print("Catalogue problems (fix before generating):")
        for p in problems:
            print(f"  - {p}")
        return 1

    load_env(BOB_DIR / ".env")
    api_key = os.environ.get("SARVAM_API_KEY", "")
    provider = "placeholder" if args.placeholder else config()["tts"]["provider"]
    if provider == "sarvam" and not (api_key or args.dry_run):
        print("SARVAM_API_KEY is not set. Add it to bob/.env (see bob/.env.example),")
        print("or run with --placeholder to test the pipeline without speech.")
        return 1

    tts = {k: v for k, v in config()["tts"].items() if k != "provider"}
    all_langs = languages()
    langs = [lang for lang in all_langs if not args.lang or lang["code"] == args.lang]
    manifest_path = prompts_dir() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    made = skipped = chars = 0
    failed = []
    for li, lang in enumerate(langs):
        lang_tts = dict(lang["tts"], **({"speaker": args.speaker} if args.speaker else {}))
        for key, text in catalog(lang["code"]).items():
            if args.only and key not in args.only:
                continue
            target = clip_path(lang["code"], key)
            sig = signature(provider, text, lang_tts, tts)
            mkey = f"{lang['code']}/{key}"
            if target.exists() and manifest.get(mkey, {}).get("sig") == sig and not args.force:
                skipped += 1
                continue
            chars += len(text)
            if args.dry_run:
                print(f"  would generate {mkey:32} {len(text):4} chars  {text[:60]}")
                made += 1
                continue
            try:
                samples = (placeholder(text, li) if provider == "placeholder"
                           else sarvam_tts(text, lang_tts, tts, api_key))
            except Exception as e:  # noqa: BLE001 - keep going, report all failures at the end
                failed.append(f"{mkey}: {e}")
                print(f"  FAILED {mkey}: {e}")
                continue
            audio.write(target, samples)
            manifest[mkey] = {"sig": sig, "provider": provider, "speaker": lang_tts["speaker"], "text": text}
            made += 1
            print(f"  {mkey:32} {len(samples) / audio.RATE:5.1f}s  {text[:50]}")

    if not args.dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        system = build_system_clips(all_langs)
        bad = [f"{p.relative_to(prompts_dir())}: {err}"
               for p in sorted(prompts_dir().rglob("*.wav")) if (err := audio.check(p))]
        print(f"\nSystem clips: {', '.join(system)}")
        print(f"Format check (16 kHz mono 16-bit): {'all OK' if not bad else bad}")

    verb = "Would generate" if args.dry_run else "Generated"
    print(f"\n{verb} {made} clip(s) ({chars} characters via {provider}); {skipped} unchanged, skipped.")
    print(f"Output: {prompts_dir()}")
    if failed:
        print(f"{len(failed)} failure(s); re-run to retry only those.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
