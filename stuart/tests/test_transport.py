import asyncio
import json
import os
from pathlib import Path

import httpx
import numpy as np
import pytest
from pydantic import ValidationError

from stuart.audio import detect_dtmf, input_chunks, play_blocking, tone
from stuart.contracts import Actions, Missed, Record, Sms, Sync, safe_wav
from stuart.fake_bob import make_fake
from stuart.lines import Adb, AndroidLine, CallerHungUp, DialFailed, SimulatorLine, live_telecom_audio_route, live_telecom_states
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


def test_live_call_state_excludes_history_and_other_sections():
    text='CallsManager: \n  mCalls: \n    Call TC@1: state=ACTIVE\n  mCallAudioManager:\n    History: state=DIALING\nHistorical calls:\n  state=DISCONNECTED\n'
    assert live_telecom_states(text)==['ACTIVE']
    idle='CallsManager: \n  mCalls: \n  mCallAudioManager:\n    History: state=ACTIVE\n'
    assert live_telecom_states(idle)==[]
    assert live_telecom_states('History: state=ACTIVE') is None


def test_current_audio_route_excludes_pending_and_history():
    text = ('CallsManager:\n  mCallAudioManager:\n    mCallAudioRouteAdapter:\n'
            '      SamsungCallAudioRouteController\n'
            '      Current route: AudioRoute[Type=TYPE_EARPIECE, Address=invalid]\n'
            '      Pending route: AudioRoute[Type=TYPE_BLUETOOTH_SCO, Address=masked]\n'
            '    mOtherSection:\n      Current route: AudioRoute[Type=TYPE_SPEAKER, Address=invalid]\n')
    assert live_telecom_audio_route(text) == 'TYPE_EARPIECE'
    assert live_telecom_audio_route(text.replace('TYPE_EARPIECE', 'TYPE_BLUETOOTH_SCO')) == 'TYPE_BLUETOOTH_SCO'
    assert live_telecom_audio_route('History: Current route: AudioRoute[Type=TYPE_BLUETOOTH_SCO, Address=masked]') is None


@pytest.mark.parametrize('scenario', ['busy', 'unknown', 'answer', 'no_answer', 'timeout'])
def test_android_answer_wait_and_call_ownership(tmp_path, monkeypatch, scenario):
    import stuart.lines as lines
    monkeypatch.setattr(lines, 'check_capture_device', lambda device: None)
    monkeypatch.setattr(lines, 'check_playback_device', lambda device: None)
    monkeypatch.setenv('VB_ANDROID_ANSWER_TIMEOUT_SECONDS', '0' if scenario == 'timeout' else '2')
    def snapshot(state=''):
        return 'CallsManager: \n  mCalls: \n' + (f'    Call: state={state}\n' if state else '') + '  mCallAudioManager:\n'
    snapshots = {
        'busy': [snapshot('ACTIVE')], 'unknown': ['Historical: state=ACTIVE'],
        'answer': [snapshot(), snapshot('DIALING'), snapshot('ACTIVE')],
        'no_answer': [snapshot(), snapshot('DIALING'), snapshot()],
        'timeout': [snapshot()],
    }[scenario]
    commands = []
    class Device:
        def run(self, *args):
            commands.append(args)
            if args == ('get-state',):
                return 'device'
            if args == ('shell', 'dumpsys', 'telecom'):
                return snapshots.pop(0)
            return ''
    async def run():
        line = AndroidLine('android-test', tmp_path, Device())
        line.input_device, line.output_device = 'receiver', 'transmitter'
        async def monitor():
            await asyncio.Future()
        line.monitor = monitor
        if scenario == 'answer':
            await line.place('+15550100100')
            assert line.observed_active and not snapshots
        else:
            with pytest.raises(DialFailed) as error:
                await line.place('+15550100100')
            if scenario in ('no_answer', 'timeout'):
                assert error.value.reason == 'no_answer'
        await line.hangup()
        await line.hangup()  # Only the call owned by Stuart is ended, once.
        if line.monitor_task:
            await asyncio.gather(line.monitor_task, return_exceptions=True)
        owned = scenario in ('answer', 'no_answer', 'timeout')
        assert sum(args[:3] == ('shell', 'am', 'start') for args in commands) == int(owned)
        assert commands.count(('shell', 'input', 'keyevent', '6')) == int(owned)
    asyncio.run(run())


