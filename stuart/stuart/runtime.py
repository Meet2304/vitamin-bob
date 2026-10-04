"""Validated local profiles, single-instance supervision, and readiness diagnostics."""
import json
import os
from pathlib import Path
import socket
import shutil
import sqlite3
import subprocess
import sys
import time
import wave
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import safe_wav

MODULE=Path(__file__).resolve().parents[1]


class Profile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode:Literal['simulator','hardware']='simulator'
    data_dir:Path
    runtime_dir:Path
    port:int=Field(default=8200,ge=1024,le=65535)
    bob_url:str='http://127.0.0.1:8100'
    hub_id:str=Field(default='kevin-demo',pattern=r'^[A-Za-z0-9_-]{1,16}$')
    simulator_lines:int=Field(default=3,ge=1,le=16)
    calls_enabled:bool=False
    sms_send_enabled:bool=False
    sms_receive_enabled:bool=True
    allowed_phones:list[str]=Field(default_factory=list)
    country_code:str=Field(default='+91',pattern=r'^\+[1-9]\d{0,3}$')
    adb_path:Path=MODULE/'runtime/tools/platform-tools/adb.exe'
    android_serial:str|None=None
    line_phone:str|None=Field(default=None,pattern=r'^\+[1-9]\d{6,14}$')
    gateway_port:int=Field(default=18080,ge=1024,le=65535)
    audio_input:str='loopback:Speaker (Realtek(R) Audio)'
    audio_output:str='wasapi:CABLE Input (VB-Audio Virtual Cable)'
    daily_sms_cap:int=Field(default=10,ge=1,le=10000)
    callback_max_attempts:int=Field(default=1,ge=1,le=5)
    sync_transport:Literal['loopback','sms']='loopback'
    central_phone:str|None=None
    max_restarts:int=Field(default=3,ge=0,le=10)

    @field_validator('data_dir','runtime_dir','adb_path')
    @classmethod
    def absolute_path(cls,value):
        if not value.is_absolute():
            raise ValueError('Use absolute paths')
        return value.resolve()

    @field_validator('bob_url')
    @classmethod
    def local_bob(cls,value):
        url=urlsplit(value)
        if url.scheme!='http' or url.hostname!='127.0.0.1' or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
            raise ValueError('Bob must use HTTP on 127.0.0.1')
        return value.rstrip('/')

    @field_validator('allowed_phones')
    @classmethod
    def phones(cls,value):
        import re
        if any(not re.fullmatch(r'\+[1-9]\d{6,14}',phone) for phone in value):
            raise ValueError('Test peers must be E.164 phone numbers')
        return sorted(set(value))

    @model_validator(mode='after')
    def distinct_ports(self):
        ports=[self.port,urlsplit(self.bob_url).port or 80]
        if self.mode=='hardware':
            ports.append(self.gateway_port)
            if not self.allowed_phones:
                raise ValueError('Hardware PoC profile requires at least one allowed test phone')
        if len(ports)!=len(set(ports)):
            raise ValueError('Bob, Stuart, and SMS gateway require distinct ports')
        if self.sync_transport=='sms' and (not self.central_phone or self.central_phone not in self.allowed_phones):
            raise ValueError('SMS Central must be one of the allowed peers')
        return self

    def environment(self,parent=None):
        parent=dict(os.environ if parent is None else parent)
        secrets={k:parent[k] for k in ('VB_SMS_GATE_USER','VB_SMS_GATE_PASSWORD','VB_SMS_WEBHOOK_TOKEN','VB_OPERATOR_TOKEN','VB_SYNC_KEY_HEX') if k in parent}
        env={k:v for k,v in parent.items() if not k.startswith('VB_')}
        env.update(secrets)
        hardware=self.mode=='hardware'
        env.update(VB_DATA_DIR=str(self.data_dir),VB_RUNTIME_DIR=str(self.runtime_dir),
            VB_BOB_URL=self.bob_url,VB_STUART_URL=f'http://127.0.0.1:{self.port}',VB_STUART_PORT=str(self.port),
            VB_HUB_ID=self.hub_id,VB_SIM_LINES='0' if hardware else str(self.simulator_lines),VB_SIM_MODE='scripted',
            VB_ANDROID_ENABLED=str(int(hardware)),VB_ANDROID_CALLS_ENABLED=str(int(self.calls_enabled)),
            VB_SMS_SEND_ENABLED=str(int(self.sms_send_enabled)),VB_SMS_RECEIVE_ENABLED=str(int(self.sms_receive_enabled)),
            VB_MANAGE_SMS_GATEWAY=str(int(hardware)),VB_COUNTRY_CODE=self.country_code,
            VB_ADB=str(self.adb_path),VB_SMS_GATE_URL=f'http://127.0.0.1:{self.gateway_port}',
            VB_AUDIO_INPUT=self.audio_input,VB_AUDIO_OUTPUT=self.audio_output,
            VB_ANDROID_REQUIRED_AUDIO_ROUTE='TYPE_BLUETOOTH_SCO' if hardware else '',
            VB_DAILY_SMS_CAP=str(self.daily_sms_cap),VB_CALLBACK_MAX_ATTEMPTS=str(self.callback_max_attempts),
            VB_SYNC_TRANSPORT=self.sync_transport,PYTHONUNBUFFERED='1')
        if hardware:
            env.update(VB_PHONE_ALLOWLIST=json.dumps(self.allowed_phones),VB_SMS_LINE_ID='android-1')
        if self.android_serial:
            env['VB_ANDROID_SERIAL']=self.android_serial
        if self.line_phone:
            env['VB_LINE_PHONE']=self.line_phone
        if self.central_phone:
            env['VB_CENTRAL_PHONE']=self.central_phone
        return env


