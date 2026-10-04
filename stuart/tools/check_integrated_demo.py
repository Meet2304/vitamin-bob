"""Exercise the running recorded demo through public HTTP APIs, with real Gemma.

Uses only the recorded mode; refuses a live phone instance. Does not reset data.
"""
import json
from pathlib import Path
import time
import uuid

import httpx


def main():
    report = {'passed': False, 'calls': [], 'mode': 'real Bob + Stuart + Gemma; recorded WAVs, scripted keypad, simulated SMS, encrypted local Central'}
    output = Path(__file__).resolve().parents[1] / 'runtime' / 'integrated-reports' / (str(uuid.uuid4()) + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=25, trust_env=False) as client:
        def get(url):
            r = client.get(url); r.raise_for_status(); return r.json()
        def post(url, **kwargs):
            r = client.post(url, **kwargs); r.raise_for_status(); return r.json()
        bob, stuart = 'http://127.0.0.1:8100', 'http://127.0.0.1:8200'
        initial = get(stuart + '/demo/state')
        if initial['mode'] != 'recorded' or initial['busy']:
            raise RuntimeError('Requires an idle recorded demo; will not use phone mode')
        if not initial['model_ready']: raise RuntimeError('Local Gemma must be ready')
        old_statuses = {c['clinic_id']: c['status'] for c in get(bob + '/api/state')['clinics'] if c['clinic_id'] in ('rampur', 'devgaon')}
        try:
            for scenario, tier, close_a in [('Hindi_1', 'MEDIUM', False), ('Gujarati_5', 'EMERGENCY', False), ('Hindi_3', 'HIGH', True)]:
                post(bob + '/api/clinics/rampur/status', json={'status': 'closed' if close_a else 'open'})
                post(bob + '/api/clinics/devgaon/status', json={'status': 'open'})
                before = {c['call_id'] for c in get(bob + '/api/state')['calls']}
                post(stuart + '/demo/run/' + scenario, headers={'X-VB-Demo': '1'})
                deadline = time.monotonic() + 100
                while True:
                    state = get(bob + '/api/state')
                    call = next((c for c in state['calls'] if c['call_id'] not in before), None)
                    if call and call['ended_at']: break
                    if time.monotonic() > deadline: raise TimeoutError('Conversation did not complete: ' + scenario)
                    time.sleep(.5)
                triage = call['triage'] or {}
                engine = (call['understanding'] or {}).get('engine', '')
                result = {'scenario': scenario, 'tier': triage.get('tier'), 'expected': tier,
                    'engine': engine, 'understand_ms': (call['understanding'] or {}).get('ms'),
                    'end_reason': call['end_reason'], 'clinic': triage.get('routed_clinic_id'),
                    'call_id': call['call_id'], 'failover_required': close_a}
                result['passed'] = (result['tier'] == tier and engine.startswith('gemma') and
                    result['end_reason'] == 'completed' and (not close_a or result['clinic'] == 'devgaon'))
                report['calls'].append(result)
                print(json.dumps(result), flush=True)
                if not result['passed']: raise AssertionError('Scenario did not meet integration expectations')
            deadline = time.monotonic() + 20
            while True:
                state = get(bob + '/api/state')
                if state['sms'] and all(m['status'] == 'delivered' for m in state['sms']) and all(r['status'] == 'acked' for r in state['sync']['recent']): break
                if time.monotonic() > deadline: raise TimeoutError('SMS/sync outboxes did not settle')
                time.sleep(.5)
            live_alerts = [a for a in state['alerts'] if not a.get('acked_at')]
            for alert in live_alerts:
                assert post(bob + '/api/alerts/' + alert['alert_id'] + '/ack', json={'by': 'Integration demo'})['ok']
            report.update(sms_statuses=[m['status'] for m in state['sms']],
                sync_statuses=[r['status'] for r in state['sync']['recent']],
                central_records=len(get(stuart + '/central/records')['records']),
                alerts_acknowledged=len(live_alerts), ready=get(stuart + '/ready')['ready'])
            report['passed'] = report['ready'] and all(r['passed'] for r in report['calls'])
        except Exception as exc:
            report['error'] = f'{type(exc).__name__}: {exc}'
        finally:
            for clinic, status in old_statuses.items():
                post(bob + '/api/clinics/' + clinic + '/status', json={'status': status})
            output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print('Report: ' + str(output), flush=True)
            print(json.dumps(report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