@pytest.mark.parametrize('scenario', ['stable', 'timeout', 'disconnected'])
def test_android_requires_stable_audio_route_before_prompts(tmp_path, monkeypatch, scenario):
    import stuart.lines as lines
    monkeypatch.setattr(lines, 'check_capture_device', lambda device: None)
    monkeypatch.setattr(lines, 'check_playback_device', lambda device: None)
    monkeypatch.setenv('VB_ANDROID_REQUIRED_AUDIO_ROUTE', 'TYPE_BLUETOOTH_SCO')
    monkeypatch.setenv('VB_ANDROID_AUDIO_ROUTE_TIMEOUT_SECONDS', '0' if scenario == 'timeout' else '2')
    original_sleep = asyncio.sleep
    async def immediate_sleep(seconds):
        await original_sleep(0)
    monkeypatch.setattr(lines.asyncio, 'sleep', immediate_sleep)
    def snapshot(state, route='TYPE_EARPIECE'):
        return ('CallsManager:\n  mCalls:\n' + (f'    Call: state={state}\n' if state else '') +
                '  mCallAudioManager:\n    mCallAudioRouteAdapter:\n' +
                f'      Current route: AudioRoute[Type={route}, Address=masked]\n')
    states = [snapshot(''), snapshot('ACTIVE')]
    if scenario == 'stable':
        states += ([snapshot('ACTIVE', 'TYPE_BLUETOOTH_SCO')] * 2 + [snapshot('ACTIVE')] +
                   [snapshot('ACTIVE', 'TYPE_BLUETOOTH_SCO')] * 5)
    elif scenario == 'disconnected':
        states += [snapshot('')]
    commands = []
    class Device:
        def run(self, *args):
            commands.append(args)
            if args == ('get-state',):
                return 'device'
            if args == ('shell', 'dumpsys', 'telecom'):
                return states.pop(0)
            return ''
    async def run():
        line = AndroidLine('android-test', tmp_path, Device())
        line.input_device, line.output_device = 'receiver', 'transmitter'
        async def monitor():
            await asyncio.Future()
        line.monitor = monitor
        if scenario == 'stable':
            await line.place('+15550100100')
            assert not states  # A brief Bluetooth route must not open prompts.
        else:
            with pytest.raises(DialFailed if scenario == 'timeout' else CallerHungUp):
                await line.place('+15550100100')
        await line.hangup()
        await asyncio.gather(line.monitor_task, return_exceptions=True)
        assert commands.count(('shell', 'input', 'keyevent', '6')) == 1
    asyncio.run(run())


@pytest.mark.skipif(os.name!='nt',reason='Windows COM audio lifecycle')
@pytest.mark.parametrize('result,uninitializes',[(0,1),(1,1),(-2147417850,0),(-2147221008,0)])
def test_windows_audio_thread_balances_com_even_on_failure(monkeypatch,result,uninitializes):
    import ctypes
    from types import SimpleNamespace
    from stuart.audio import windows_audio_thread
    calls=[]
    class Initialize:
        def __call__(self,pointer,flags):
            calls.append('initialize')
            return result
    api=SimpleNamespace(CoInitializeEx=Initialize(),CoUninitialize=lambda:calls.append('uninitialize'))
    monkeypatch.setattr(ctypes,'WinDLL',lambda name:api)
    if result==-2147221008:
        with pytest.raises(OSError,match='COM initialization'):
            with windows_audio_thread():
                pytest.fail('Failed COM initialization must prevent audio access')
    else:
        with pytest.raises(ValueError,match='audio failure'):
            with windows_audio_thread():
                raise ValueError('audio failure')
    assert calls.count('initialize')==1
    assert calls.count('uninitialize')==uninitializes


