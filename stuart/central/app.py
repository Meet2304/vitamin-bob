import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from stuart.sync_link import Codec, Receiver, load_key

runtime=Path(__file__).resolve().parents[1]/"runtime"
receiver=Receiver(runtime/"central-standalone.db",Codec(load_key(runtime),os.getenv("VB_HUB_ID","kevin-demo")))
app=FastAPI(title="Central • SMS receiver")

class Frame(BaseModel):
    text:str

@app.post("/frames")
def frame(request:Frame):
    try:
        ack=receiver.receive(request.text)
        return {"ack":ack}
    except Exception:
        raise HTTPException(422,"Invalid or unauthenticated frame")

@app.get("/records")
def records():
    return receiver.rows()

@app.get("/")
def home():
    from fastapi.responses import HTMLResponse
    return HTMLResponse('<html lang="en"><meta charset="utf-8"><title>Central receiver</title><body style="max-width:900px;margin:40px auto;background:#f5f1e7;color:#203a32;font-family:Georgia"><h1>Central receiver</h1><p>Local receiver • SMS-sized encrypted frames • one committed record per ID</p><pre id="records"></pre><script>async function refresh(){const r=await fetch("/records");document.getElementById("records").textContent=JSON.stringify(await r.json(),null,2)}refresh();setInterval(refresh,1000)</script></body></html>')
