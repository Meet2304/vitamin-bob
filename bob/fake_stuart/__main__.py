"""Fake Stuart: drives Bob through scripted calls and checks everything Bob sends against the contract.

    python -m fake_stuart run                  # all scenarios (Bob must be running on :8100)
    python -m fake_stuart run hi_emergency failover_clinic_a_closed
    python -m fake_stuart run --pace 1.5       # slow down so the dashboard can be watched live
    python -m fake_stuart serve                # only the fake Stuart API (status, sms, sync) for the dashboard

It plays both sides Bob talks to:
  * Stuart's API on :8200: /v1/health, /v1/status, /v1/sms, /v1/sync. Every request is validated;
    SMS and sync records get sms_status / sync_status events back, as the real Stuart would send.
  * The patient and the clinicians: missed calls, callbacks, keypad presses (from each vignette's
    ground truth), recordings (synthetic patient audio if generated, else a placeholder WAV plus a
    transcript sidecar so Bob can be tested without the model), SMS commands, hang-ups, duplicates.
Exit code 1 if any contract violation or failed expectation was found.
"""

import argparse
import json
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn
from fastapi import Body, FastAPI, Request

BOB_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOB_DIR))

from vitamin_bob import audio, config, contract  # noqa: E402
from vitamin_bob.prompts import data_dir  # noqa: E402

HEADERS = {contract.HEADER: contract.VERSION}
LINE_ID = "fake-line-1"
LINE_MSISDN = "+919999000001"
violations: list[str] = []
state = {"sms": [], "sync": [], "queue": [], "active": {}, "sms_counts": {"sent": 0, "segments": 0, "failed": 0},
         "sync_counts": {"queued": 0, "sent": 0, "acked": 0, "failed": 0}}
lock = threading.Lock()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def violation(msg: str) -> None:
    with lock:
        violations.append(msg)
    print(f"    !! CONTRACT: {msg}")


# --- the fake Stuart API ----------------------------------------------------------------------
app = FastAPI(title="Fake Stuart")


def check_header(request: Request, what: str) -> None:
    if request.headers.get(contract.HEADER) != contract.VERSION:
        violation(f"{what}: missing or wrong {contract.HEADER} header")


@app.get("/v1/health")
def health():
    return {"ok": True, "module": "stuart"}


@app.get("/v1/status")
def status(request: Request):
    check_header(request, "GET /v1/status")
    with lock:
        active = list(state["active"].values())
        return {
            "lines": [{"line_id": LINE_ID, "label": "Kevin line 1 (fake)", "msisdn": LINE_MSISDN,
                       "state": "in_call" if active else "idle"}],
            "queue": list(state["queue"]),
            "active_calls": active,
            "sms": {"sent_today": state["sms_counts"]["sent"], "segments_today": state["sms_counts"]["segments"],
                    "failed_today": state["sms_counts"]["failed"], "queued": {"urgent": 0, "normal": 0, "bulk": 0}},
            "sync": dict(state["sync_counts"]),
        }


def send_event(ev: dict) -> dict | None:
    ev = {"event_id": uuid.uuid4().hex, "at": now(), **ev}
    try:
        r = httpx.post(f"{config.BOB_URL}/v1/events", json=ev, headers=HEADERS, timeout=30)
        return r.json()
    except Exception as e:  # noqa: BLE001
        violation(f"Bob did not answer {ev['type']}: {e}")
        return None


def _later(delay: float, ev: dict) -> None:
    def run():
        time.sleep(delay)
        resp = send_event(ev)
        if resp != {"ack": True}:
            violation(f"{ev['type']} should be acked with {{'ack': true}}, got {resp}")
    threading.Thread(target=run, daemon=True).start()