def test_callback_playback_preserves_pcm_and_pads_last_buffer(tmp_path,monkeypatch):
    import sounddevice as sd
    import wave
    played=[]
    monkeypatch.setattr(sd,'query_devices',lambda *args:{'hostapi':0})
    monkeypatch.setattr(sd,'query_hostapis',lambda *args:{'name':'Test'})
    class Output:
        def __init__(self,callback,finished_callback,**kwargs):
            self.callback,self.finished=callback,finished_callback
        def __enter__(self):
            # Variable host buffer sizes, including a partial last buffer.
            for frames in [357,901,513,127]:
                buffer=np.empty((frames,1),dtype='int16')
                try:
                    self.callback(buffer,frames,None,None)
                except sd.CallbackStop:
                    played.append(buffer.copy())
                    self.finished()
                    break
                played.append(buffer.copy())
            return self
        def __exit__(self,*args):
            pass
    monkeypatch.setattr(sd,'OutputStream',Output)
    path=tone(tmp_path/'prompt.wav',0.1)
    play_blocking(path)
    with wave.open(str(path),'rb') as wav:
        expected=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2')
    actual=np.concatenate(played).reshape(-1)
    assert np.array_equal(actual[:len(expected)],expected)
    assert np.all(actual[len(expected):]==0)


def test_capture_callback_reports_driver_overflow(monkeypatch):
    import sounddevice as sd
    monkeypatch.setattr(sd,'query_devices',lambda *args:{'hostapi':0})
    monkeypatch.setattr(sd,'query_hostapis',lambda *args:{'name':'Test'})
    class Input:
        active=True
        def __init__(self,callback,**kwargs):
            self.callback=callback
        def __enter__(self):
            flags=sd.CallbackFlags()
            flags.input_overflow=True
            with pytest.raises(sd.CallbackAbort):
                self.callback(np.zeros((800,1),dtype='int16'),800,None,flags)
            self.active=False
            return self
        def __exit__(self,*args):
            pass
    monkeypatch.setattr(sd,'InputStream',Input)
    with input_chunks() as read:
        with pytest.raises(OSError,match='overflow'):
            read()


def test_native_wasapi_preserves_stereo_pcm_and_honors_cancel(tmp_path,monkeypatch):
    import wave
    import stuart.audio as audio
    played=[]
    class Player:
        buffersize=1600
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def play(self,data): played.append(data.copy())
    class Speaker:
        channels=2
        def player(self,**kwargs):
            assert kwargs['samplerate']==16000 and kwargs['channels']==2
            return Player()
    monkeypatch.setattr(audio,'wasapi_speaker',lambda device:Speaker())
    path=tone(tmp_path/'native.wav',0.1)
    play_blocking(path,'wasapi:test')
    with wave.open(str(path),'rb') as wav:
        expected=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype('float32')/32768
    actual=np.concatenate(played)
    assert np.array_equal(actual[:len(expected),0],expected)
    assert np.array_equal(actual[:len(expected),1],expected)
    assert np.all(actual[len(expected):]==0)
    played.clear()
    play_blocking(path,'wasapi:test',stopped=lambda:True)
    assert not played


def test_loopback_captures_stereo_then_downmixes_to_contract_pcm(monkeypatch):
    import sys
    from types import SimpleNamespace
    requests=[]
    class Recorder:
        def __enter__(self):
            return self
        def __exit__(self,*args):
            pass
        def record(self,numframes):
            return np.array([[0.5,0.25],[-0.5,-0.25],[2,2]],dtype='float32')
    class Mic:
        name,id,isloopback,channels='Test speakers','test',True,2
        def recorder(self,**kwargs):
            requests.append(kwargs)
            return Recorder()
    monkeypatch.setitem(sys.modules,'soundcard',SimpleNamespace(all_microphones=lambda **kwargs:[Mic()]))
    with input_chunks('loopback:Test speakers') as read:
        pcm=read()
    assert requests[0]['channels']==2 and requests[0]['samplerate']==16000
    assert pcm.dtype==np.int16 and pcm.shape==(3,1)
    assert pcm[:,0].tolist()==[12288,-12288,32767]
    with pytest.raises(ValueError,match='exact speaker'):
        with input_chunks('loopback:unknown'):
            pass


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


