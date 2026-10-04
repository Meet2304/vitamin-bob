import math
import wave
from pathlib import Path

RATE = 16000
DTMF_LOW = [697, 770, 852, 941]
DTMF_HIGH = [1209, 1336, 1477]
DTMF_KEYS = ["123", "456", "789", "*0#"]


def tone(path, seconds=0.3, frequency=440):
    import numpy as np
    t = np.arange(int(seconds * RATE)) / RATE
    samples = (np.sin(2 * np.pi * frequency * t) * 3500).astype("<i2")
    write_wav(path, samples.tobytes())
    return Path(path).resolve()


def write_wav(path, pcm):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm)


def duration(path):
    with wave.open(str(path), "rb") as f:
        return round(f.getnframes() * 1000 / f.getframerate())


def detect_dtmf(samples, rate=RATE):
    """Narrow frequency measurements, with purity and twist checks against speech."""
    import numpy as np
    x = np.asarray(samples, dtype=float).reshape(-1)
    if len(x) < rate * 0.025 or np.sqrt(np.mean(x*x)) < 0.003:
        return None
    t = np.arange(len(x)) / rate
    # Equivalent to evaluating the Goertzel bins at the specified frequencies.
    power = [abs(np.dot(x, np.exp(-2j*np.pi*f*t)))**2 for f in DTMF_LOW + DTMF_HIGH]
    lo, hi = int(np.argmax(power[:4])), int(np.argmax(power[4:]))
    a, b = power[lo], power[4+hi]
    others = [p for i, p in enumerate(power) if i not in (lo, hi+4)]
    if min(a,b) < 5 * max(others, default=0) or not 0.16 < a/max(b,1e-12) < 6.3:
        return None
    # A pair of real sinusoids concentrates approximately N*energy/2 in these bins.
    purity = 2*(a+b)/(len(x)*np.dot(x,x)+1e-12)
    return DTMF_KEYS[lo][hi] if purity > 0.65 else None


def play_blocking(path, device=None, stopped=None):
    import numpy as np
    import sounddevice as sd
    with wave.open(str(path), "rb") as f:
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").reshape(-1,1)
    with sd.OutputStream(samplerate=RATE, channels=1, dtype="int16", device=device) as stream:
        for offset in range(0, len(samples), 800):
            if stopped and stopped():
                break
            stream.write(samples[offset:offset+800])


def record_blocking(path, max_ms, silence_ms, device=None, stopped=None):
    import numpy as np
    import sounddevice as sd
    chunks, silent, heard = [], 0, False
    with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", device=device, blocksize=800) as stream:
        for _ in range(math.ceil(max_ms / 50)):
            if stopped and stopped():
                break
            chunk, _ = stream.read(800)
            chunks.append(chunk.copy())
            rms = np.sqrt(np.mean(chunk.astype(float)**2)) / 32768
            if rms > 0.015:
                heard, silent = True, 0
            else:
                silent += 50
            if heard and silent >= silence_ms:
                break
    pcm = np.concatenate(chunks).astype("<i2").tobytes() if chunks else b""
    write_wav(path, pcm)
    return {"recording_path": str(Path(path).resolve()), "duration_ms": len(pcm)//32,
            "status": "ok" if heard else "no_input"}
