import math
import os
import queue
import threading
import time
import wave
from contextlib import contextmanager
from pathlib import Path

RATE = 16000
DTMF_LOW = [697, 770, 852, 941]
DTMF_HIGH = [1209, 1336, 1477]
DTMF_KEYS = ["123", "456", "789", "*0#"]


@contextmanager
def windows_audio_thread():
    """COM audio objects require initialization in every executor thread."""
    if os.name != 'nt':
        yield
        return
    # SoundCard initializes only its importing thread. Import before balancing
    # our own per-operation COM reference, including already-initialized threads.
    import soundcard
    import ctypes
    ole32=ctypes.WinDLL('ole32')
    initialize=ole32.CoInitializeEx
    initialize.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    initialize.restype=ctypes.c_long
    result=initialize(None,0)
    if result < 0 and (result & 0xffffffff) != 0x80010106:
        raise OSError(f'Windows audio COM initialization failed: {result & 0xffffffff:#x}')
    try:
        yield
    finally:
        # S_OK and S_FALSE each acquire a reference. Changed-apartment mode does
        # not; in that case the caller's existing apartment remains in use.
        if result >= 0:
            ole32.CoUninitialize()


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


@windows_audio_thread()
def play_blocking(path, device=None, stopped=None):
    import numpy as np
    import sounddevice as sd
    with wave.open(str(path), "rb") as f:
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").reshape(-1,1)
    if isinstance(device,str) and device.startswith('wasapi:'):
        speaker = wasapi_speaker(device)
        # Use native shared-mode WASAPI for the virtual transmit cable. Keep
        # stereo channel layout and let Windows convert the 16 kHz mix rate.
        with speaker.player(samplerate=RATE,channels=speaker.channels,blocksize=1600) as player:
            for offset in range(0,len(samples),800):
                if stopped and stopped():
                    return
                data = np.repeat(samples[offset:offset+800].astype('float32')/32768,
                                 speaker.channels,axis=1)
                player.play(data)
            # Queue one full silent buffer to drain the last audible samples.
            player.play(np.zeros((player.buffersize,speaker.channels),dtype='float32'))
        return
    finished, offset = threading.Event(), 0
    def callback(outdata, frames, timing, status):
        nonlocal offset
        outdata.fill(0)
        count = min(frames, len(samples)-offset)
        outdata[:count] = samples[offset:offset+count]
        offset += count
        if offset >= len(samples):
            raise sd.CallbackStop()
    # WDM-KS Bluetooth endpoints support callbacks but reject blocking write().
    with sd.OutputStream(samplerate=RATE, channels=1, dtype="int16", device=device,
                         callback=callback, finished_callback=finished.set,
                         **stream_settings(device,'output')) as stream:
        deadline = time.monotonic()+len(samples)/RATE+5
        while not finished.wait(0.05):
            if stopped and stopped():
                stream.abort()
                return
            if time.monotonic() >= deadline:
                stream.abort()
                raise TimeoutError("Audio output did not finish")
        if offset < len(samples):
            raise OSError("Audio output stopped before the prompt finished")


@contextmanager
def input_chunks(device=None, dtype="int16", blocksize=800):
    with windows_audio_thread():
        with _input_chunks(device,dtype,blocksize) as read:
            yield read


