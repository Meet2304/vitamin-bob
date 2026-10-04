import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request

from .audio import tone
from .contracts import Actions, CONTRACT, IncomingSms, Input, Missed, Sms, Sync, compact, safe_wav, validate_event
from .lines import Adb, AndroidLine, CallerHungUp, DialFailed, SimulatorLine
from .storage import Store, now, uid
from .sync_link import Codec, Receiver, load_key

log = logging.getLogger("stuart")
GSM = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM_EXT = set("^{}\\[~]|€\f")


def segments(text):
    if all(c in GSM or c in GSM_EXT for c in text):
        units = sum(2 if c in GSM_EXT else 1 for c in text)
        return 1 if units<=160 else (units+152)//153
    units = len(text.encode("utf-16-be"))//2
    return 1 if units<=70 else (units+66)//67


class Switchboard:
    def __init__(self, data_dir=None, runtime=None, bob_url=None, lines=None):
        root = Path(__file__).resolve().parents[2]
        self.data = Path(data_dir or os.getenv("VB_DATA_DIR",root/"data")).resolve()
        self.runtime = Path(runtime or root/"stuart"/"runtime").resolve()
        self.runtime.mkdir(parents=True,exist_ok=True)
        (self.data/"recordings").mkdir(parents=True,exist_ok=True)
        self.store = Store(self.data/"stuart.db")
        self.bob_url = (bob_url or os.getenv("VB_BOB_URL","http://127.0.0.1:8100")).rstrip("/")
        self.hub = os.getenv("VB_HUB_ID","kevin-demo")
        self.codec = Codec(load_key(self.runtime),self.hub)
        self.central = Receiver(self.runtime/"central.db",self.codec)
        self.sync_transport = os.getenv("VB_SYNC_TRANSPORT","loopback")
        self.sms_cap = int(os.getenv("VB_DAILY_SMS_CAP","100"))
        self.price = float(os.getenv("VB_SMS_PRICE_PER_SEGMENT","0"))
        self.retry_gap = float(os.getenv("VB_CALLBACK_RETRY_SECONDS","30"))
        self.max_attempts = int(os.getenv("VB_CALLBACK_MAX_ATTEMPTS","3"))
        self.event_timeout = float(os.getenv("VB_BOB_TIMEOUT_SECONDS","30"))
        self.tasks, self.errors = [], {}
        self.event_locks = {}
        self.deciding = set()
        self.client = httpx.AsyncClient(timeout=self.event_timeout,trust_env=False)
        self.hold = tone(self.runtime/"hold.wav",0.25,350)
        if lines is not None:
            self.lines = lines
        else:
            count = int(os.getenv("VB_SIM_LINES","1"))
            mode = os.getenv("VB_SIM_MODE","scripted")
            self.lines = {f"sim-{i+1}": SimulatorLine(f"sim-{i+1}",self.runtime,mode,
                            json.loads(os.getenv("VB_SIM_DIGITS",'["1","2","1"]')),
                            os.getenv("VB_SIM_RECORDING")) for i in range(count)}
            if os.getenv("VB_ANDROID_ENABLED") == "1":
                adbpath = os.getenv("VB_ADB",str(self.runtime/"tools"/"platform-tools"/"adb.exe"))
                self.lines["android-1"] = AndroidLine("android-1",self.runtime,Adb(adbpath,os.getenv("VB_ANDROID_SERIAL")))

    async def start(self):
        # A process crash leaves a call outcome unknown; never pretend that it completed.
        orphans=self.store.rows("SELECT * FROM calls WHERE ended_at IS NULL")
        for call in orphans:
            self.store.execute("UPDATE calls SET ended_at=?,reason='failed' WHERE id=?",(now(),call["id"]))
            self.store.execute("UPDATE missed SET status='failed' WHERE id=?",(call["missed_id"],))
            self.spawn(self.notify("call_ended",call_id=call["id"],reason="failed"))
        # An interruption between claiming a callback and creating its call row is also visible.
        for row in self.store.rows("SELECT * FROM missed WHERE status='calling'"):
            self.store.execute("UPDATE missed SET status='failed' WHERE id=?",(row['id'],))
            self.spawn(self.notify('callback_failed',missed_call_id=row['id'],phone=row['phone'],attempts=row['attempts']))
        interrupted=self.store.rows("SELECT id FROM sms WHERE status='sending'")
        for row in interrupted:
            self.store.execute("UPDATE sms SET error='Send outcome unknown after restart' WHERE id=?",(row['id'],))
            self.spawn(self.sms_status(row['id'],'failed'))
        self.spawn(self.dispatch())
        self.spawn(self.sms_worker())
        self.spawn(self.sms_receipts())
        self.spawn(self.sync_worker())
        self.spawn(self.recover_decisions())
        for line in self.lines.values():
            if isinstance(line,AndroidLine):
                self.spawn(self.poll_android(line))

    def spawn(self,coro):
        task=asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    async def notify(self,typ,**fields):
        try:
            return await self.event(typ,**fields)
        except OSError:
            return None

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        await self.client.aclose()
        self.store.close()
        self.central.db.close()

    async def event(self,typ,event_id=None,**fields):
        event_id=event_id or uid()
        lock=self.event_locks.setdefault(event_id,asyncio.Lock())
        async with lock:
            return await self._event(typ,event_id,**fields)

    async def _event(self,typ,event_id,**fields):
        event={"event_id": event_id or uid(),"type":typ,"at":now(),**fields}
        validate_event(event)
        existing=self.store.one("SELECT * FROM events WHERE id=?",(event["event_id"],))
        if existing:
            if existing["response"]:
                return json.loads(existing["response"])
            event=json.loads(existing["payload"])
        else:
            self.store.execute("INSERT INTO events(id,call_id,payload) VALUES(?,?,?)",(event["event_id"],fields.get("call_id"),compact(event)))
        last_error=None
        # One original request plus at most three retries, all with the same event ID.
        used=existing["attempts"] if existing else 0
        for attempt in range(used,4):
            try:
                self.store.execute("UPDATE events SET attempts=attempts+1 WHERE id=?",(event["event_id"],))
                response=await self.client.post(self.bob_url+"/v1/events",headers={"X-VB-Contract":CONTRACT},json=event)
                response.raise_for_status()
                result=response.json()
                if typ in ("call_started","action_result"):
                    Actions.model_validate(result)
                elif typ=="missed_call":
                    if result.get("ack") is not True or type(result.get("callback")) is not bool:
                        raise ValueError("Invalid missed_call acknowledgement")
                elif result.get("ack") is not True:
                    raise ValueError("Missing event acknowledgement")
                self.store.execute("UPDATE events SET response=?,error=NULL WHERE id=?",(compact(result),event["event_id"]))
                return result
            except (httpx.HTTPError,ValueError) as exc:
                last_error=type(exc).__name__
                self.store.execute("UPDATE events SET error=? WHERE id=?",(last_error,event["event_id"]))
                if attempt<3:
                    await asyncio.sleep(0.15*(attempt+1))
        raise OSError(f"Bob event {typ} was not acknowledged: {last_error or 'retry limit exhausted'}")

    async def missed(self,request):
        if request.line_id not in self.lines:
            raise ValueError("Unknown line")
        if request.source_id:
            prior=self.store.one("SELECT * FROM missed WHERE source_id=?",(request.source_id,))
            if prior:
                return prior["id"]
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
        prior=self.store.one("SELECT * FROM missed WHERE phone=? AND received_at>? ORDER BY received_at DESC LIMIT 1",(request.phone,cutoff))
        if prior:
            return prior["id"]
        missed_id,event_id=uid(),uid()
        self.store.execute("INSERT INTO missed(id,source_id,phone,line_id,received_at,status,event_id) VALUES(?,?,?,?,?,'pending',?)",
                           (missed_id,request.source_id,request.phone,request.line_id,now(),event_id))
        await self.decide(missed_id)
        return missed_id

    async def decide(self,missed_id):
        if missed_id in self.deciding:
            return
        self.deciding.add(missed_id)
        row=self.store.one("SELECT * FROM missed WHERE id=?",(missed_id,))
        try:
            response=await self.event("missed_call",event_id=row["event_id"],missed_call_id=missed_id,phone=row["phone"],line_id=row["line_id"])
            self.store.execute("UPDATE missed SET status=?,decision=? WHERE id=?",("queued" if response["callback"] else "done",int(response["callback"]),missed_id))
        except OSError:
            self.errors["bob"]="Missed call stored; awaiting Bob's callback decision. Retry exhausted; operator recovery required."
        finally:
            self.deciding.discard(missed_id)

    async def recover_decisions(self):
        # Only recover requests with attempts still available, including crashes before POST.
        while True:
            rows=self.store.rows("SELECT m.id FROM missed m LEFT JOIN events e ON e.id=m.event_id WHERE m.status='pending' AND (e.id IS NULL OR e.attempts<4)")
            for row in rows:
                await self.decide(row["id"])
            await asyncio.sleep(2)

    async def dispatch(self):
        while True:
            for line in self.lines.values():
                if line.state=="idle":
                    pending=self.store.rows("SELECT * FROM missed WHERE status='queued' AND next_at<=? ORDER BY received_at",(time.time(),))
                    row=next((r for r in pending if isinstance(self.lines[r['line_id']],AndroidLine)==isinstance(line,AndroidLine)),None)
                    if row:
                        self.store.execute("UPDATE missed SET status='calling',attempts=attempts+1 WHERE id=?",(row["id"],))
                        row["attempts"]+=1
                        line.state="in_call"
                        self.spawn(self.call(row,line))
            await asyncio.sleep(0.1)

    async def waiting(self,line,typ,**fields):
        stopped=asyncio.Event()
        async def hold():
            await asyncio.sleep(1.5)
            while not stopped.is_set():
                await line.play(self.hold,stopped)
                await asyncio.sleep(0.8)
        holding=asyncio.create_task(hold())
        try:
            # Retries still share the total 30-second call-side deadline.
            result=await asyncio.wait_for(self.event(typ,**fields),self.event_timeout)
            line.check()
            return Actions.model_validate(result)
        finally:
            stopped.set()
            # Let blocking audio stop at a block boundary before next prompt/record action.
            holding.cancel() if line.mode=="scripted" else None
            try:
                await asyncio.wait_for(asyncio.gather(holding,return_exceptions=True),1.5)
            except asyncio.TimeoutError:
                holding.cancel()

    async def call(self,row,line):
        call_id=uid()
        self.store.execute("INSERT INTO calls(id,missed_id,phone,line_id,started_at,current_action) VALUES(?,?,?,?,?,'waiting_for_bob')",(call_id,row["id"],row["phone"],line.line_id,now()))
        reason="failed"
        actions=None
        final_sent=False
        try:
            await line.place(row["phone"])
            actions=await self.waiting(line,"call_started",call_id=call_id,missed_call_id=row["id"],phone=row["phone"],line_id=line.line_id)
            for _ in range(100):
                final_sent=False
                final=None
                for action in actions.actions:
                    self.store.execute("UPDATE calls SET current_action=? WHERE id=?",(action.type,call_id))
                    prior=self.store.one("SELECT * FROM actions WHERE call_id=? AND action_id=?",(call_id,action.action_id))
                    if prior:
                        if prior["status"]!="done" or prior["type"]!=action.type:
                            raise ValueError("Action reuse with unknown/conflicting execution")
                        final=json.loads(prior["result"])
                        continue
                    self.store.execute("INSERT INTO actions VALUES(?,?,?,'running',NULL)",(call_id,action.action_id,action.type))
                    if action.type=="play":
                        path=safe_wav(action.audio_path,self.data/"prompts")
                        await line.play(path)
                        result={"status":"ok"}
                    elif action.type=="keypad":
                        result=await line.keypad(action)
                    elif action.type=="listen":
                        path=self.data/"recordings"/(call_id+"-"+uid()+".wav")
                        result=await line.listen(action,path)
                    else:
                        await line.hangup()
                        result={"status":"ok"}
                        reason="completed"
                    self.store.execute("UPDATE actions SET status='done',result=? WHERE call_id=? AND action_id=?",(compact(result),call_id,action.action_id))
                    final=result
                if actions.actions[-1].type=="hangup":
                    break
                self.store.execute("UPDATE calls SET current_action='waiting_for_bob' WHERE id=?",(call_id,))
                final_sent=True
                actions=await self.waiting(line,"action_result",call_id=call_id,action_id=actions.actions[-1].action_id,**final)
            else:
                raise ValueError("Call exceeded 100 action lists")
        except DialFailed as exc:
            reason=exc.reason
            self.errors['dial']='Callback attempt failed: '+str(exc)
            if row["attempts"]<self.max_attempts:
                self.store.execute("UPDATE missed SET status='queued',next_at=? WHERE id=?",(time.time()+self.retry_gap,row["id"]))
            else:
                self.store.execute("UPDATE missed SET status='failed' WHERE id=?",(row["id"],))
                try:
                    await self.event("callback_failed",missed_call_id=row["id"],phone=row["phone"],attempts=row["attempts"])
                except OSError:
                    pass
        except CallerHungUp:
            reason="caller_hung_up"
            if actions and not final_sent and actions.actions[-1].type!='hangup':
                try:
                    await self.event('action_result',call_id=call_id,action_id=actions.actions[-1].action_id,status='caller_hung_up')
                except OSError:
                    pass
        except asyncio.CancelledError:
            reason="failed"
            raise
        except Exception as exc:
            self.errors["call"] = type(exc).__name__ + ": call failed; inspect local event/action state"
            if actions and not final_sent and actions.actions[-1].type!='hangup':
                try:
                    await self.event('action_result',call_id=call_id,action_id=actions.actions[-1].action_id,status='error')
                except OSError:
                    pass
            fallback=self.data/"prompts"/"system"/"fallback.wav"
            try:
                await line.play(safe_wav(fallback,self.data/"prompts"))
            except Exception:
                pass
        finally:
            try:
                await line.hangup()
            except Exception:
                line.state="offline"
            self.store.execute("UPDATE calls SET ended_at=?,reason=?,current_action=NULL WHERE id=?",(now(),reason,call_id))
            missed=self.store.one('SELECT status FROM missed WHERE id=?',(row['id'],))
            if missed and missed['status']!='queued':
                self.store.execute("UPDATE missed SET status=? WHERE id=?",("done" if reason=="completed" else "failed",row["id"]))
            try:
                await self.event("call_ended",call_id=call_id,reason=reason)
            except OSError:
                pass

    def queue_sms(self,request):
        payload=request.model_dump()
        existing=self.store.one("SELECT request FROM sms WHERE id=?",(request.message_id,))
        if existing:
            if json.loads(existing["request"])!=payload:
                raise ValueError("message_id was already used with different content")
            return
        self.store.execute("INSERT INTO sms(id,request,priority,segments,status,created_at,updated_at) VALUES(?,?,?,?,'queued',?,?)",(request.message_id,compact(payload),{"urgent":0,"normal":1,"bulk":2}[request.priority],segments(request.text),now(),now()))

    async def sms_status(self,message_id,status,error=None):
        previous=self.store.one("SELECT status FROM sms WHERE id=?",(message_id,))
        if not previous or previous['status']=='delivered':
            return
        # Keep gateway diagnostics locally; the Bob event remains contract v0.2.
        if status=='failed' and isinstance(error,str) and error:
            self.store.execute("UPDATE sms SET error=? WHERE id=?",(error[:1024],message_id))
        if previous['status']==status:
            return
        self.store.execute("UPDATE sms SET status=?,updated_at=? WHERE id=?",(status,now(),message_id))
        try:
            await self.event("sms_status",message_id=message_id,status=status)
        except OSError:
            pass
        if status in ('sent','delivered'):
            await self.update_sms_sync_state()

    async def update_sms_sync_state(self):
        if self.sync_transport!='sms':
            return
        for row in self.store.rows("SELECT * FROM sync WHERE status='queued' AND attempts>0"):
            prefix=f"sync-{self.hub}-{row['seq']}-{row['attempts']}-"
            messages=self.store.rows("SELECT status FROM sms WHERE id LIKE ?",(prefix+'%',))
            expected=len(json.loads(row['frames']))
            if len(messages)==expected and all(m['status'] in ('sent','delivered') for m in messages):
                self.store.execute("UPDATE sync SET status='sent' WHERE id=?",(row['id'],))
                try:
                    await self.event('sync_status',record_id=row['id'],status='sent')
                except OSError:
                    pass

    async def sms_worker(self):
        while True:
            for row in self.store.rows("SELECT * FROM sms WHERE status='queued' ORDER BY priority,rowid"):
                target=os.getenv("VB_SMS_LINE_ID")
                eligible=[l for l in self.lines.values() if (not target or l.line_id==target) and l.state!="offline" and (row["priority"]<2 or l.state=="idle")]
                # Never silently simulate SMS when an Android transport is configured.
                if not target and any(isinstance(l,AndroidLine) for l in self.lines.values()):
                    eligible=[l for l in eligible if isinstance(l,AndroidLine)]
                if not eligible:
                    break
                today=datetime.now().astimezone().date().isoformat()
                line=next((l for l in eligible if self.used_segments(l.line_id,today)+row["segments"]<=self.sms_cap),None)
                if line is None:
                    self.store.execute("UPDATE sms SET error='Daily segment cap reached' WHERE id=?",(row["id"],))
                    await self.sms_status(row["id"],"failed")
                    continue
                self.store.execute("UPDATE sms SET status='sending',line_id=?,sent_at=? WHERE id=?",(line.line_id,now(),row["id"]))
                try:
                    status=await line.send_sms(json.loads(row["request"]))
                    if status=="accepted":
                        self.store.execute("UPDATE sms SET status='accepted' WHERE id=? AND status='sending'",(row["id"],))
                    else:
                        await self.sms_status(row["id"],"sent")
                        if status=="delivered":
                            await self.sms_status(row["id"],"delivered")
                except Exception as exc:
                    self.store.execute("UPDATE sms SET error=? WHERE id=?",(type(exc).__name__,row["id"]))
                    await self.sms_status(row["id"],"failed")
                break  # Re-evaluate priority after each send, so newly queued urgent SMS wins.
            await asyncio.sleep(0.1)

    def used_segments(self,line_id,today):
        # Include uncertain sends: cost may have occurred even when delivery status is unknown.
        rows=self.store.rows("SELECT segments,sent_at FROM sms WHERE line_id=? AND sent_at IS NOT NULL",(line_id,))
        return sum(r["segments"] for r in rows if datetime.fromisoformat(r["sent_at"]).astimezone().date().isoformat()==today)

    async def sms_receipts(self):
        cursor=0
        while True:
            pending=self.store.rows("SELECT id,line_id FROM sms WHERE status IN ('accepted','sent') ORDER BY rowid")
            if pending:
                cursor %= len(pending)
                ordered=pending[cursor:]+pending[:cursor]
                for row in ordered[:10]:
                    line=self.lines.get(row['line_id'])
                    if not isinstance(line,AndroidLine):
                        continue
                    try:
                        status,error=await line.sms_receipt(row['id'])
                        self.errors.pop('sms_receipts',None)
                        if status:
                            await self.sms_status(row['id'],status,error)
                    except Exception as exc:
                        # A missing receipt never triggers a second charged send.
                        self.errors['sms_receipts']=type(exc).__name__
                        break
                cursor += min(10,len(pending))
            await asyncio.sleep(10)

    async def queue_sync(self,request):
        # Validate every ID before inserting any item in a batch.
        by_id={}
        for record in request.records:
            payload=record.model_dump()
            existing=self.store.one("SELECT request FROM sync WHERE id=?",(record.record_id,))
            if (existing and json.loads(existing['request'])!=payload) or (record.record_id in by_id and by_id[record.record_id]!=payload):
                raise ValueError("record_id was already used with different content")
            by_id[record.record_id]=payload
        for record in request.records:
            payload=record.model_dump()
            existing=self.store.one("SELECT * FROM sync WHERE id=?",(record.record_id,))
            if existing:
                if json.loads(existing["request"])!=payload:
                    raise ValueError("record_id was already used with different content")
                continue
            seq=self.store.sequence()
            frames=self.codec.frames(seq,[payload])
            self.store.execute("INSERT INTO sync(id,request,status,seq,frames) VALUES(?,?,'queued',?,?)",(record.record_id,compact(payload),seq,compact(frames)))
            try:
                await self.event("sync_status",record_id=record.record_id,status="queued")
            except OSError:
                pass

    async def ack(self,text):
        seq=self.codec.verify_ack(text)
        row=self.store.one("SELECT * FROM sync WHERE seq=?",(seq,))
        if row and row["status"]!="acked":
            if row['status']!='sent':
                self.store.execute("UPDATE sync SET status='sent' WHERE id=?",(row['id'],))
                await self.notify('sync_status',record_id=row['id'],status='sent')
            self.store.execute("UPDATE sync SET status='acked' WHERE id=?",(row["id"],))
            try:
                await self.event("sync_status",record_id=row["id"],status="acked")
            except OSError:
                pass

    async def sync_worker(self):
        while True:
            if any(l.state=="idle" for l in self.lines.values()):
                for row in self.store.rows("SELECT * FROM sync WHERE status IN ('queued','sent') AND next_at<=? ORDER BY seq",(time.time(),)):
                    if self.sync_transport=='sms' and row['attempts']:
                        prefix=f"sync-{self.hub}-{row['seq']}-{row['attempts']}-"
                        previous=self.store.rows("SELECT status FROM sms WHERE id LIKE ?",(prefix+'%',))
                        if any(m['status'] in ('queued','sending','accepted') for m in previous):
                            continue  # Do not retransmit while the transport outcome is pending.
                    attempt=row["attempts"]+1
                    self.store.execute("UPDATE sync SET attempts=?,next_at=? WHERE id=?",(attempt,time.time()+min(300,2**min(attempt,8)),row["id"]))
                    if attempt>5:
                        self.store.execute("UPDATE sync SET status='failed' WHERE id=?",(row["id"],))
                        try:
                            await self.event("sync_status",record_id=row["id"],status="failed")
                        except OSError:
                            pass
                        continue
                    ack=None
                    try:
                        for i,frame in enumerate(json.loads(row["frames"])):
                            if self.sync_transport=="loopback":
                                # A deterministic demo fault: drop first frame on first attempt.
                                if os.getenv("VB_SYNC_DROP_FIRST")=="1" and attempt==1 and i==0:
                                    continue
                                ack=self.central.receive(frame) or ack
                            elif self.sync_transport=="sms":
                                to=os.getenv("VB_CENTRAL_PHONE")
                                if not to:
                                    raise ValueError("Set VB_CENTRAL_PHONE for SMS sync")
                                self.queue_sms(Sms(message_id=f"sync-{self.hub}-{row['seq']}-{attempt}-{i}",to=to,text=frame,priority="bulk"))
                            else:
                                raise ValueError("Unknown sync transport")
                        if self.sync_transport=='loopback':
                            self.store.execute("UPDATE sync SET status='sent' WHERE id=?",(row["id"],))
                            await self.event("sync_status",record_id=row["id"],status="sent")
                        if ack:
                            await self.ack(ack)
                    except Exception as exc:
                        self.errors["sync"]=type(exc).__name__
            await asyncio.sleep(0.2)

    async def incoming_sms(self,request):
        if request.line_id not in self.lines:
            raise ValueError('Unknown incoming SMS line')
        prior=self.store.one("SELECT * FROM incoming WHERE id=?",(request.message_id,))
        event_id=prior['event_id'] if prior else uid()
        if not prior:
            self.store.execute("INSERT INTO incoming VALUES(?,?)",(request.message_id,event_id))
        if request.text.startswith("VBA1|"):
            await self.ack(request.text)
        else:
            await self.event("sms_received",event_id=event_id,**request.model_dump())

    async def poll_android(self,line):
        cursor_key="android_since_"+line.line_id
        prior=self.store.one("SELECT value FROM meta WHERE key=?",(cursor_key,))
        since=int(prior['value']) if prior else int(time.time()*1000)
        if not prior:
            self.store.execute("INSERT INTO meta VALUES(?,?)",(cursor_key,str(since)))
        seen=set()
        while True:
            try:
                available=await line.available()
                if not available:
                    if line.state=="in_call":
                        line.disconnected=True
                    line.state="offline"
                    await asyncio.sleep(1)
                    continue
                if line.state=="offline":
                    line.state="idle"
                state=await asyncio.to_thread(line.adb.run,"shell","dumpsys","telephony.registry")
                if "mCallState=1" in state and line.state=="idle":
                    line.state="ringing"
                    await asyncio.to_thread(line.adb.run,"shell","input","keyevent","6")
                    line.state="idle"
                raw=await asyncio.to_thread(line.adb.run,"shell","content","query","--uri","content://call_log/calls",
                                             "--projection","_id:number:type:date","--where",f"date>{since}")
                if "Permission Denial" in raw or "Error while accessing provider" in raw:
                    raise PermissionError("Android blocks shell call-log access; companion app required")
                import re
                for entry in raw.splitlines():
                    match=re.search(r"_id=(\d+), number=(.*?), type=(\d+), date=(\d+)",entry)
                    if not match or match[1] in seen or match[3] not in ("3","5"):
                        continue
                    seen.add(match[1])
                    phone=re.sub(r"[\s()-]","",match[2])
                    if not phone.startswith("+"):
                        phone=os.getenv("VB_COUNTRY_CODE","+91")+phone.lstrip("0")
                    await self.missed(Missed(phone=phone,line_id=line.line_id,source_id="adb-call-"+match[1]))
            except Exception as exc:
                self.errors["android"]=type(exc).__name__+": check USB authorization and call-log permissions"
            await asyncio.sleep(0.7)

    def status(self):
        sms=self.store.rows("SELECT * FROM sms")
        today=datetime.now().astimezone().date().isoformat()
        sent=[s for s in sms if s["sent_at"] and datetime.fromisoformat(s["sent_at"]).astimezone().date().isoformat()==today]
        counts={s:len(self.store.rows("SELECT id FROM sync WHERE status=?",(s,))) for s in ("queued","sent","acked","failed")}
        return {
            "lines":[{"line_id":l.line_id,"label":("Android USB / PC audio" if isinstance(l,AndroidLine) else "SIMULATOR "+l.mode),"msisdn":os.getenv("VB_LINE_PHONE","") if isinstance(l,AndroidLine) else "","state":l.state} for l in self.lines.values()],
            "queue":[{"missed_call_id":r["id"],"phone":r["phone"],"received_at":r["received_at"],"status":r["status"],"attempts":r["attempts"]} for r in self.store.rows("SELECT * FROM missed WHERE decision=1 ORDER BY received_at DESC LIMIT 100")],
            "active_calls":[{"call_id":r["id"],"phone":r["phone"],"line_id":r["line_id"],"started_at":r["started_at"],"current_action":r["current_action"]} for r in self.store.rows("SELECT * FROM calls WHERE ended_at IS NULL")],
            "sms":{"sent_today":sum(s["status"] in ("sent","delivered") for s in sent),"segments_today":sum(s["segments"] for s in sent if s['status'] in ('sent','delivered')),"failed_today":sum(s["status"]=="failed" for s in sms if s['updated_at'] and datetime.fromisoformat(s['updated_at']).astimezone().date().isoformat()==today),"queued":{p:sum(s["priority"]==i and s["status"]=="queued" for s in sms) for i,p in enumerate(("urgent","normal","bulk"))}},
            "sync":counts,
        }


