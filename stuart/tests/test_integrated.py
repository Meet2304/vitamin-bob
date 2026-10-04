import asyncio
from types import SimpleNamespace

import httpx

from stuart.integrated import RecordedPatientLine, add_demo_routes
from stuart.service import Switchboard, make_app


def test_recorded_patient_uses_reference_keys_and_keeps_scenario_after_restart(tmp_path):
    scenarios = {'case': {'lang': 'gu', 'age': '2', 'symptoms': {'cough': 21}, 'flags': ['convulsions']}}
    first = RecordedPatientLine(tmp_path, scenarios)
    first.assign('+15550100100', 'case')
    async def run():
        line = RecordedPatientLine(tmp_path, scenarios)
        await line.place('+15550100100')
        for clip, expected in [('lang_menu', '2'), ('who_is_sick', '2'), ('q_symptom_cough', '1'),
                               ('q_symptom_fever', '2'), ('q_days_cough', '21'), ('q_flag_convulsions', '1')]:
            line.clips = [clip]
            result = await line.keypad(SimpleNamespace(terminator='#', max_digits=3))
            assert result == {'status': 'ok', 'digits': expected}
    asyncio.run(run())


def test_demo_refuses_phone_mode_and_unlabelled_mutations(tmp_path):
    async def run():
        board = Switchboard(tmp_path/'data', tmp_path/'runtime', lines={})
        app = make_app(board); app.state.board = board
        add_demo_routes(app, board, {'case': {}}, None, 'phone', [])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1:8200') as client:
            assert (await client.post('/demo/run/case')).status_code == 403
            assert (await client.post('/demo/run/case', headers={'X-VB-Demo':'1'})).status_code == 409
        await board.stop()
    asyncio.run(run())


def test_double_click_cannot_swap_recorded_patient_while_bob_decides(tmp_path):
    async def run():
        line = RecordedPatientLine(tmp_path, {'one': {}, 'two': {}})
        board = Switchboard(tmp_path/'data', tmp_path/'runtime', lines={line.line_id:line})
        entered, release = asyncio.Event(), asyncio.Event()
        async def missed(request):
            entered.set(); await release.wait(); return 'missed-id'
        board.missed = missed
        app = make_app(board); app.state.board = board
        add_demo_routes(app, board, line.scenarios, line, 'recorded', [])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1:8200', headers={'X-VB-Demo':'1'}) as client:
            first = asyncio.create_task(client.post('/demo/run/one'))
            await entered.wait()
            assert (await client.post('/demo/run/two')).status_code == 409
            assert list(line.bindings.values()) == ['one']
            release.set()
            assert (await first).json()['missed_call_id'] == 'missed-id'
        await board.stop()
    asyncio.run(run())
