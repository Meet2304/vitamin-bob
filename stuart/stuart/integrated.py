"""Attended demo: merged Bob, real Stuart, and local Gemma in one lifecycle.

Only the recorded patient's line is simulated. Bob receives WAV audio with no
transcript sidecar; Stuart's durable transport and encrypted receiver are real.
"""
import argparse
import asyncio
import hmac
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
import uvicorn

from .contracts import Missed, safe_wav
from .demo_settings import add_settings_routes, apply_pending, disable_workers, finish_apply
from .lines import SimulatorLine
from .runtime import InstanceLock, load_profile

MODULE = Path(__file__).resolve().parents[1]
BOB = MODULE.parent / 'bob'


def load_scenarios(data):
    rows = [json.loads(line) for line in (BOB / 'eval/vignettes_recorded.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    for row in rows:
        row['wav'] = data / 'eval_audio' / row['lang'] / (row['id'] + '.wav')
        safe_wav(str(row['wav']), data / 'eval_audio')
    return {row['id']: row for row in rows}


class RecordedPatientLine(SimulatorLine):
    def __init__(self, runtime, scenarios):
        super().__init__('recorded-1', runtime)
        self.scenario = None
        self.clips = []
        self.scenarios = scenarios
        self.bindings_path = Path(runtime) / 'recorded-patients.json'
        self.bindings = json.loads(self.bindings_path.read_text()) if self.bindings_path.exists() else {}

    def assign(self, phone, scenario_id):
        self.bindings[phone] = scenario_id
        self.bindings_path.write_text(json.dumps(self.bindings))

    async def place(self, phone):
        self.scenario = self.scenarios[self.bindings[phone]]
        self.clips = []
        await super().place(phone)

    async def play(self, path, stop=None):
        self.check()
        # Hold tones run concurrently while Bob understands audio, not as questions.
        if stop is None:
            self.clips.append(Path(path).stem)
            await asyncio.sleep(.3)
        else:
            await asyncio.sleep(.1)

    async def keypad(self, action):
        self.check()
        v = self.scenario
        key = None
        for clip in reversed(self.clips):
            if clip == 'lang_menu': key = '1' if v['lang'] == 'hi' else '2'
            elif clip == 'who_is_sick': key = v.get('age', '3')
            elif clip.startswith('q_symptom_'):
                item = clip.removeprefix('q_symptom_')
                key = '3' if item in v.get('unknown_symptoms', []) else ('1' if item in v['symptoms'] else '2')
            elif clip.startswith('q_days_'):
                days = v['symptoms'].get(clip.removeprefix('q_days_'))
                key = str(days) + '#' if isinstance(days, int) else '#'
            elif clip.startswith('q_flag_'):
                item = clip.removeprefix('q_flag_')
                key = '3' if item in v.get('unknown_flags', []) else ('1' if item in v.get('flags', []) else '2')
            if key is not None: break
        self.clips = []
        await asyncio.sleep(.4)
        key = key or ''
        if action.terminator: key = key.split(action.terminator)[0]
        return {'status': 'ok' if key else 'no_input', 'digits': key[:action.max_digits]}

    async def listen(self, action, path):
        self.recording = self.scenario['wav']
        return await super().listen(action, path)


def add_demo_routes(app, board, scenarios, line, mode, servers):
    @app.get('/demo')
    async def demo_page():
        return FileResponse(MODULE / 'stuart/demo.html')

    @app.get('/demo/state')
    async def demo_state():
        active = board.store.one("SELECT COUNT(*) AS n FROM calls WHERE ended_at IS NULL")['n']
        queued = board.store.one("SELECT COUNT(*) AS n FROM missed WHERE status IN ('queued','calling','pending')")['n']
        model = False
        try:
            r = await board.client.get('http://127.0.0.1:8300/health', timeout=1)
            model = r.status_code == 200
        except httpx.HTTPError:
            pass
        return {'mode': mode, 'busy': bool(active or queued), 'model_ready': model,
            'bob_dashboard': 'http://127.0.0.1:8100/dashboard',
            'scenarios': [{'id': v['id'], 'lang': v['lang'], 'expected': v['expected'],
                           'available': True} for v in scenarios.values()],
            'central_records': len(board.central.rows()), 'transport_errors': board.errors}

    def local_action(request):
        if request.headers.get('X-VB-Demo') != '1':
            raise HTTPException(403, 'Use the local demo controls')
        origin = request.headers.get('origin')
        if origin and origin != 'http://127.0.0.1:8200':
            raise HTTPException(403, 'Local demo origin required')

    @app.post('/demo/run/{scenario_id}')
    async def run_scenario(scenario_id: str, request: Request):
        local_action(request)
        if mode != 'recorded': raise HTTPException(409, 'Recorded scenarios require recorded mode')
        if scenario_id not in scenarios: raise HTTPException(404, 'Unknown recording')
        if board.store.one("SELECT id FROM calls WHERE ended_at IS NULL") or board.store.one(
                "SELECT id FROM missed WHERE status IN ('queued','calling','pending')"):
            raise HTTPException(409, 'Wait for the current call to finish')
        # Reserve synchronously before awaiting Bob so two button presses cannot swap patients.
        if app.state.starting: raise HTTPException(409, 'Call is starting')
        app.state.starting = True
        try:
            phone = '+1555' + str(uuid.uuid4().int % 10_000_000).zfill(7)
            line.assign(phone, scenario_id)
            result = await board.missed(Missed(phone=phone, line_id=line.line_id))
            return {'missed_call_id': result, 'scenario': scenario_id}
        finally:
            app.state.starting = False

    @app.get('/demo/audio/{scenario_id}')
    async def recording(scenario_id: str):
        if scenario_id not in scenarios: raise HTTPException(404, 'Unknown recording')
        return FileResponse(scenarios[scenario_id]['wav'], media_type='audio/wav')

    @app.post('/operator/shutdown')
    async def shutdown(request: Request):
        if not hmac.compare_digest(request.headers.get('X-VB-Operator', ''), os.environ['VB_OPERATOR_TOKEN']):
            raise HTTPException(403, 'Operator token required')
        for server in servers: server.should_exit = True
        return {'stopping': True}

    app.state.starting = False


async def serve(args, profile):
    # Demo setup: apply a saved pending revision to this launcher's profile before any worker exists.
    profile, settings_state = apply_pending(args.config, profile)
    # All runtime components get one explicit environment before importing Bob.
    env = profile.environment()
    env.update(VB_BOB_DB=str(profile.data_dir / 'bob.db'),
        VB_SEED_FILE=str(BOB / 'seed/demo_district.json'), VB_UNDERSTAND='gemma',
        VB_LLM_URL='http://127.0.0.1:8300', VB_ESCALATE_AFTER_S='3600')
    if args.mode=='phone':
        env.update(VB_CALLBACK_QUEUE_SECONDS='8',VB_ANDROID_AUTO_REJECT='0')
    for key in list(os.environ):
        if key.startswith('VB_'): del os.environ[key]
    os.environ.update(env)
    sys.path.insert(0, str(BOB))
    from vitamin_bob.server import app as bob_app
    # Register the configured clinician in Bob (idempotent, history kept). If the revision cannot be
    # applied consistently, keep calls and outgoing SMS off for this run; the setup screen shows why.
    settings_state = finish_apply(profile, settings_state)
    if settings_state.get('error'):
        profile = disable_workers(profile)
    from .service import Switchboard, make_app
    scenarios = load_scenarios(profile.data_dir)
    line = RecordedPatientLine(profile.runtime_dir, scenarios) if args.mode == 'recorded' else None
    board = Switchboard(lines={line.line_id: line} if line else None)
    app = make_app(board)
    @bob_app.get('/api/live-call')
    async def live_call_state():
        return board.live_state() | {'mode':args.mode}

    @bob_app.post('/api/live-call/control')
    async def live_call_control(request: Request):
        if request.headers.get('X-VB-Demo')!='1' or request.headers.get('origin','http://127.0.0.1:8100')!='http://127.0.0.1:8100':
            raise HTTPException(403,'Use the local dashboard controls')
        body=await request.json()
        if type(body.get('paused')) is not bool:
            raise HTTPException(400,'paused must be true or false')
        board.callbacks_paused=body['paused']
        board.store.execute("INSERT OR REPLACE INTO meta VALUES('callbacks_paused',?)",('1' if body['paused'] else '0',))
        return {'paused':board.callbacks_paused}
    add_settings_routes(bob_app, profile, profile)
    servers = [uvicorn.Server(uvicorn.Config(application, host='127.0.0.1', port=port,
                log_level='warning', access_log=False)) for application, port in ((bob_app, 8100), (app, 8200))]
    add_demo_routes(app, board, scenarios, line, args.mode, servers)
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for server in servers: server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--llama', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--mode', choices=['recorded', 'phone'], default='recorded')
    args = parser.parse_args()
    profile = load_profile(args.config)
    if profile.port != 8200 or profile.bob_url != 'http://127.0.0.1:8100':
        raise ValueError('Integrated demo uses Bob 8100, Stuart 8200, Gemma 8300')
    if (profile.mode == 'hardware') != (args.mode == 'phone'):
        raise ValueError('Profile mode does not match demo mode')
    if not os.getenv('VB_OPERATOR_TOKEN'): raise ValueError('Start with Start-IntegratedDemo.ps1')
    for port in (8100, 8200, 8300):
        with socket.socket() as check: check.bind(('127.0.0.1', port))
    profile.runtime_dir.mkdir(parents=True, exist_ok=True)
    model = args.models / 'gemma-4-E2B-it-Q8_0.gguf'
    projection = args.models / 'mmproj-gemma-4-E2B-it-BF16.gguf'
    for path in (args.llama, model, projection):
        if not path.is_file(): raise ValueError(f'Missing local model asset: {path.name}')
    with InstanceLock(profile.data_dir / '.stuart.lock'):
        for directory in ('prompts', 'eval_audio'):
            source, target = args.assets / directory, profile.data_dir / directory
            if not target.exists(): shutil.copytree(source, target)
        for clip in (profile.data_dir / 'prompts').rglob('*.wav'):
            safe_wav(str(clip), profile.data_dir / 'prompts')
        load_scenarios(profile.data_dir)
        manifest = profile.runtime_dir / 'integrated-process.json'
        def state(value):
            manifest.write_text(json.dumps({'state': value, 'mode': args.mode, 'pid': os.getpid()}))
        with (profile.runtime_dir / 'model.log').open('ab') as log:
            process = subprocess.Popen([str(args.llama), '-m', str(model), '--mmproj', str(projection),
                '--host', '127.0.0.1', '--port', '8300', '-c', '8192', '--jinja'],
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                state('loading_model')
                deadline = time.monotonic() + 150
                with httpx.Client(timeout=2, trust_env=False) as client:
                    while True:
                        if process.poll() is not None: raise RuntimeError('Gemma exited; inspect model.log')
                        try:
                            if client.get('http://127.0.0.1:8300/health').status_code == 200: break
                        except httpx.HTTPError: pass
                        if time.monotonic() > deadline: raise TimeoutError('Gemma startup timed out')
                        time.sleep(.5)
                state('running')
                asyncio.run(serve(args, profile))
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=15)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
                state('stopped')


if __name__ == '__main__':
    main()
