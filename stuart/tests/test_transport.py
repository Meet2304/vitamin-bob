import asyncio
import json
import os
from pathlib import Path

import httpx
import numpy as np
import pytest
from pydantic import ValidationError

from stuart.audio import detect_dtmf
from stuart.contracts import Actions, Missed, Record, Sms, Sync, safe_wav
from stuart.fake_bob import make_fake
from stuart.lines import Adb, SimulatorLine
from stuart.service import Switchboard, make_app, segments
from stuart.sync_link import Codec, Receiver


def test_adb_sql_filter_stays_one_remote_argument(monkeypatch):
    import shlex
    import subprocess
    captured=[]
    def run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command,0,'No result found.','')
    monkeypatch.setattr(subprocess,'run',run)
    adb=Adb('adb.exe','demo-device')
    query='date>9999999999999'
    adb.run('shell','content','query','--where',query)
    assert shlex.split(captured[0][-1])==['content','query','--where',query]
    assert "'date>9999999999999'" in captured[0][-1]
    adb.run('devices','-l')
    assert captured[1]==['adb.exe','-s','demo-device','devices','-l']


def test_contract_rejects_invalid_action_order():
    terminal={"type":"keypad","action_id":"x","max_digits":1,"timeout_ms":1000,"terminator":None}
    assert len(Actions.model_validate({"actions":[terminal]}).actions)==1
    for invalid in ([],[terminal,terminal],[{"type":"play","action_id":"p","audio_path":"x"}]):
        with pytest.raises(ValidationError):
            Actions.model_validate({"actions":invalid})


def test_payload_limit_counts_utf8():
    Record(record_id="x",kind="triage",payload={"a":"x"*192})
    with pytest.raises(ValidationError):
        Record(record_id="x",kind="triage",payload={"a":"ह"*70})


def test_sms_encoding_and_multipart():
    assert segments("a"*160)==1
    assert segments("a"*161)==2
    assert segments("^"*80)==1
    assert segments("^"*81)==2
    assert segments("ह"*70)==1
    assert segments("ह"*71)==2
    assert segments("😀"*36)==2


def test_dtmf_and_speech_noise_rejection():
    t=np.arange(1280)/16000
    for lo,hi,key in [(697,1209,"1"),(770,1336,"5"),(941,1477,"#")]:
        signal=0.2*np.sin(2*np.pi*lo*t)+0.2*np.sin(2*np.pi*hi*t)
        assert detect_dtmf(signal)==key
    assert detect_dtmf(np.random.default_rng(4).normal(0,0.1,1280)) is None
    assert detect_dtmf(np.zeros(1280)) is None


def test_sync_drop_duplicate_restart_and_authenticated_ack(tmp_path):
    codec=Codec(os.urandom(32),"kevin-test")
    receiver=Receiver(tmp_path/"central.db",codec)
    record={"record_id":"record-one","kind":"triage","payload":{"t":"U","c":"B","x":"0123456789"*10}}
    frames=codec.frames(1,[record])
    assert all(len(f)<=160 for f in frames)
    assert len(frames)>1
    for frame in frames[1:]:
        assert receiver.receive(frame) is None
    receiver.db.close()
    receiver=Receiver(tmp_path/"central.db",codec)
    ack=receiver.receive(frames[0])
    assert codec.verify_ack(ack)==1
    assert len(receiver.rows())==1
    for frame in frames:
        assert codec.verify_ack(receiver.receive(frame))==1
    assert len(receiver.rows())==1
    altered=ack[:-3]+"AAAA"
    with pytest.raises(Exception):
        codec.verify_ack(altered)
    receiver.db.close()


def test_sync_tamper_fails_without_commit(tmp_path):
    codec=Codec(os.urandom(32))
    receiver=Receiver(tmp_path/"central.db",codec)
    frames=codec.frames(7,[{"record_id":"r","kind":"t","payload":{"t":"L"}}])
    prefix,body=frames[0].rsplit("|",1)
    frames[0]=prefix+"|"+("A" if body[0]!="A" else "B")+body[1:]
    with pytest.raises(Exception):
        for frame in frames:
            receiver.receive(frame)
    assert receiver.rows()==[]


