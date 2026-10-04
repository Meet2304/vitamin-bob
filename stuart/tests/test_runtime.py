import asyncio
import json
from pathlib import Path
import socket

import httpx
import pytest
from pydantic import ValidationError

from stuart.contracts import IncomingSms, Sms, normalize_phone
from stuart.gateway import GatewayBridge
from stuart.lines import AndroidLine, SimulatorLine
from stuart.runtime import InstanceLock, Profile, backup, restore
from stuart.service import Switchboard, make_app


def profile(tmp_path,**kwargs):
    return Profile(**({'data_dir':tmp_path/'data','runtime_dir':tmp_path/'runtime'}|kwargs))


def test_profile_isolates_modes_and_requires_scoped_hardware(tmp_path):
    p=profile(tmp_path)
    env=p.environment({'PATH':'kept','VB_ANDROID_ENABLED':'1','VB_PHONE_ALLOWLIST':'bad',
        'VB_SMS_LINE_ID':'android-1','VB_SYNC_TRANSPORT':'sms','VB_SMS_GATE_PASSWORD':'secret'})
    assert env['VB_ANDROID_ENABLED']=='0' and env['VB_SYNC_TRANSPORT']=='loopback'
    assert 'VB_SMS_LINE_ID' not in env and 'VB_PHONE_ALLOWLIST' not in env
    assert env['PATH']=='kept' and env['VB_SMS_GATE_PASSWORD']=='secret'
    with pytest.raises(ValidationError):
        profile(tmp_path,mode='hardware')
    with pytest.raises(ValidationError):
        profile(tmp_path,bob_url='http://example.com:8100')
    with pytest.raises(ValidationError):
        profile(tmp_path,port=8100)
    with pytest.raises(ValidationError):
        profile(tmp_path,data_dir=Path('relative'))
    p=profile(tmp_path,mode='hardware',allowed_phones=['+15550100100'])
    env=p.environment({})
    assert env['VB_SIM_LINES']=='0' and env['VB_ANDROID_CALLS_ENABLED']=='0'
    assert env['VB_SMS_SEND_ENABLED']=='0' and env['VB_MANAGE_SMS_GATEWAY']=='1'


def test_instance_lock_releases_after_exit(tmp_path):
    path=tmp_path/'instance.lock'
    with InstanceLock(path):
        with pytest.raises(RuntimeError):
            with InstanceLock(path):
                pass
    with InstanceLock(path):
        pass


def test_backup_restore_preserves_queue_and_key_and_refuses_overwrite(tmp_path):
    from stuart.storage import Store
    p=profile(tmp_path/'original')
    store=Store(p.data_dir/'stuart.db')
    store.execute("INSERT INTO meta VALUES('proof','saved')")
    p.runtime_dir.mkdir(parents=True)
    (p.runtime_dir/'demo-sync.key').write_bytes(b'k'*32)
    result=backup(p)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    recovery=profile(tmp_path/'recovery',port=port)
    assert restore(recovery,result['backup'])['start_automatically'] is False
    recovered=Store(recovery.data_dir/'stuart.db')
    assert recovered.one("SELECT value FROM meta WHERE key='proof'")['value']=='saved'
    assert (recovery.runtime_dir/'demo-sync.key').read_bytes()==b'k'*32
    with pytest.raises(ValueError,match='fresh'):
        restore(recovery,result['backup'])
    store.close();recovered.close()


@pytest.mark.parametrize('sender,country,expected',[
    ('(412) 555-0100','+1','+14125550100'),('14125550100','+1','+14125550100'),
    ('+14125550100','+1','+14125550100'),('00919800000001','+91','+919800000001'),
    ('919800000001','+91','+919800000001'),('9800000001','+91','+919800000001')])
def test_carrier_sender_normalization(sender,country,expected):
    assert normalize_phone(sender,country)==expected


def test_inbound_webhook_normalizes_and_deduplicates(tmp_path,monkeypatch):
    monkeypatch.setenv('VB_SMS_WEBHOOK_TOKEN','token')
    monkeypatch.setenv('VB_COUNTRY_CODE','+1')
    monkeypatch.setenv('VB_PHONE_ALLOWLIST','["+14125550100"]')
    async def run():
        b=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'android-1':SimulatorLine('android-1',tmp_path)})
        await b.client.aclose()
        seen=[]
        def ack(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={'ack':True})
        b.client=httpx.AsyncClient(transport=httpx.MockTransport(ack))
        app=make_app(b);app.state.board=b
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://stuart') as c:
            payload={'event':'sms:received','payload':{'messageId':'one','sender':'4125550100','message':'test'}}
            for _ in range(2):
                r=await c.post('/android/smsgate?token=token',json=payload)
                assert r.status_code==200
            assert len(seen)==1 and seen[0]['phone']=='+14125550100'
            payload['payload'].update(messageId='two',sender='+14125550101')
            assert (await c.post('/android/smsgate?token=token',json=payload)).status_code==200
            assert len(seen)==1 and len(b.store.rows('SELECT * FROM incoming'))==1
        await b.stop()
    asyncio.run(run())


def test_disabled_send_does_not_drain_preexisting_queue(tmp_path,monkeypatch):
    async def run():
        b=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={'sim-1':SimulatorLine('sim-1',tmp_path)})
        b.queue_sms(Sms(message_id='queued',to='+15550100100',text='test',priority='normal'))
        b.sms_send_enabled=False
        with pytest.raises(ValueError,match='disabled'):
            b.queue_sms(Sms(message_id='new',to='+15550100100',text='test',priority='normal'))
        b.spawn(b.sms_worker())
        await asyncio.sleep(.15)
        assert b.store.one("SELECT status FROM sms WHERE id='queued'")['status']=='queued'
        await b.stop()
    asyncio.run(run())