def test_sms_webhook_auth_failure_reason_and_duplicate_receipts(tmp_path,monkeypatch):
    monkeypatch.setenv('VB_SMS_WEBHOOK_TOKEN','test-secret')
    async def run():
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={'ack':True})))
        board.queue_sms(Sms(message_id='m',to='+15550100100',text='test',priority='normal'))
        payload={'event':'sms:failed','payload':{'messageId':'m','reason':'SEND_SMS denied'}}
        app=make_app(board)
        app.state.board=board  # ASGITransport does not run the application lifespan.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                    base_url='http://stuart') as client:
            assert (await client.post('/android/smsgate',json=payload)).status_code==403
            assert board.store.one("SELECT status,error FROM sms WHERE id='m'")=={'status':'queued','error':None}
            url='/android/smsgate?token=test-secret'
            assert (await client.post(url,json=payload)).status_code==200
            assert board.store.one("SELECT status,error FROM sms WHERE id='m'")=={'status':'failed','error':'SEND_SMS denied'}
            payload['payload']['reason']='x'*1100
            assert (await client.post(url,json=payload)).status_code==200
            assert len(board.store.one("SELECT error FROM sms WHERE id='m'")['error'])==1024
            assert len(board.store.rows('SELECT * FROM events'))==1
            payload['payload']['messageId']='unknown'
            assert (await client.post(url,json=payload)).status_code==200
            assert len(board.store.rows('SELECT * FROM events'))==1
            payload={'event':'sms:delivered','payload':{'messageId':'m'}}
            assert (await client.post(url,json=payload)).status_code==200
            payload={'event':'sms:failed','payload':{'messageId':'m','reason':'late failure'}}
            assert (await client.post(url,json=payload)).status_code==200
            assert board.store.one("SELECT status FROM sms WHERE id='m'")['status']=='delivered'
            assert board.store.one("SELECT error FROM sms WHERE id='m'")['error']!='late failure'
            assert len(board.store.rows('SELECT * FROM events'))==2
        await board.stop()
    asyncio.run(run())


@pytest.mark.parametrize('state,expected',[('Pending',None),('Sent','sent'),('Delivered','delivered'),('Failed','failed')])
def test_android_sms_receipt_reads_only_known_id(tmp_path,monkeypatch,state,expected):
    monkeypatch.setenv('VB_SMS_GATE_USER','test-user')
    monkeypatch.setenv('VB_SMS_GATE_PASSWORD','test-password')
    monkeypatch.setenv('VB_SMS_GATE_URL','http://gateway')
    original_client=httpx.AsyncClient
    def response(request):
        assert request.method=='GET' and request.url.path=='/message/known-id'
        assert request.headers['authorization'].startswith('Basic ')
        return httpx.Response(200,json={'state':state,'recipients':[{'error':'permission denied' if state=='Failed' else None}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original_client(
        transport=httpx.MockTransport(response),**kwargs))
    async def run():
        line=AndroidLine('android-1',tmp_path,Adb('unused'))
        assert await line.sms_receipt('known-id')==(expected,'permission denied' if state=='Failed' else None)
    asyncio.run(run())


def test_sms_poll_recovers_receipt_without_resending(tmp_path):
    class ReceiptLine(AndroidLine):
        async def send_sms(self,request):
            raise AssertionError('Receipt recovery must not send')
        async def sms_receipt(self,message_id):
            assert message_id=='accepted'
            return 'delivered',None
    async def run():
        line=ReceiptLine('android-1',tmp_path,Adb('unused'))
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={line.line_id:line})
        await board.client.aclose()
        board.client=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request:httpx.Response(200,json={'ack':True})))
        for message_id in ('accepted','failed','queued'):
            board.queue_sms(Sms(message_id=message_id,to='+15550100100',text='test',priority='normal'))
            board.store.execute('UPDATE sms SET status=?,line_id=? WHERE id=?',(message_id,line.line_id,message_id))
        board.spawn(board.sms_receipts())
        try:
            await wait_for(lambda:board.store.one("SELECT status FROM sms WHERE id='accepted'")['status']=='delivered')
            assert board.store.one("SELECT status FROM sms WHERE id='failed'")['status']=='failed'
            assert board.store.one("SELECT status FROM sms WHERE id='queued'")['status']=='queued'
            events=[json.loads(r['payload']) for r in board.store.rows('SELECT payload FROM events')]
            assert len(events)==1 and events[0]['status']=='delivered'
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