async def wait_for(predicate,seconds=4):
    for _ in range(int(seconds/0.02)):
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("Timed out waiting for transport state")


def test_end_to_end_mock_call_sms_and_sync(tmp_path,monkeypatch):
    monkeypatch.setenv("VB_SYNC_DROP_FIRST","1")
    async def run():
        data,runtime=tmp_path/"data",tmp_path/"runtime"
        fake=make_fake(data,runtime)
        line=SimulatorLine("sim-1",runtime)
        board=Switchboard(data,runtime,lines={"sim-1":line})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake),base_url="http://mock",trust_env=False)
        await board.start()
        try:
            first=await board.missed(Missed(phone="+919000000001"))
            duplicate=await board.missed(Missed(phone="+919000000001"))
            assert first==duplicate
            await wait_for(lambda: board.store.one("SELECT status FROM missed WHERE id=?",(first,))["status"]=="done")
            event_rows=board.store.rows("SELECT payload FROM events WHERE call_id IS NOT NULL ORDER BY rowid")
            events=[json.loads(r["payload"]) for r in event_rows]
            assert [e["type"] for e in events]==["call_started","action_result","action_result","call_ended"]
            assert events[1]["digits"]=="1"
            recording=Path(events[2]["recording_path"])
            assert recording.is_file()
            safe_wav(recording,data/"recordings")
            assert events[-1]["reason"]=="completed"
            request=Sms(message_id="sms1",to="+919000000002",text="test",priority="normal")
            board.queue_sms(request)
            board.queue_sms(request)
            await wait_for(lambda: board.store.one("SELECT status FROM sms WHERE id='sms1'")["status"]=="delivered")
            assert len(board.store.rows("SELECT * FROM sms"))==1
            await board.queue_sync(Sync(records=[Record(record_id="rec1",kind="triage",payload={"t":"U"})]))
            await wait_for(lambda: board.store.one("SELECT status FROM sync WHERE id='rec1'")["status"]=="acked",6)
            assert len(board.central.rows())==1
            assert board.store.one("SELECT attempts FROM sync WHERE id='rec1'")["attempts"]==2
        finally:
            await board.stop()
    asyncio.run(run())


def test_bob_down_keeps_missed_call_without_callback(tmp_path):
    async def run():
        line=SimulatorLine("sim-1",tmp_path)
        board=Switchboard(tmp_path/"data",tmp_path/"runtime",lines={"sim-1":line})
        await board.client.aclose()
        async def failed(request):
            raise httpx.ConnectError("offline")
        board.client=httpx.AsyncClient(transport=httpx.MockTransport(failed))
        missed_id=await board.missed(Missed(phone="+919000000004"))
        row=board.store.one("SELECT * FROM missed WHERE id=?",(missed_id,))
        assert row["status"]=="pending" and row["decision"] is None
        assert board.store.rows("SELECT * FROM calls")==[]
        event=board.store.one("SELECT * FROM events WHERE id=?",(row["event_id"],))
        assert event["attempts"]==4
        await board.stop()
    asyncio.run(run())


def test_daily_cap_and_priority(tmp_path,monkeypatch):
    monkeypatch.setenv("VB_DAILY_SMS_CAP","1")
    async def run():
        fake=make_fake(tmp_path/"data",tmp_path/"runtime")
        board=Switchboard(tmp_path/"data",tmp_path/"runtime",lines={"sim-1":SimulatorLine("sim-1",tmp_path)})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        board.queue_sms(Sms(message_id="bulk",to="+919000000001",text="b",priority="bulk"))
        board.queue_sms(Sms(message_id="urgent",to="+919000000001",text="u",priority="urgent"))
        await board.start()
        try:
            await wait_for(lambda: all(r["status"] in ("delivered","failed") for r in board.store.rows("SELECT * FROM sms")))
            assert board.store.one("SELECT status FROM sms WHERE id='urgent'")["status"]=="delivered"
            assert board.store.one("SELECT status FROM sms WHERE id='bulk'")["status"]=="failed"
        finally:
            await board.stop()
    asyncio.run(run())