def load_profile(path):
    return Profile.model_validate_json(Path(path).read_text(encoding='utf-8-sig'))


class InstanceLock:
    """OS lock releases on crash; a stale PID can never authorize killing a process."""
    def __init__(self,path):
        self.path=Path(path)
        self.file=None

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        self.file.seek(0)
        if self.path.stat().st_size==0:
            self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Another Stuart supervisor owns this data directory') from None
        return self

    def __exit__(self,*args):
        self.file.close()


def doctor(profile):
    checks={}
    with httpx.Client(timeout=2,trust_env=False) as client:
        try:
            r=client.get(profile.bob_url+'/v1/health',headers={'X-VB-Contract':'0.2'})
            checks['bob']=r.status_code==200 and r.json()=={'ok':True,'module':'bob'}
        except (httpx.HTTPError,ValueError):
            checks['bob']=False
        try:
            r=client.get(f'http://127.0.0.1:{profile.port}/ready')
            checks['running_service']=r.json()
        except (httpx.HTTPError,ValueError):
            checks['running_service']=None
    try:
        safe_wav(str(profile.data_dir/'prompts/system/fallback.wav'),profile.data_dir/'prompts')
        checks['fallback_prompt']=True
    except (ValueError,OSError,EOFError,wave.Error):
        checks['fallback_prompt']=False
    if profile.mode=='hardware':
        from .lines import Adb
        try:
            checks['usb']=Adb(profile.adb_path,profile.android_serial).run('get-state').strip()=='device'
        except (OSError,subprocess.TimeoutExpired):
            checks['usb']=False
        checks['operator_audio_transfer_required']=profile.calls_enabled
    return {'mode':profile.mode,'checks':checks}