@app.post("/v1/sms")
def sms(request: Request, body: dict = Body(...)):
    check_header(request, "POST /v1/sms")
    try:
        m = contract.SmsRequest.model_validate(body).model_dump()
    except Exception as e:  # noqa: BLE001
        violation(f"/v1/sms invalid: {e}")
        return {"queued": False}
    with lock:
        if any(x["message_id"] == m["message_id"] for x in state["sms"]):
            return {"queued": True}  # idempotent
        state["sms"].append(m)
        segments = -(-len(m["text"]) // (153 if m["text"].isascii() else 67))
        state["sms_counts"]["sent"] += 1
        state["sms_counts"]["segments"] += segments
    _later(0.3, {"type": "sms_status", "message_id": m["message_id"], "status": "delivered"})
    return {"queued": True}


@app.post("/v1/sync")
def sync(request: Request, body: dict = Body(...)):
    check_header(request, "POST /v1/sync")
    try:
        req = contract.SyncRequest.model_validate(body)
    except Exception as e:  # noqa: BLE001
        violation(f"/v1/sync invalid: {e}")
        return {"queued": False}
    for rec in req.records:
        for p in contract.sync_payload_problems(rec.payload):
            violation(f"sync record {rec.kind}: {p}")
        with lock:
            if any(x["record_id"] == rec.record_id for x in state["sync"]):
                continue
            state["sync"].append(rec.model_dump())
            state["sync_counts"]["acked"] += 1
        _later(0.4, {"type": "sync_status", "record_id": rec.record_id, "status": "sent"})
        _later(0.9, {"type": "sync_status", "record_id": rec.record_id, "status": "acked"})
    return {"queued": True}


def serve_in_background() -> None:
    port = int(config.STUART_URL.rsplit(":", 1)[1])
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        try:
            httpx.get(f"{config.STUART_URL}/v1/health", timeout=0.2)
            return
        except httpx.HTTPError:
            time.sleep(0.1)


# --- the scripted patient ---------------------------------------------------------------------
def load_vignettes() -> dict:
    out = {}
    for f in (BOB_DIR / "eval").glob("vignettes*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                v = json.loads(line)
                v.setdefault("lang", "hi")
                out[v["id"]] = v
    return out


class Patient:
    def __init__(self, scn: dict, vignette: dict | None, pace: float):
        self.scn, self.v, self.pace = scn, vignette, pace
        self.menu = list(scn.get("menu", []))
        self.keys = {k: list(v) for k, v in scn.get("keys", {}).items()}
        self.questions = 0

    def truth_key(self, clip: str) -> str | None:
        v = self.v or {}
        sym, flags = v.get("symptoms", {}), v.get("flags", [])
        if clip.startswith("q_symptom_"):
            s = clip.removeprefix("q_symptom_")
            return "3" if s in v.get("unknown_symptoms", []) else ("1" if s in sym else "2")
        if clip.startswith("q_days_"):
            d = sym.get(clip.removeprefix("q_days_"))
            return f"{d}#" if isinstance(d, int) else "#"
        if clip.startswith("q_flag_"):
            f = clip.removeprefix("q_flag_")
            return "3" if f in v.get("unknown_flags", []) else ("1" if f in flags else "2")
        return None

    def press(self, clips: list[str]) -> str | None:
        for clip in reversed(clips):
            if clip in self.keys and self.keys[clip]:
                return self.keys[clip].pop(0)
            if clip == "lang_menu":
                return self.menu.pop(0) if self.menu else None
            if clip == "who_is_sick":
                return (self.v or {}).get("age", "3")
            if (k := self.truth_key(clip)) is not None:
                self.questions += 1
                return k
        return None

    def recording(self) -> tuple[str, int]:
        """Copy what the patient 'says' into data/recordings, as Stuart would after a listen."""
        rec_dir = data_dir() / "recordings"
        rec_dir.mkdir(parents=True, exist_ok=True)
        target = rec_dir / f"{uuid.uuid4().hex}.wav"
        v = self.v
        synth = data_dir() / "eval_audio" / v["lang"] / f"{v['id']}.wav"
        if synth.exists():
            shutil.copy(synth, target)
        else:
            audio.write(target, audio.tone(300, min(20000, 90 * len(v["transcript"])), volume=0.05))
        target.with_suffix(".transcript.txt").write_text(v["transcript"], encoding="utf-8")
        with __import__("wave").open(str(target)) as w:
            ms = int(1000 * w.getnframes() / w.getframerate())
        return str(target.resolve()), ms


def clip_of(action: dict) -> str:
    p = Path(action["audio_path"])
    return f"{p.parent.name}/{p.stem}"


def run_call(scn: dict, vignettes: dict, pace: float) -> dict:
    """One missed call through to hangup. Returns what the patient heard."""
    v = vignettes.get(scn.get("vignette")) if scn.get("vignette") else None
    patient = Patient(scn, v, pace)
    phone, dup = scn["phone"], scn.get("duplicate", False)
    heard: list[str] = []
    mc_id = uuid.uuid4().hex

    def event(ev: dict, after_listen: bool = False) -> dict | None:
        ev = {"event_id": uuid.uuid4().hex, "at": now(), **ev}
        t = time.time()
        try:
            resp = httpx.post(f"{config.BOB_URL}/v1/events", json=ev, headers=HEADERS, timeout=30).json()
        except Exception as e:  # noqa: BLE001
            violation(f"Bob did not answer {ev['type']}: {e}")
            return None
        dt = time.time() - t
        if dt > (20 if after_listen else 2):
            violation(f"{ev['type']} answered in {dt:.1f}s (limit {20 if after_listen else 2}s)")
        if dup:  # resend the same event_id: Bob must return the identical response
            again = httpx.post(f"{config.BOB_URL}/v1/events", json=ev, headers=HEADERS, timeout=30).json()
            if again != resp:
                violation(f"duplicate {ev['type']} got a different response")
        return resp

    with lock:
        state["queue"].append({"missed_call_id": mc_id, "phone": phone, "received_at": now(), "status": "queued",
                               "attempts": 0})
    resp = event({"type": "missed_call", "missed_call_id": mc_id, "phone": phone, "line_id": LINE_ID})
    result = {"callback": None, "heard": heard, "questions": 0}
    if not resp or set(resp) != {"ack", "callback"} or resp.get("ack") is not True:
        violation(f"missed_call response must be {{ack, callback}}, got {resp}")
        return result
    result["callback"] = resp["callback"]
    print(f"    missed call from {phone}: callback={resp['callback']}")
    if not resp["callback"] or scn.get("kind") == "missed_call_only":
        _dequeue(mc_id)
        return result
    if scn.get("kind") == "callback_failed":
        _dequeue(mc_id)
        r = event({"type": "callback_failed", "missed_call_id": mc_id, "phone": phone, "attempts": 3})
        if r != {"ack": True}:
            violation(f"callback_failed should be acked, got {r}")
        print("    callback failed after 3 attempts (reported to Bob)")
        return result

    call_id = uuid.uuid4().hex
    with lock:
        for q in state["queue"]:
            if q["missed_call_id"] == mc_id:
                q["status"] = "calling"
        state["active"][call_id] = {"call_id": call_id, "phone": phone, "line_id": LINE_ID, "started_at": now(),
                                    "current_action": "waiting_for_bob"}
    resp = event({"type": "call_started", "call_id": call_id, "missed_call_id": mc_id, "phone": phone,
                  "line_id": LINE_ID})
    after_listen, hung_up = False, False
    for _ in range(60):
        if resp is None:
            break
        problems = contract.action_list_problems(resp)
        for p in problems:
            violation(f"action list: {p}")
        if problems:
            break
        actions = resp["actions"]
        clips = [clip_of(a) for a in actions if a["type"] == "play"]
        heard.extend(clips)
        final = actions[-1]
        _set_action(call_id, final["type"])
        time.sleep(pace)
        print(f"    BOB  {' + '.join(c.split('/')[1] for c in clips) or '-'}  -> {final['type']}")
        if final["type"] == "hangup":
            break
        if scn.get("hangup_after_questions") is not None and patient.questions >= scn["hangup_after_questions"] \
                and any("q_" in c for c in clips):
            print("    PAT  (hangs up)")
            event({"type": "action_result", "call_id": call_id, "action_id": final["action_id"],
                   "status": "caller_hung_up"})
            hung_up = True
            break
        base = {"type": "action_result", "call_id": call_id, "action_id": final["action_id"]}
        if final["type"] == "keypad":
            key = patient.press([c.split("/")[1] for c in clips])
            print(f"    PAT  {'[' + key + ']' if key else '(no key, timeout)'}")
            ev = {**base, "status": "ok", "digits": key} if key else {**base, "status": "timeout"}
            after_listen = False
        else:  # listen
            if scn.get("silent"):
                print("    PAT  (says nothing)")
                ev = {**base, "status": "no_input"}
            else:
                path, ms = patient.recording()
                print(f"    PAT  says: {v['transcript'][:70]}  ({ms / 1000:.1f}s)")
                ev = {**base, "status": "ok", "recording_path": path, "duration_ms": ms}
            after_listen = True
        resp = event(ev, after_listen=after_listen)

    reason = "caller_hung_up" if hung_up else "completed"
    r = event({"type": "call_ended", "call_id": call_id, "reason": reason})
    if r != {"ack": True}:
        violation(f"call_ended should be acked, got {r}")
    with lock:
        state["active"].pop(call_id, None)
    _dequeue(mc_id)
    result["questions"] = patient.questions
    return result


def _set_action(call_id: str, kind: str) -> None:
    with lock:
        if call_id in state["active"]:
            state["active"][call_id]["current_action"] = kind


def _dequeue(mc_id: str) -> None:
    with lock:
        state["queue"] = [q for q in state["queue"] if q["missed_call_id"] != mc_id]


def outcome_of(heard: list[str]) -> tuple[str | None, str | None, str | None]:
    names = [h.split("/")[1] for h in heard]
    outcome = next((n.removeprefix("out_") for n in names
                    if n in ("out_emergency", "out_high", "out_uncertain", "out_appointment")), None)
    clinic = next((n.removeprefix("clinic_") for n in names if n.startswith("clinic_")), None)
    digits = "".join(n.removeprefix("digit_") for n in names[names.index("case_number") + 1:]
                     if n.startswith("digit_")) if "case_number" in names else None
    return outcome, clinic, digits


def sms_to(phone: str, since: int, wait_s: float = 6.0) -> list[dict]:
    """SMS Bob asked Stuart to send to `phone` since index `since`. Bob's worker delivers its outbox
    about once a second, so poll for a few seconds before concluding nothing was sent."""
    deadline = time.time() + wait_s
    while True:
        with lock:
            got = [m for m in state["sms"][since:] if m["to"] == phone]
        if got or time.time() > deadline:
            return got
        time.sleep(0.25)


def check(label: str, ok: bool, detail: str, failures: list[str]) -> None:
    print(f"    {'ok ' if ok else 'XX '} {label}: {detail}")
    if not ok:
        failures.append(f"{label}: {detail}")


def run_scenario(scn: dict, vignettes: dict, pace: float, ctx: dict) -> list[str]:
    failures: list[str] = []
    steps = scn["steps"] if scn.get("kind") == "steps" else [{"call": scn, "expect": scn.get("expect", {})}]
    for step in steps:
        since = len(state["sms"])
        if "sms" in step:
            text = step["sms"]["text"].replace("{last_code}", ctx.get("last_code") or "0000")
            print(f"    SMS  from {step['sms']['from']}: {text}")
            r = send_event({"type": "sms_received", "message_id": uuid.uuid4().hex, "phone": step["sms"]["from"],
                            "line_id": LINE_ID, "text": text})
            if r != {"ack": True}:
                violation(f"sms_received should be acked, got {r}")
            if to := step.get("expect_sms_to"):
                got = sms_to(to, since)
                check("reply SMS", bool(got), got[0]["text"] if got else f"none to {to}", failures)
            if to := step.get("expect_no_sms_to"):
                got = sms_to(to, since)
                check("no reply to stranger", not got, "none sent" if not got else got[0]["text"], failures)
            continue
        call, expect = step["call"], step.get("expect", {})
        res = run_call(call, vignettes, pace)
        outcome, clinic, code = outcome_of(res["heard"])
        ctx["last_code"] = code or ctx.get("last_code")
        if "callback" in expect:
            check("callback", res["callback"] == expect["callback"], f"callback={res['callback']}", failures)
        if "outcome" in expect:
            check("outcome", outcome == expect["outcome"], f"heard {outcome} (expected {expect['outcome']})", failures)
        if "clinic" in expect:
            check("clinic", clinic == expect["clinic"], f"named {clinic} (expected {expect['clinic']})", failures)
        for key in ("alert_sms_to", "sms_to"):
            if to := expect.get(key):
                got = sms_to(to, since)
                check(key.replace("_", " "), bool(got), got[0]["text"][:90] if got else f"none to {to}", failures)
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("names", nargs="*")
    r.add_argument("--pace", type=float, default=0.0, help="seconds to wait per action (for watching live)")
    sub.add_parser("serve")
    args = ap.parse_args()
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    serve_in_background()
    print(f"Fake Stuart on {config.STUART_URL}; Bob at {config.BOB_URL}")
    if args.cmd == "serve":
        print("Serving /v1/status, /v1/sms, /v1/sync. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0
    try:
        h = httpx.get(f"{config.BOB_URL}/v1/health", headers=HEADERS, timeout=2).json()
        if h != {"ok": True, "module": "bob"}:
            violation(f"Bob /v1/health returned {h}")
    except Exception as e:  # noqa: BLE001
        print(f"Bob is not reachable at {config.BOB_URL} ({e}). Start it: python -m vitamin_bob.server")
        return 1

    scenarios = json.loads((Path(__file__).with_name("scenarios.json")).read_text(encoding="utf-8"))["scenarios"]
    if args.names:
        scenarios = [s for s in scenarios if s["name"] in args.names]
    vignettes, ctx, results = load_vignettes(), {}, []
    for scn in scenarios:
        print(f"\n== {scn['name']}")
        before = len(violations)
        failures = run_scenario(scn, vignettes, args.pace, ctx)
        results.append((scn["name"], failures, len(violations) - before))
    time.sleep(1.5)  # let late sms_status / sync_status events land

    print("\n================ SUMMARY ================")
    for name, failures, v in results:
        print(f"  {'PASS' if not failures and not v else 'FAIL'}  {name}" + (f"  ({'; '.join(failures)})" if failures else "")
              + (f"  [{v} contract violation(s)]" if v else ""))
    with lock:
        print(f"\n  SMS Bob asked Stuart to send: {len(state['sms'])}   sync records: {len(state['sync'])}"
              f"   largest sync payload: {max((len(contract.compact(s['payload']).encode()) for s in state['sync']), default=0)} bytes")
    print(f"  Contract violations: {len(violations)}")
    bad = sum(1 for _, f, v in results if f or v)
    print(f"  Scenarios passed: {len(results) - bad}/{len(results)}")
    return 1 if bad or violations else 0


if __name__ == "__main__":
    sys.exit(main())