def test_http_contract_header_and_id_conflict(tmp_path):
    from fastapi.testclient import TestClient
    fake=make_fake(tmp_path/"data",tmp_path/"runtime")
    board=Switchboard(tmp_path/"data",tmp_path/"runtime",lines={})
    with TestClient(make_app(board)) as client:
        assert client.get("/v1/health").status_code==409
        headers={"X-VB-Contract":"0.2"}
        assert client.get("/v1/health",headers=headers).json()=={"ok":True,"module":"stuart"}
        request={"message_id":"m","to":"+919000000001","text":"one","priority":"normal"}
        assert client.post("/v1/sms",headers=headers,json=request).status_code==200
        request["text"]="two"
        assert client.post("/v1/sms",headers=headers,json=request).status_code==409


def test_three_lines_execute_simultaneously(tmp_path):
    class SlowLine(SimulatorLine):
        async def play(self,path,stop=None):
            await asyncio.sleep(0.15)
            self.check()
    async def run():
        fake=make_fake(tmp_path/'data',tmp_path/'runtime')
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={f'sim-{i}':SlowLine(f'sim-{i}',tmp_path) for i in range(1,4)})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        await board.start()
        try:
            for i in range(3):
                await board.missed(Missed(phone=f'+91900000001{i}',line_id='sim-1'))
            await wait_for(lambda: len(board.status()['active_calls'])==3)
            await wait_for(lambda: all(r['status']=='done' for r in board.store.rows('SELECT * FROM missed')))
            assert len({r['line_id'] for r in board.store.rows('SELECT * FROM calls')})==3
        finally:
            await board.stop()
    asyncio.run(run())


def test_callback_retry_exhaustion_reports_failure(tmp_path,monkeypatch):
    monkeypatch.setenv('VB_CALLBACK_RETRY_SECONDS','0.02')
    monkeypatch.setenv('VB_CALLBACK_MAX_ATTEMPTS','2')
    async def run():
        fake=make_fake(tmp_path/'data',tmp_path/'runtime')
        line=SimulatorLine('sim-1',tmp_path)
        line.dial_failure=True
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'sim-1':line})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        await board.start()
        try:
            missed=await board.missed(Missed(phone='+919000000050'))
            await wait_for(lambda: board.store.one('SELECT status FROM missed WHERE id=?',(missed,))['status']=='failed')
            events=[json.loads(r['payload']) for r in board.store.rows('SELECT payload FROM events')]
            failures=[e for e in events if e['type']=='callback_failed']
            assert len(failures)==1 and failures[0]['attempts']==2
            assert board.store.one('SELECT attempts FROM missed WHERE id=?',(missed,))['attempts']==2
        finally:
            await board.stop()
    asyncio.run(run())


def test_bob_timeout_ends_call_and_preserves_failure_event(tmp_path,monkeypatch):
    monkeypatch.setenv('VB_BOB_TIMEOUT_SECONDS','0.15')
    async def run():
        from stuart.audio import tone
        data=tmp_path/'data'
        tone(data/'prompts'/'system'/'fallback.wav')
        board=Switchboard(data,tmp_path/'runtime',lines={'sim-1':SimulatorLine('sim-1',tmp_path)})
        await board.client.aclose()
        async def response(request):
            event=json.loads(request.content)
            if event['type']=='missed_call':
                return httpx.Response(200,json={'ack':True,'callback':True})
            if event['type']=='call_started':
                await asyncio.sleep(2)
            return httpx.Response(200,json={'ack':True})
        board.client=httpx.AsyncClient(transport=httpx.MockTransport(response))
        await board.start()
        try:
            missed=await board.missed(Missed(phone='+919000000060'))
            await wait_for(lambda: board.store.one('SELECT status FROM missed WHERE id=?',(missed,))['status']=='failed')
            call=board.store.one('SELECT * FROM calls')
            assert call['reason']=='failed' and call['ended_at']
            assert board.lines['sim-1'].state=='idle'
            assert board.store.one("SELECT response FROM events WHERE payload LIKE '%call_ended%'")['response']
        finally:
            await board.stop()
    asyncio.run(run())