async def require_contract(x_vb_contract: str | None=Header(default=None)):
    if x_vb_contract!=CONTRACT:
        raise HTTPException(409,"Expected X-VB-Contract: 0.2")


def make_app(board=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.board=board or Switchboard()
        await app.state.board.start()
        yield
        await app.state.board.stop()
    app=FastAPI(title="Stuart • contract 0.2",lifespan=lifespan)
    def get_board(request:Request):
        return request.app.state.board
    @app.get("/v1/health",dependencies=[Depends(require_contract)])
    async def health():
        return {"ok":True,"module":"stuart"}
    @app.get("/v1/status",dependencies=[Depends(require_contract)])
    async def status(b=Depends(get_board)):
        return b.status()
    @app.post("/v1/sms",dependencies=[Depends(require_contract)])
    async def sms(request:Sms,b=Depends(get_board)):
        try:
            b.queue_sms(request)
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        return {"queued":True}
    @app.post("/v1/sync",dependencies=[Depends(require_contract)])
    async def sync(request:Sync,b=Depends(get_board)):
        try:
            await b.queue_sync(request)
        except ValueError as exc:
            raise HTTPException(409,str(exc))
        return {"queued":True}
    @app.post("/sim/missed-call")
    async def missed(request:Missed,b=Depends(get_board)):
        if request.line_id not in b.lines or isinstance(b.lines[request.line_id],AndroidLine):
            raise HTTPException(400,"Select a simulator line")
        return {"missed_call_id":await b.missed(request)}
    @app.post("/sim/sms")
    async def incoming(request:IncomingSms,b=Depends(get_board)):
        await b.incoming_sms(request)
        return {"ack":True}
    @app.post("/android/smsgate")
    async def smsgate(request:Request,b=Depends(get_board)):
        import hmac
        secret=os.getenv("VB_SMS_WEBHOOK_TOKEN")
        if not secret or not hmac.compare_digest(request.query_params.get('token',''),secret):
            raise HTTPException(403,"Configure and provide the SMS webhook token")
        body=await request.json()
        typ,payload=body.get('event'),body.get('payload',{})
        try:
            if typ=='sms:received':
                await b.incoming_sms(IncomingSms(message_id=payload['messageId'],phone=payload['sender'],text=payload['message'],line_id='android-1'))
            elif typ in ('sms:sent','sms:delivered','sms:failed'):
                await b.sms_status(payload['messageId'],typ.split(':')[1],payload.get('reason'))
            else:
                raise ValueError('Unsupported webhook event')
        except (ValueError,KeyError) as exc:
            raise HTTPException(422,str(exc))
        return {'ack':True}
    @app.post("/operator/retry-pending",dependencies=[Depends(require_contract)])
    async def retry_pending(b=Depends(get_board)):
        rows=b.store.rows("SELECT m.id,m.event_id FROM missed m WHERE m.status='pending'")
        for row in rows:
            b.store.execute("UPDATE events SET attempts=0 WHERE id=?",(row['event_id'],))
            await b.decide(row['id'])
        return {'retried':len(rows)}
    @app.post("/operator/retry-events",dependencies=[Depends(require_contract)])
    async def retry_events(b=Depends(get_board)):
        retried,failed=0,0
        for row in b.store.rows("SELECT * FROM events WHERE response IS NULL ORDER BY rowid"):
            if row['id'] in b.event_locks and b.event_locks[row['id']].locked():
                continue
            payload=json.loads(row['payload'])
            b.store.execute("UPDATE events SET attempts=0 WHERE id=?",(row['id'],))
            try:
                await b.event(payload['type'],event_id=row['id'],**{k:v for k,v in payload.items() if k not in ('event_id','type','at')})
                retried+=1
            except OSError:
                failed+=1
        for row in b.store.rows("SELECT id FROM missed WHERE status='pending'"):
            await b.decide(row['id'])
        return {'retried':retried,'failed':failed}
    @app.post("/operator/retry-sync",dependencies=[Depends(require_contract)])
    async def retry_sync(b=Depends(get_board)):
        count=b.store.execute("UPDATE sync SET status='queued',attempts=0,next_at=0 WHERE status='failed'")
        return {'retried':count}
    @app.post("/sim/{line_id}/digits")
    async def digits(line_id:str,request:Input,b=Depends(get_board)):
        if line_id not in b.lines or isinstance(b.lines[line_id],AndroidLine):
            raise HTTPException(404,"Unknown simulator line")
        await b.lines[line_id].input.put(request.digits)
        return {"queued":True}
    @app.post("/sim/{line_id}/hangup")
    async def hungup(line_id:str,b=Depends(get_board)):
        if line_id not in b.lines or isinstance(b.lines[line_id],AndroidLine):
            raise HTTPException(404,"Unknown simulator line")
        b.lines[line_id].disconnected=True
        return {"ack":True}
    @app.get("/diagnostics")
    async def diagnostics(b=Depends(get_board)):
        return {"errors":b.errors,"pending_decisions":len(b.store.rows("SELECT id FROM missed WHERE status='pending'")),
                "unacknowledged_events":len(b.store.rows("SELECT id FROM events WHERE response IS NULL")),
                "sync_transport":b.sync_transport,"sms_price_assumption":b.price,
                "reserved_segments_today":sum(b.used_segments(line,datetime.now().astimezone().date().isoformat()) for line in b.lines),
                "estimated_sms_rupees_today":b.status()["sms"]["segments_today"]*b.price}
    @app.get("/central/records")
    async def records(b=Depends(get_board)):
        return {"transport":b.sync_transport,"records":b.central.rows()}
    @app.get("/",include_in_schema=False)
    async def home():
        from fastapi.responses import HTMLResponse
        return HTMLResponse((Path(__file__).with_name("console.html")).read_text(encoding="utf-8"))
    return app


app=make_app()
