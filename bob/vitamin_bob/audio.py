"""WAV helpers, standard library only.

Every file Bob hands to Stuart must be WAV, 16 kHz, mono, 16-bit PCM (contract 7.1), so
everything that writes audio goes through `to_contract` or `write`, and `check` verifies it.
"""

import array
import io
import math
import wave
from pathlib import Path

RATE = 16000


def read_pcm(data: bytes) -> tuple[array.array, int]:
    """Decode WAV bytes into mono 16-bit samples and their sample rate."""
    with wave.open(io.BytesIO(data)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM, got {8 * w.getsampwidth()}-bit")
        channels, rate = w.getnchannels(), w.getframerate()
        samples = array.array("h", w.readframes(w.getnframes()))
    if channels == 2:
        samples = array.array("h", ((samples[i] + samples[i + 1]) // 2 for i in range(0, len(samples), 2)))
    elif channels != 1:
        raise ValueError(f"unsupported channel count {channels}")
    return samples, rate


def resample(samples: array.array, src: int, dst: int = RATE) -> array.array:
    """Linear interpolation. Good enough for speech prompts that are generated near 16 kHz."""
    if src == dst or not samples:
        return samples
    n = int(len(samples) * dst / src)
    out = array.array("h", bytes(2 * n))
    step = src / dst
    last = len(samples) - 1
    for i in range(n):
        pos = i * step
        j = int(pos)
        frac = pos - j
        nxt = samples[j + 1] if j < last else samples[last]
        out[i] = int(samples[j] + (nxt - samples[j]) * frac)
    return out


def silence(ms: int) -> array.array:
    return array.array("h", bytes(2 * (RATE * ms // 1000)))


def tone(freq: float, ms: int, volume: float = 0.3) -> array.array:
    n = RATE * ms // 1000
    fade = min(n // 2, RATE // 100)  # 10 ms fade in/out avoids clicks
    out = array.array("h")
    for i in range(n):
        env = min(1.0, i / fade, (n - 1 - i) / fade) if fade else 1.0
        out.append(int(32767 * volume * env * math.sin(2 * math.pi * freq * i / RATE)))
    return out


def to_contract(data: bytes, pad_ms: int = 150) -> array.array:
    """Any 16-bit WAV -> contract samples, with a short tail so clips played back to back breathe."""
    samples, rate = read_pcm(data)
    return resample(samples, rate) + silence(pad_ms)


def write(path: Path, samples: array.array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


def concat(paths: list[Path], gap_ms: int = 250) -> array.array:
    out = array.array("h")
    for p in paths:
        samples, rate = read_pcm(p.read_bytes())
        out += resample(samples, rate) + silence(gap_ms)
    return out


def check(path: Path) -> str | None:
    """None if the file meets the contract, else what is wrong."""
    try:
        with wave.open(str(path)) as w:
            got = (w.getframerate(), w.getnchannels(), w.getsampwidth())
    except Exception as e:  # noqa: BLE001 - report any unreadable file
        return f"unreadable: {e}"
    return None if got == (RATE, 1, 2) else f"rate/channels/width {got}, expected ({RATE}, 1, 2)"
