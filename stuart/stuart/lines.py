import asyncio
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from .audio import check_capture_device, check_playback_device, detect_dtmf, duration, input_chunks, play_blocking, record_blocking, tone


class DialFailed(Exception):
    def __init__(self,message,reason='failed'):
        super().__init__(message)
        self.reason=reason


class CallerHungUp(Exception):
    pass


def live_telecom_states(text):
    """Read current calls only; dumpsys also includes historical ACTIVE events."""
    section=re.search(r'(?ms)^CallsManager:[ \t]*\r?\n.*?^([ \t]+)mCalls:[ \t]*\r?\n(.*?)(?=^\1\S|\Z)',text)
    if not section:
        return None
    return re.findall(r'\bstate\s*[:=]\s*([A-Z_]+)',section[2],re.IGNORECASE)


def live_telecom_audio_route(text):
    section = re.search(r'(?ms)^([ \t]+)mCallAudioRouteAdapter:[ \t]*\r?\n(.*?)(?=^\1\S|\Z)', text)
    if not section:
        return None
    route = re.search(r'(?m)^\s+Current route: AudioRoute\[Type=([A-Z_]+),', section[2])
    return route[1] if route else None


class SimulatorLine:
    def __init__(self, line_id, runtime, mode="scripted", digits=None, recording=None):
        self.line_id, self.mode, self.runtime = line_id, mode, Path(runtime)
        self.state = "idle"
        self.input = asyncio.Queue()
        self.script = list(digits or ["1", "2", "1"])
        self.initial_script = self.script.copy()
        self.recording = recording
        self.disconnected = False
        self.dial_failure = False
        self.input_device = os.getenv("VB_AUDIO_INPUT")
        self.output_device = os.getenv("VB_AUDIO_OUTPUT")
        self.input_device = int(self.input_device) if self.input_device and self.input_device.isdigit() else self.input_device
        self.output_device = int(self.output_device) if self.output_device and self.output_device.isdigit() else self.output_device

    async def place(self, phone):
        if self.dial_failure:
            raise DialFailed("Simulated no answer",reason='no_answer')
        self.disconnected = False
        self.script = self.initial_script.copy()
        self.state = "in_call"

    def check(self):
        if self.disconnected:
            raise CallerHungUp()

    async def play(self, path, stop=None):
        self.check()
        if self.mode != "scripted":
            await asyncio.to_thread(play_blocking, path, self.output_device,
                                    lambda: self.disconnected or (stop and stop.is_set()))
        else:
            await asyncio.sleep(0.03)
        self.check()

    async def keypad(self, action):
        self.check()
        if self.mode == "scripted":
            await asyncio.sleep(0.02)
            if not self.script:
                return {"status": "timeout", "digits": ""}
            text = self.script.pop(0)
        else:
            deadline=time.monotonic()+action.timeout_ms/1000
            while True:
                self.check()
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    return {"status":"timeout","digits":""}
                try:
                    text=await asyncio.wait_for(self.input.get(),min(0.1,remaining))
                    break
                except asyncio.TimeoutError:
                    continue
        self.check()
        text = text.split(action.terminator)[0] if action.terminator else text
        return {"status": "ok" if text else "no_input", "digits": text[:action.max_digits]}

    async def listen(self, action, path):
        self.check()
        if self.mode != "scripted":
            result = await asyncio.to_thread(record_blocking, path, action.max_ms,
                                            action.end_silence_ms, self.input_device,
                                            lambda: self.disconnected)
        else:
            if self.recording:
                shutil.copyfile(self.recording, path)
            else:
                tone(path, 0.4, 220)
            result = {"status": "ok", "recording_path": str(Path(path).resolve()), "duration_ms": duration(path)}
        self.check()
        return result

    async def hangup(self):
        self.disconnected, self.state = True, "idle"

    async def send_sms(self, request):
        await asyncio.sleep(0.02)
        return "delivered"

    async def available(self):
        return True


class Adb:
    def __init__(self, executable, serial=None):
        self.executable, self.serial = str(executable), serial

    def run(self, *args, timeout=8):
        # adb joins shell arguments into a remote shell command. Quote there as well
        # as using a local argv list, so SQL > comparisons are not redirections.
        remote = ["shell", shlex.join(args[1:])] if args and args[0] == "shell" else list(args)
        command = [self.executable] + (["-s", self.serial] if self.serial else []) + remote
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                creationflags=flags, encoding="utf-8", errors="replace")
        if result.returncode:
            raise OSError(result.stderr.strip() or result.stdout.strip())
        return result.stdout