def supervise(profile):
    env=profile.environment()
    if not env.get('VB_OPERATOR_TOKEN'):
        raise ValueError('Use Start-Stuart.ps1 to load the protected operator token')
    if profile.mode=='hardware' and any(not env.get(key) for key in ('VB_SMS_GATE_USER','VB_SMS_GATE_PASSWORD','VB_SMS_WEBHOOK_TOKEN')):
        raise ValueError('Protected local SMSGate credentials are missing')
    if profile.calls_enabled:
        safe_wav(str(profile.data_dir/'prompts/system/fallback.wav'),profile.data_dir/'prompts')
    profile.runtime_dir.mkdir(parents=True,exist_ok=True)
    manifest=profile.runtime_dir/'process.json'
    def write(state,**extra):
        value={'state':state,'supervisor_pid':os.getpid(),'port':profile.port,'mode':profile.mode,
               'updated_at':time.time(),**extra}
        temp=manifest.with_suffix('.tmp')
        temp.write_text(json.dumps(value,indent=2),encoding='utf-8')
        temp.replace(manifest)
    with InstanceLock(profile.data_dir/'.stuart.lock'):
        restarts=0
        while True:
            # Refuse a collision; never terminate a listener found on this port.
            with socket.socket() as probe:
                probe.bind(('127.0.0.1',profile.port))
            logpath=profile.runtime_dir/'service.log'
            if logpath.exists() and logpath.stat().st_size>2_000_000:
                logpath.replace(profile.runtime_dir/'service.previous.log')
            with logpath.open('ab') as log:
                child=subprocess.Popen([sys.executable,'-m','stuart','serve','--port',str(profile.port)],
                    cwd=MODULE,env=env,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                write('running',child_pid=child.pid,restarts=restarts)
                try:
                    code=child.wait()
                except KeyboardInterrupt:
                    try:
                        httpx.post(f'http://127.0.0.1:{profile.port}/operator/shutdown',
                            headers={'X-VB-Operator':env['VB_OPERATOR_TOKEN']},timeout=3,trust_env=False)
                        child.wait(timeout=15)
                    except (httpx.HTTPError,subprocess.TimeoutExpired):
                        child.terminate();child.wait(timeout=10)
                    write('stopped',restarts=restarts)
                    return 0
            if code==0:
                write('stopped',restarts=restarts)
                return 0
            if restarts>=profile.max_restarts:
                write('failed',exit_code=code,restarts=restarts)
                return code
            restarts+=1
            write('restarting',exit_code=code,restarts=restarts)
            time.sleep(min(10,2**restarts))


def backup(profile):
    from uuid import uuid4
    target=profile.runtime_dir/'backups'/str(uuid4())
    target.mkdir(parents=True)
    saved=[]
    for source,name in [(profile.data_dir/'stuart.db','stuart.db'),(profile.runtime_dir/'central.db','central.db')]:
        if not source.is_file():
            continue
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as incoming:
            with sqlite3.connect(target/name) as outgoing:
                incoming.backup(outgoing)
                if outgoing.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise OSError('Backup failed SQLite integrity check')
        saved.append(name)
    key=profile.runtime_dir/'demo-sync.key'
    if key.is_file():
        shutil.copy2(key,target/key.name)
        saved.append(key.name)
    if 'stuart.db' not in saved:
        raise ValueError('No Stuart database to back up')
    (target/'manifest.json').write_text(json.dumps({'version':1,'files':saved,'created_at':time.time(),
        'hub_id':profile.hub_id,'key_source':'runtime' if key.is_file() else 'external'},indent=2))
    return {'backup':str(target),'files':saved}


def restore(profile,source):
    source=Path(source).resolve()
    manifest=json.loads((source/'manifest.json').read_text())
    files=manifest.get('files',[])
    if manifest.get('version')!=1 or 'stuart.db' not in files or set(files)-{'stuart.db','central.db','demo-sync.key'}:
        raise ValueError('Unsupported backup manifest')
    if manifest.get('hub_id')!=profile.hub_id:
        raise ValueError('Restore must preserve the backed-up hub_id')
    targets={'stuart.db':profile.data_dir/'stuart.db','central.db':profile.runtime_dir/'central.db',
             'demo-sync.key':profile.runtime_dir/'demo-sync.key'}
    with InstanceLock(profile.data_dir/'.stuart.lock'):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',profile.port))
        for name in files:
            if targets[name].exists():
                raise ValueError('Restore requires fresh data and runtime directories')
            path=source/name
            if not path.is_file():
                raise ValueError('Backup file is missing')
            if name.endswith('.db'):
                with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise ValueError('Backup database is corrupt')
        for name in files:
            targets[name].parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source/name,targets[name])
    return {'restored':files,'key_source':manifest.get('key_source'),'start_automatically':False}
