"""Transport-only Bob mock. Test tones are not clinical or language prompts."""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request

from .audio import tone
from .contracts import Actions, CONTRACT, compact, validate_event
from .service import require_contract
from .storage import Store, uid


def make_fake(data_dir=None,runtime=None):
    root=Path(__file__).resolve().parents[2]
    data=Path(data_dir or os.getenv("VB_DATA_DIR",root/"data")).resolve()
    state=Path(runtime or root/"stuart"/"runtime")
    state.mkdir(parents=True,exist_ok=True)
    db=Store(state/"fake-bob.db")
    db.execute("CREATE TABLE IF NOT EXISTS mock_events(id TEXT PRIMARY KEY,payload TEXT,response TEXT)")
    prompt=tone(data/"prompts"/"mock"/"test.wav",0.5)
    tone(data/"prompts"/"system"/"fallback.wav",0.5,330)
    lock=asyncio.Lock()
    app=FastAPI(title="Fake Bob • scripted transport check")
    @app.get("/v1/health",dependencies=[Depends(require_contract)])
    async def health():
        return {"ok":True,"module":"bob"}
    @app.post("/v1/events",dependencies=[Depends(require_contract)])
    async def event(request:Request):
        value=await request.json()
        try:
            validate_event(value)
        except (ValueError,TypeError,KeyError) as exc:
            raise HTTPException(422,str(exc))
        async with lock:
            prior=db.one("SELECT * FROM mock_events WHERE id=?",(value["event_id"],))
            if prior:
                if json.loads(prior["payload"])!=value:
                    raise HTTPException(409,"event_id reused with different event")
                return json.loads(prior["response"])
            typ=value["type"]
            if typ=="missed_call":
                result={"ack":True,"callback":True}
            elif typ=="call_started":
                result={"actions":[{"type":"play","action_id":uid(),"audio_path":str(prompt)},
                                   {"type":"keypad","action_id":uid(),"max_digits":1,"timeout_ms":15000,"terminator":None}]}
            elif typ=="action_result":
                if "digits" in value:
                    result={"actions":[{"type":"play","action_id":uid(),"audio_path":str(prompt)},
                                       {"type":"listen","action_id":uid(),"max_ms":5000,"end_silence_ms":800}]}
                else:
                    result={"actions":[{"type":"hangup","action_id":uid()}]}
            else:
                result={"ack":True}
            if "actions" in result:
                Actions.model_validate(result)
            db.execute("INSERT INTO mock_events VALUES(?,?,?)",(value["event_id"],compact(value),compact(result)))
            return result
    @app.get("/mock/events")
    async def events():
        return [json.loads(r["payload"]) for r in db.rows("SELECT payload FROM mock_events ORDER BY rowid")]
    @app.post("/mock/messages")
    async def test_messages():
        url=os.getenv("VB_STUART_URL","http://127.0.0.1:8200")
        async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
            transport=await client.get(url+'/v1/status',headers={'X-VB-Contract':CONTRACT})
            transport.raise_for_status()
            if any(line['line_id'].startswith('android-') for line in transport.json()['lines']):
                raise HTTPException(409,'Mock messages are restricted to simulated lines')
            sms=await client.post(url+"/v1/sms",headers={"X-VB-Contract":CONTRACT},json={"message_id":uid(),"to":"+919000000001","text":"Vitamin Bob transport test","priority":"normal"})
            sms.raise_for_status()
            sync=await client.post(url+"/v1/sync",headers={"X-VB-Contract":CONTRACT},json={"records":[{"record_id":uid(),"kind":"triage","payload":{"t":tier,"c":"demo"}} for tier in ("L","M","U")]})
            sync.raise_for_status()
        return {"queued":True,"note":"Synthetic destination; use simulator lines only"}
    return app


app=make_fake()
