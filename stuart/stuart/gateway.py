"""Repair USB forwarding and this Stuart instance's local SMSGate webhooks."""
import asyncio
import os
from urllib.parse import urlsplit

import httpx

from .lines import AndroidLine
from .storage import now


class GatewayBridge:
    def __init__(self, board):
        self.board=board
        self.line=next(l for l in board.lines.values() if isinstance(l,AndroidLine))
        self.url=os.environ['VB_SMS_GATE_URL'].rstrip('/')
        self.auth=(os.environ['VB_SMS_GATE_USER'],os.environ['VB_SMS_GATE_PASSWORD'])
        self.local_port=urlsplit(self.url).port
        self.port=int(os.environ['VB_STUART_PORT'])
        self.token=os.environ['VB_SMS_WEBHOOK_TOKEN']
        self.prefix=f'stuart-{board.hub}-{self.port}-'
        events=['sms:sent','sms:delivered','sms:failed']
        if os.getenv('VB_SMS_RECEIVE_ENABLED','1')=='1':
            events.append('sms:received')
        self.hooks=[{'id':self.prefix+event.split(':')[1],'event':event,
            'url':f'http://127.0.0.1:{self.port}/android/smsgate?token={self.token}'} for event in events]
        self.created_forward=False
        self.created_reverse=False
        self.state={'managed':True,'ready':False,'last_checked':None}

    async def forwarding(self,mode,local,remote):
        adb=self.line.adb
        rows=(await asyncio.to_thread(adb.run,mode,'--list')).splitlines()
        for row in rows:
            fields=row.split()
            if len(fields)>=3 and fields[-2]==local:
                if fields[-1]!=remote:
                    raise OSError('USB port belongs to another mapping')
                return False
        await asyncio.to_thread(adb.run,mode,'--no-rebind',local,remote)
        return True

    async def ensure(self):
        if not await self.line.available():
            raise OSError('USB disconnected or unauthorized')
        self.created_forward |= await self.forwarding('forward',f'tcp:{self.local_port}','tcp:8080')
        self.created_reverse |= await self.forwarding('reverse',f'tcp:{self.port}',f'tcp:{self.port}')
        async with httpx.AsyncClient(base_url=self.url,auth=self.auth,timeout=5,trust_env=False) as client:
            response=await client.get('/health')
            health=response.json()
            failed={k for k,v in health.get('checks',{}).items() if isinstance(v,dict) and v.get('status')=='fail'}
            offline_checks={'connection:status','connection:transport'}
            expected_offline_failure=(response.status_code==500 and bool(failed)
                and failed<=offline_checks and health.get('status')=='fail')
            if not expected_offline_failure:
                response.raise_for_status()
            response=await client.get('/settings')
            response.raise_for_status()
            if response.json().get('webhooks',{}).get('internet_required') is not False:
                response=await client.patch('/settings',json={'webhooks':{'internet_required':False}})
                response.raise_for_status()
            response=await client.get('/webhooks')
            response.raise_for_status()
            existing={row['id']:row for row in response.json()}
            for hook in self.hooks:
                old=existing.get(hook['id'])
                if old and all(old.get(k)==v for k,v in hook.items()):
                    continue
                if old:
                    response=await client.delete('/webhooks/'+hook['id'])
                    response.raise_for_status()
                response=await client.post('/webhooks',json=hook)
                response.raise_for_status()
        self.state={'managed':True,'ready':True,'offline_webhooks':True,'registered_events':[h['event'] for h in self.hooks],
                    'expected_offline_checks':sorted(failed & offline_checks),'last_checked':now()}

    async def run(self):
        while True:
            try:
                await self.ensure()
                self.board.errors.pop('gateway',None)
            except Exception as exc:
                # HTTP exception strings may contain the webhook token; never expose them.
                self.state={'managed':True,'ready':False,'error':type(exc).__name__,'last_checked':now()}
                self.board.errors['gateway']=type(exc).__name__+': check USB and SMSGate local service'
            await asyncio.sleep(10)

    async def close(self):
        try:
            async with httpx.AsyncClient(base_url=self.url,auth=self.auth,timeout=3,trust_env=False) as client:
                response=await client.get('/webhooks')
                response.raise_for_status()
                existing={row['id']:row for row in response.json()}
                for hook in self.hooks:
                    if existing.get(hook['id'],{}).get('url')==hook['url']:
                        response=await client.delete('/webhooks/'+hook['id'])
                        response.raise_for_status()
            for mode,created,port in [('forward',self.created_forward,self.local_port),('reverse',self.created_reverse,self.port)]:
                if created:
                    await asyncio.to_thread(self.line.adb.run,mode,'--remove',f'tcp:{port}')
            self.state['cleanup_complete']=True
        except Exception:
            self.state['cleanup_complete']=False