def test_bob_can_decline_callback(tmp_path):
    async def run():
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'sim-1':SimulatorLine('sim-1',tmp_path)})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'ack':True,'callback':False})))
        await board.start()
        try:
            missed=await board.missed(Missed(phone='+919000000070'))
            await asyncio.sleep(0.15)
            assert board.store.one('SELECT decision FROM missed WHERE id=?',(missed,))['decision']==0
            assert board.status()['queue']==[] and board.status()['active_calls']==[]
        finally:
            await board.stop()
    asyncio.run(run())


def test_caller_hangup_during_keypad_reports_once(tmp_path):
    class WaitingLine(SimulatorLine):
        async def keypad(self,action):
            while not self.disconnected:
                await asyncio.sleep(0.02)
            self.check()
    async def run():
        fake=make_fake(tmp_path/'data',tmp_path/'runtime')
        line=WaitingLine('sim-1',tmp_path)
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'sim-1':line})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        await board.start()
        try:
            missed=await board.missed(Missed(phone='+919000000080'))
            await wait_for(lambda: any(c['current_action']=='keypad' for c in board.status()['active_calls']))
            line.disconnected=True
            await wait_for(lambda: bool(board.store.one('SELECT ended_at FROM calls')['ended_at']))
            events=[json.loads(r['payload']) for r in board.store.rows('SELECT payload FROM events')]
            results=[e for e in events if e['type']=='action_result']
            assert len(results)==1 and results[0]['status']=='caller_hung_up'
            assert board.store.one('SELECT reason FROM calls')['reason']=='caller_hung_up'
            assert len([e for e in events if e['type']=='call_ended'])==1
        finally:
            await board.stop()
    asyncio.run(run())


def test_queued_callback_survives_restart(tmp_path):
    async def run():
        fake=make_fake(tmp_path/'data',tmp_path/'runtime')
        def board():
            return Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'sim-1':SimulatorLine('sim-1',tmp_path)})
        first=board()
        await first.client.aclose()
        first.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        missed=await first.missed(Missed(phone='+919000000090'))
        assert first.store.one('SELECT status FROM missed WHERE id=?',(missed,))['status']=='queued'
        await first.stop()
        second=board()
        await second.client.aclose()
        second.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=fake))
        await second.start()
        try:
            await wait_for(lambda: second.store.one('SELECT status FROM missed WHERE id=?',(missed,))['status']=='done')
            assert len(second.store.rows('SELECT * FROM calls'))==1
        finally:
            await second.stop()
    asyncio.run(run())


def test_start_recovers_interrupted_call_without_waiting_for_bob(tmp_path):
    async def run():
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'sim-1':SimulatorLine('sim-1',tmp_path)})
        board.store.execute("INSERT INTO missed(id,phone,line_id,received_at,status,attempts,decision) VALUES('m','+919000000099','sim-1','2026-10-04T00:00:00+00:00','calling',1,1)")
        board.store.execute("INSERT INTO calls(id,missed_id,phone,line_id,started_at) VALUES('c','m','+919000000099','sim-1','2026-10-04T00:00:00+00:00')")
        await board.client.aclose()
        async def slow(request):
            await asyncio.sleep(5)
            return httpx.Response(200,json={'ack':True})
        board.client=httpx.AsyncClient(transport=httpx.MockTransport(slow))
        await asyncio.wait_for(board.start(),0.2)
        assert board.store.one("SELECT reason FROM calls WHERE id='c'")['reason']=='failed'
        assert board.store.one("SELECT status FROM missed WHERE id='m'")['status']=='failed'
        await board.stop()
    asyncio.run(run())


def test_central_concurrent_duplicates_commit_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    codec=Codec(os.urandom(32))
    receiver=Receiver(tmp_path/'central.db',codec)
    frames=codec.frames(10,[{'record_id':'same-record','kind':'triage','payload':{'t':'M'}}])
    def deliver(_):
        ack=None
        for frame in frames:
            ack=receiver.receive(frame) or ack
        return ack
    with ThreadPoolExecutor(max_workers=6) as pool:
        acknowledgements=list(pool.map(deliver,range(12)))
    assert all(codec.verify_ack(ack)==10 for ack in acknowledgements)
    assert len(receiver.rows())==1
    receiver.db.close()