@pytest.mark.parametrize('health_mode',['healthy','offline','cellular_failure'])
def test_gateway_repairs_only_own_hooks_and_usb_mappings(tmp_path,monkeypatch,health_mode):
    for key,value in {'VB_SMS_GATE_URL':'http://127.0.0.1:18080','VB_STUART_PORT':'18210',
        'VB_SMS_GATE_USER':'test','VB_SMS_GATE_PASSWORD':'secret','VB_SMS_WEBHOOK_TOKEN':'token'}.items():
        monkeypatch.setenv(key,value)
    class Device:
        def __init__(self):
            self.maps={'forward':{'tcp:18080':'tcp:8080'},'reverse':{}}
        def run(self,*args):
            if args==('get-state',):return 'device'
            mode,op,*rest=args
            if op=='--list':return '\n'.join('device '+k+' '+v for k,v in self.maps[mode].items())
            if op=='--no-rebind':self.maps[mode][rest[0]]=rest[1]
            if op=='--remove':self.maps[mode].pop(rest[0])
            return ''
    async def run():
        device=Device()
        line=AndroidLine('android-1',tmp_path,device)
        board=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={line.line_id:line})
        bridge=GatewayBridge(board)
        hooks={'unrelated':{'id':'unrelated','event':'sms:received','url':'https://example.com/hook'}}
        settings={'webhooks':{'internet_required':True}}
        def response(request):
            if request.url.path=='/health':
                if health_mode=='healthy':return httpx.Response(200,json={'status':'pass'})
                checks={'connection:status':{'status':'fail'},'connection:transport':{'status':'fail'}}
                if health_mode=='cellular_failure':checks['connection:cellular']={'status':'fail'}
                return httpx.Response(500,json={'status':'fail','checks':checks})
            if request.url.path=='/settings':
                if request.method=='PATCH':
                    assert json.loads(request.content)=={'webhooks':{'internet_required':False}}
                    settings['webhooks']['internet_required']=False
                return httpx.Response(200,json=settings)
            if request.method=='GET':return httpx.Response(200,json=list(hooks.values()))
            if request.method=='POST':
                row=json.loads(request.content);hooks[row['id']]=row
                return httpx.Response(201,json=row)
            if request.method=='DELETE':
                hooks.pop(request.url.path.rsplit('/',1)[1]);return httpx.Response(204)
            raise AssertionError('Unexpected operation')
        original=httpx.AsyncClient
        monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(response),**kwargs))
        if health_mode=='cellular_failure':
            with pytest.raises(httpx.HTTPStatusError):
                await bridge.ensure()
            assert len(hooks)==1 and not bridge.state['ready']
            await bridge.close()
            await board.stop()
            return
        await bridge.ensure()
        assert bridge.state['ready'] and len(hooks)==5
        assert settings['webhooks']['internet_required'] is False
        hooks.pop(bridge.hooks[0]['id']);device.maps['reverse'].clear()
        await bridge.ensure()
        assert len(hooks)==5 and device.maps['reverse']['tcp:18210']=='tcp:18210'
        await bridge.close()
        assert list(hooks)==['unrelated']
        assert device.maps['forward']=={'tcp:18080':'tcp:8080'} and not device.maps['reverse']
        await board.stop()
    asyncio.run(run())


@pytest.mark.parametrize('caller,enabled,reject',[
    ('5550100100',True,True),('+15550100101',True,False),('',True,False),('5550100100',False,False)])
def test_scoped_phone_poll_leaves_other_calls_alone(tmp_path,monkeypatch,caller,enabled,reject):
    monkeypatch.setenv('VB_PHONE_ALLOWLIST','["+15550100100"]')
    monkeypatch.setenv('VB_COUNTRY_CODE','+1')
    monkeypatch.setenv('VB_ANDROID_CALLS_ENABLED',str(int(enabled)))
    async def run():
        commands=[]
        class Device:
            def run(self,*args):
                commands.append(args)
                if args==('get-state',):return 'device'
                if args==('shell','dumpsys','telephony.registry'):
                    return f'mCallState=1\nmCallIncomingNumber={caller}\n'
                return 'No result found.'
        line=AndroidLine('android-1',tmp_path,Device())
        b=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={line.line_id:line})
        b.spawn(b.poll_android(line))
        try:
            for _ in range(100):
                if (not enabled and commands) or any(c[:3]==('shell','content','query') for c in commands):break
                await asyncio.sleep(.01)
            assert commands
            assert (('shell','input','keyevent','6') in commands)==reject
            if not enabled:
                assert all(c==('get-state',) for c in commands)
        finally:
            await b.stop()
    asyncio.run(run())


def test_readiness_reports_bob_down_without_changing_health_contract(tmp_path):
    async def run():
        b=Switchboard(tmp_path/'data',tmp_path/'runtime',lines={})
        await b.client.aclose()
        b.client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(503)))
        app=make_app(b);app.state.board=b
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://stuart') as c:
            assert (await c.get('/v1/health',headers={'X-VB-Contract':'0.2'})).json()=={'ok':True,'module':'stuart'}
            r=await c.get('/ready')
            assert r.status_code==503 and r.json()['bob'] is False
        await b.stop()
    asyncio.run(run())
