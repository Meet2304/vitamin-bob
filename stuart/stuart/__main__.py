import argparse
import asyncio
import json
import os
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description="Stuart local transport service")
    parser.add_argument("command",choices=["serve","fake-bob","central","trigger","devices","check-phone","run","doctor","backup","restore"])
    parser.add_argument('--config',type=Path)
    parser.add_argument('--backup',type=Path)
    parser.add_argument("--port",type=int)
    parser.add_argument("--phone",default="+919000000001")
    parser.add_argument("--line",default="sim-1")
    args=parser.parse_args()
    if args.command in ('run','doctor','backup','restore'):
        from .runtime import load_profile, supervise, doctor, backup, restore
        if not args.config:
            parser.error('--config is required')
        profile=load_profile(args.config)
        if args.command=='doctor':
            print(json.dumps(doctor(profile),indent=2))
        elif args.command=='backup':
            print(json.dumps(backup(profile),indent=2))
        elif args.command=='restore':
            if not args.backup:
                parser.error('--backup is required')
            print(json.dumps(restore(profile,args.backup),indent=2))
        else:
            raise SystemExit(supervise(profile))
    elif args.command in ("serve","fake-bob","central"):
        import importlib
        import hmac
        import uvicorn
        from fastapi import Header, HTTPException
        module,port={"serve":("stuart.service:app",8200),"fake-bob":("stuart.fake_bob:app",8100),"central":("central.app:app",8300)}[args.command]
        module_name,attribute=module.split(':')
        app=getattr(importlib.import_module(module_name),attribute)
        server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=args.port or port,log_level="info",access_log=False))
        @app.post('/operator/shutdown')
        async def shutdown(x_vb_operator: str | None=Header(default=None)):
            token=os.getenv('VB_OPERATOR_TOKEN')
            if not token or not hmac.compare_digest(x_vb_operator or '',token):
                raise HTTPException(403,'Operator token required')
            server.should_exit=True
            return {'stopping':True}
        server.run()
    elif args.command=="devices":
        import sounddevice as sd
        print(sd.query_devices())
        if os.name == 'nt':
            import soundcard as sc
            print('\nWASAPI speaker loopback inputs:')
            for mic in sc.all_microphones(include_loopback=True):
                if mic.isloopback and mic.channels >= 2:
                    print('loopback:'+mic.name)
            print('\nNative WASAPI outputs:')
            for speaker in sc.all_speakers():
                print('wasapi:'+speaker.name)
    elif args.command=="check-phone":
        from .lines import Adb
        runtime=Path(__file__).resolve().parents[1]/"runtime"
        adb=Adb(os.getenv("VB_ADB",str(runtime/"tools"/"platform-tools"/"adb.exe")),os.getenv("VB_ANDROID_SERIAL"))
        for label,command in [("USB devices",("devices","-l")),("Model",("shell","getprop","ro.product.model")),("Android",("shell","getprop","ro.build.version.release")),
                              ("Call-log access (empty query)",("shell","content","query","--uri","content://call_log/calls","--projection","_id","--where","date>9999999999999")),
                              ("SMS access (empty query)",("shell","content","query","--uri","content://sms/inbox","--projection","_id","--where","date>9999999999999"))]:
            try:
                print(label+": "+adb.run(*command).strip())
            except Exception as exc:
                print(label+": "+str(exc))
    else:
        import httpx
        url=os.getenv("VB_STUART_URL","http://127.0.0.1:8200")
        result=httpx.post(url+"/sim/missed-call",json={"phone":args.phone,"line_id":args.line},timeout=35,trust_env=False)
        result.raise_for_status()
        print(json.dumps(result.json(),indent=2))

if __name__=="__main__":
    main()