@contextmanager
def _input_chunks(device=None, dtype="int16", blocksize=800):
    """Bounded callback capture, including callback-only Windows Bluetooth drivers."""
    if isinstance(device,str) and device.startswith("loopback:"):
        import numpy as np
        mic = loopback_device(device)
        # Capture every channel before downmixing: SoundCard documents a Windows
        # single-channel capture problem. WASAPI converts the mix rate to 16 kHz.
        with mic.recorder(samplerate=RATE,channels=mic.channels,blocksize=blocksize*4) as recorder:
            def read(timeout=0.1):
                mono = np.mean(recorder.record(numframes=blocksize),axis=1,keepdims=True)
                if dtype == "float32":
                    return mono.astype("float32")
                return np.clip(np.rint(mono*32768),-32768,32767).astype("int16")
            yield read
        return
    import sounddevice as sd
    chunks, errors = queue.Queue(maxsize=100), []
    def callback(indata, frames, timing, status):
        if status.input_overflow:
            errors.append(OSError("Audio input overflow"))
            raise sd.CallbackAbort()
        try:
            chunks.put_nowait(indata.copy())
        except queue.Full:
            errors.append(OSError("Audio capture consumer fell behind"))
            raise sd.CallbackAbort()
    with sd.InputStream(samplerate=RATE, channels=1, dtype=dtype, device=device,
                        blocksize=blocksize, callback=callback,
                        **stream_settings(device,'input')) as stream:
        def read(timeout=0.1):
            if errors:
                raise errors[0]
            try:
                return chunks.get(timeout=timeout)
            except queue.Empty:
                if not stream.active:
                    raise OSError("Audio input stopped unexpectedly")
                return None
        yield read


def loopback_device(device):
    import soundcard as sc
    selector = device.removeprefix("loopback:")
    matches = [m for m in sc.all_microphones(include_loopback=True)
               if m.isloopback and (m.id == selector or selector.casefold() in m.name.casefold())]
    if not selector or len(matches) != 1:
        raise ValueError("Select one exact speaker loopback name from stuart devices")
    if matches[0].channels < 2:
        raise ValueError("Use a stereo speaker endpoint for Windows loopback capture")
    return matches[0]


def wasapi_speaker(device):
    import soundcard as sc
    selector = device.removeprefix('wasapi:')
    matches = [s for s in sc.all_speakers()
               if s.id == selector or selector.casefold() in s.name.casefold()]
    if not selector or len(matches) != 1:
        raise ValueError('Select one exact WASAPI speaker name from stuart devices')
    return matches[0]


@windows_audio_thread()
def check_capture_device(device):
    if isinstance(device,str) and device.startswith("loopback:"):
        mic = loopback_device(device)
        with mic.recorder(samplerate=RATE,channels=mic.channels,blocksize=3200):
            pass
    else:
        import sounddevice as sd
        sd.check_input_settings(device=device,channels=1,dtype='int16',samplerate=RATE,
                                **stream_settings(device,'input'))


def stream_settings(device,direction):
    import sounddevice as sd
    info = sd.query_devices(device,direction)
    if sd.query_hostapis(info['hostapi'])['name'] == 'Windows WASAPI':
        # Windows shared-mode conversion preserves the 16 kHz WAV contract while
        # allowing virtual cables configured with a 48 kHz mix format.
        return {'extra_settings':sd.WasapiSettings(auto_convert=True)}
    return {}


@windows_audio_thread()
def check_playback_device(device):
    if isinstance(device,str) and device.startswith('wasapi:'):
        speaker = wasapi_speaker(device)
        with speaker.player(samplerate=RATE,channels=speaker.channels,blocksize=1600):
            pass
        return
    import sounddevice as sd
    sd.check_output_settings(device=device,channels=1,dtype='int16',samplerate=RATE,
                             **stream_settings(device,'output'))


def record_blocking(path, max_ms, silence_ms, device=None, stopped=None):
    import numpy as np
    chunks, silent, heard = [], 0, False
    with input_chunks(device) as read:
        deadline = time.monotonic()+max_ms/1000
        frames = 0
        while time.monotonic() < deadline and frames < math.ceil(max_ms*RATE/1000):
            if stopped and stopped():
                break
            chunk = read()
            if chunk is None:
                continue
            chunk = chunk[:math.ceil(max_ms*RATE/1000)-frames]
            frames += len(chunk)
            chunks.append(chunk.copy())
            rms = np.sqrt(np.mean(chunk.astype(float)**2)) / 32768
            if rms > 0.015:
                heard, silent = True, 0
            else:
                silent += len(chunk)*1000/RATE
            if heard and silent >= silence_ms:
                break
    pcm = np.concatenate(chunks).astype("<i2").tobytes() if chunks else b""
    write_wav(path, pcm)
    return {"recording_path": str(Path(path).resolve()), "duration_ms": len(pcm)//32,
            "status": "ok" if heard else "no_input"}
