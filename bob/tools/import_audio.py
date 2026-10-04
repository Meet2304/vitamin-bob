"""Convert patient recordings (m4a, mp3, ogg, wav, ...) to the contract format for tests and eval.

    python tools/import_audio.py                       # data/Patient/<lang>/* -> data/eval_audio/<lang>/<name>.wav
    python tools/import_audio.py --phone               # also simulate a narrowband phone line (8 kHz)

Output is WAV, 16 kHz, mono, 16-bit, trimmed to 25 s (the longest `listen` in the contract).
Uses PyAV (bundles its own decoder), so ffmpeg does not need to be installed. Needs: pip install av
"""

import argparse
import array
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vitamin_bob import audio  # noqa: E402
from vitamin_bob.prompts import data_dir  # noqa: E402

MAX_S = 25


def decode(path: Path, rate: int) -> array.array:
    import av  # noqa: PLC0415

    out = array.array("h")
    with av.open(str(path)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
        for frame in container.decode(audio=0):
            for f in resampler.resample(frame):
                out.frombytes(bytes(f.planes[0])[: f.samples * 2])
        for f in resampler.resample(None):
            out.frombytes(bytes(f.planes[0])[: f.samples * 2])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(data_dir() / "Patient"))
    ap.add_argument("--dst", default=str(data_dir() / "eval_audio"))
    ap.add_argument("--phone", action="store_true", help="band-limit through 8 kHz like a phone call")
    args = ap.parse_args()
    src, dst = Path(args.src), Path(args.dst)
    files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in
                   {".m4a", ".mp3", ".ogg", ".opus", ".wav", ".aac", ".amr", ".3gp", ".flac", ".webm"})
    if not files:
        print(f"No audio files under {src}")
        return 1
    for p in files:
        lang = p.parent.name
        samples = decode(p, 8000 if args.phone else audio.RATE)
        if args.phone:
            samples = audio.resample(samples, 8000, audio.RATE)
        samples = samples[: MAX_S * audio.RATE]
        target = dst / lang / f"{p.stem}.wav"
        audio.write(target, samples)
        peak = max((abs(x) for x in samples), default=0) / 32767
        print(f"  {lang}/{p.name:24} -> {target.relative_to(dst.parent)}  {len(samples) / audio.RATE:5.1f}s  peak {peak:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
