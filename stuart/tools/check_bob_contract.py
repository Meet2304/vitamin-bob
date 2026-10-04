"""Real Bob + Stuart HTTP smoke check with synthetic calls and isolated data.

No phone, model, or over-air SMS is enabled. Bob's source and existing data are
read-only inputs. This checks transport compatibility, not clinical accuracy.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time
import uuid

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE))


async def check(args):
    import httpx
    import uvicorn
    from stuart.contracts import safe_wav
    from stuart.lines import SimulatorLine
    from stuart.service import Switchboard, make_app

    bob_root = args.bob_root.resolve()
    prompt_root = (args.prompt_root or bob_root.parent / 'data' / 'prompts').resolve()
    if not (bob_root / 'vitamin_bob' / 'server.py').is_file():
        raise ValueError('Select the current Bob module directory')
    if not (prompt_root / 'system' / 'fallback.wav').is_file():
        raise ValueError('Bob prompt audio is missing')
    if args.bob_port == args.stuart_port:
        raise ValueError('Use distinct ports')
    for port in (args.bob_port, args.stuart_port):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    root = MODULE / 'runtime' / 'bob-contract-check' / str(uuid.uuid4())
    data = root / 'data'
    shutil.copytree(prompt_root, data / 'prompts')
    clips = list((data / 'prompts').rglob('*.wav'))
    for clip in clips:
        safe_wav(str(clip), data / 'prompts')
    bob_url, stuart_url = f'http://127.0.0.1:{args.bob_port}', f'http://127.0.0.1:{args.stuart_port}'
    os.environ.update(VB_DATA_DIR=str(data), VB_BOB_DB=str(data / 'bob.db'),
                      VB_SEED_FILE=str(bob_root / 'seed' / 'demo_district.json'),
                      VB_BOB_URL=bob_url, VB_STUART_URL=stuart_url, VB_UNDERSTAND='keyword',
                      VB_ANDROID_ENABLED='0', VB_SMS_LINE_ID='sim-hi', VB_SYNC_TRANSPORT='loopback',
                      VB_DAILY_SMS_CAP='100', VB_SYNC_DROP_FIRST='0', VB_ESCALATE_AFTER_S='3600')
    sys.path.insert(0, str(bob_root))
    from vitamin_bob.server import app as bob_app
    lines = {f'sim-{lang}': SimulatorLine(f'sim-{lang}', root, digits=[key, '3'] + ['2'] * 30)
             for lang, key in [('hi', '1'), ('gu', '2')]}
    board = Switchboard(data, root / 'transport', bob_url, lines)
    servers = [uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                log_level='error', access_log=False)) for app, port in
                [(bob_app, args.bob_port), (make_app(board), args.stuart_port)]]
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    report = {'mode': 'real Bob/Stuart over localhost HTTP; scripted calls; keyword mode; simulated SMS; encrypted loopback sync',
              'data_dir': str(data), 'prompt_wavs_validated': len(clips)}
    headers = {'X-VB-Contract': '0.2'}
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            deadline = time.monotonic() + 10
            while not all(server.started for server in servers):
                if any(task.done() for task in tasks) or time.monotonic() > deadline:
                    raise RuntimeError('Local integration services did not start')
                await asyncio.sleep(0.1)
            for url in (bob_url, stuart_url):
                response = await client.get(url + '/v1/health', headers=headers)
                response.raise_for_status()
            response = await client.post(bob_url + '/api/clinics/rampur/status', json={'status': 'open'})
            response.raise_for_status()
            for index, line_id in enumerate(lines, 11):
                response = await client.post(stuart_url + '/sim/missed-call', headers=headers,
                    json={'phone': f'+9198000000{index}', 'line_id': line_id})
                response.raise_for_status()
            deadline = time.monotonic() + 45
            while True:
                response = await client.get(bob_url + '/api/state')
                response.raise_for_status()
                state = response.json()
                if len(state['calls']) == 2 and all(call['ended_at'] for call in state['calls']):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('Scripted bilingual calls did not finish')
                await asyncio.sleep(0.25)
            response = await client.post(stuart_url + '/sim/sms', json={
                'message_id': 'synthetic-clinic-closed', 'phone': '+919000000001',
                'line_id': 'sim-hi', 'text': 'CLOSED'})
            response.raise_for_status()
            deadline = time.monotonic() + 12
            while True:
                state = (await client.get(bob_url + '/api/state')).json()
                central = (await client.get(stuart_url + '/central/records')).json()['records']
                sync = state['sync']['recent']
                if (state['sms'] and all(message['status'] == 'delivered' for message in state['sms']) and
                        len(central) >= 4 and len(sync) >= 4 and all(record['status'] == 'acked' for record in sync)):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('Bob outboxes did not finish simulated transport')
                await asyncio.sleep(0.25)
            report['calls'] = [{key: call[key] for key in ('lang', 'step', 'end_reason')} |
                              {'tier': (call['triage'] or {}).get('tier')} for call in state['calls']]
            report['sms_statuses'] = [message['status'] for message in state['sms']]
            report['central_records'] = len(central)
            report['bob_sync_statuses'] = [record['status'] for record in sync]
            report['clinic_closed_by_sms'] = any(clinic['clinic_id'] == 'rampur' and clinic['status'] == 'closed'
                                                 for clinic in state['clinics'])
            report['transport_errors'] = board.errors
            report['unacknowledged_events'] = len(board.store.rows('SELECT id FROM events WHERE response IS NULL'))
            report['passed'] = (sorted(call['lang'] for call in report['calls']) == ['gu', 'hi'] and
                all(call['end_reason'] == 'completed' and call['tier'] for call in report['calls']) and
                report['clinic_closed_by_sms'] and not board.errors and not report['unacknowledged_events'])
    except Exception as exc:
        report.update(passed=False, error=f'{type(exc).__name__}: {exc}')
        report['transport_errors'] = board.errors
        if 'state' in locals():
            report['bob_sync_statuses'] = [record['status'] for record in state.get('sync', {}).get('recent', [])]
        if 'central' in locals():
            report['central_records'] = len(central)
    finally:
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        output = root / 'result.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True, indent=2))
        print(f'Report: {output}')
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bob-root', type=Path, required=True)
    parser.add_argument('--prompt-root', type=Path)
    parser.add_argument('--bob-port', type=int, default=18101)
    parser.add_argument('--stuart-port', type=int, default=18201)
    raise SystemExit(asyncio.run(check(parser.parse_args())))