class AndroidLine(SimulatorLine):
    """ADB control plus explicitly selected PC audio endpoints; no call-audio API claims."""
    def __init__(self, line_id, runtime, adb, **kwargs):
        super().__init__(line_id, runtime, mode="interactive", **kwargs)
        self.adb = adb
        self.state = "offline"
        self.monitor_task = None
        self.observed_active = False
        self.dial_started = False

    async def available(self):
        try:
            return (await asyncio.to_thread(self.adb.run, "get-state")).strip() == "device"
        except (OSError, subprocess.TimeoutExpired):
            return False

    async def place(self, phone):
        self.dial_started = False
        if not await self.available():
            raise DialFailed("Android USB line offline")
        if self.input_device is None or self.output_device is None:
            raise DialFailed("Set verified VB_AUDIO_INPUT and VB_AUDIO_OUTPUT before phone callbacks")
        states = live_telecom_states(await asyncio.to_thread(self.adb.run, 'shell', 'dumpsys', 'telecom'))
        if states is None:
            raise DialFailed('Android live call state unavailable; handset compatibility test required')
        if states:
            raise DialFailed('Android already has a call; leave it under operator control')
        try:
            await asyncio.to_thread(check_capture_device, self.input_device)
            await asyncio.to_thread(check_playback_device, self.output_device)
        except Exception as exc:
            raise DialFailed('Configured audio endpoints cannot carry PCM16 at 16 kHz') from exc
        output=await asyncio.to_thread(self.adb.run, "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", "tel:"+phone)
        if 'Error:' in output or 'Permission Denial' in output:
            raise DialFailed('Android rejected the call command')
        self.dial_started = True
        self.disconnected, self.state, self.observed_active = False, "in_call", False
        deadline=time.monotonic()+float(os.getenv('VB_ANDROID_ANSWER_TIMEOUT_SECONDS','45'))
        seen=False
        while time.monotonic()<deadline:
            states=live_telecom_states(await asyncio.to_thread(self.adb.run,'shell','dumpsys','telecom'))
            if states is None:
                raise DialFailed('Android live call state unavailable; handset compatibility test required')
            states=[s.upper() for s in states]
            if 'ACTIVE' in states:
                self.observed_active=True
                break
            seen=seen or bool(states)
            if seen and not states:
                raise DialFailed('Call ended before remote answer',reason='no_answer')
            await asyncio.sleep(0.5)
        else:
            raise DialFailed('Remote answer deadline exceeded',reason='no_answer')
        self.monitor_task = asyncio.create_task(self.monitor())
        required_route = os.getenv('VB_ANDROID_REQUIRED_AUDIO_ROUTE')
        if required_route:
            deadline = time.monotonic() + float(os.getenv('VB_ANDROID_AUDIO_ROUTE_TIMEOUT_SECONDS', '60'))
            stable = 0
            while time.monotonic() < deadline:
                self.check()
                dump = await asyncio.to_thread(self.adb.run, 'shell', 'dumpsys', 'telecom')
                if not live_telecom_states(dump):
                    raise CallerHungUp()
                stable = stable + 1 if live_telecom_audio_route(dump) == required_route else 0
                if stable >= 5:
                    break
                await asyncio.sleep(0.5)
            else:
                raise DialFailed('Required call audio route unavailable; select Transfer to PC in Phone Link')

    async def monitor(self):
        # This signal is OEM-dependent: report disconnect only after seeing non-idle state.
        errors = 0
        while not self.disconnected:
            await asyncio.sleep(0.7)
            try:
                text = await asyncio.to_thread(self.adb.run, "shell", "dumpsys", "telephony.registry")
                states = re.findall(r"mCallState=(\d+)", text)
                if any(s != "0" for s in states):
                    self.observed_active = True
                elif states and self.observed_active:
                    self.disconnected = True
                errors = 0
            except (OSError, subprocess.TimeoutExpired):
                errors += 1
                if errors >= 2:
                    self.disconnected = True

    async def keypad(self, action):
        def collect():
            digits, previous, stable, released = "", None, 0, True
            deadline = time.monotonic() + action.timeout_ms/1000
            with input_chunks(self.input_device,dtype="float32",blocksize=640) as read:
                while time.monotonic() < deadline and not self.disconnected:
                    chunk = read(min(0.1,max(0.001,deadline-time.monotonic())))
                    if chunk is None:
                        continue
                    key = detect_dtmf(chunk)
                    stable = stable+1 if key and key == previous else 1
                    if key is None:
                        released = True
                    elif stable >= 2 and released:
                        released = False
                        if key == action.terminator:
                            return {"status": "ok" if digits else "no_input", "digits": digits}
                        digits += key
                        if len(digits) >= action.max_digits:
                            return {"status": "ok", "digits": digits}
                    previous = key
            return {"status": "ok" if digits else "timeout", "digits": digits}
        result = await asyncio.to_thread(collect)
        self.check()
        return result

    async def hangup(self):
        try:
            if self.dial_started:
                await asyncio.to_thread(self.adb.run, "shell", "input", "keyevent", "6")
        finally:
            self.dial_started = False
            await super().hangup()
            if self.monitor_task:
                self.monitor_task.cancel()

    async def send_sms(self, request):
        import httpx
        url = os.getenv("VB_SMS_GATE_URL", "http://127.0.0.1:8080")
        username, password = os.getenv("VB_SMS_GATE_USER"), os.getenv("VB_SMS_GATE_PASSWORD")
        if not username or not password:
            raise OSError("SMSGate local credentials are not configured")
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(url+"/message", auth=(username,password),
                                         json={"id": request["message_id"], "textMessage": {"text": request["text"]},
                                               "phoneNumbers": [request["to"]]})
            response.raise_for_status()
        # API acceptance is queued, not proof of sending or delivery; webhook updates later.
        return "accepted"
