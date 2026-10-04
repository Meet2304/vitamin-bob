"""The call conversation as a contract state machine: one event in, one action list out.

    call_started   -> language menu (repeats until a key is pressed; a known caller skips it)
    menu key       -> welcome + who is sick (keypad)
    age key        -> describe (beep, listen <= 25 s)
    recording      -> understand (Gemma, or keyword fallback) -> only the questions still needed
    answers        -> tier (deterministic rules) -> route -> book / alert -> outcome -> hangup
    call_ended     -> if no tier yet: UNCERTAIN (never lower than what is known) + clinician alert

State lives in bob.db (sessions.state), so every step survives a restart and duplicates are cheap.
Everything Bob says is a list of pre-recorded clips (prompts.py); the model never speaks.
"""

import json
from pathlib import Path

from . import alerts, clinics, config, db, sync
from .contract import MAX_LISTEN_MS
from .privacy import patient_key
from .prompts import SYSTEM, clip_path, lang_for_key, languages, outcome_keys, question_keys, text_of
from .protocol import AGE_GROUPS, AGE_LABEL_EN, RED_FLAGS, SYMPTOM_LABEL_EN, Tier
from .rules import YES, classify
from .session import CallSession, Question, session_from_dict, session_to_dict
from .understand import understand

MENU_TRIES = 6        # ~1 minute of menu repeats before giving up (patient may not have picked up yet)
KEY_TRIES = 3         # asks per keypad question before treating it as "don't know"
LISTEN_TRIES = 2
MIN_SPEECH_MS = 1200  # a shorter recording is treated as silence
KEY_TIMEOUT_MS = 8000
DAYS_TIMEOUT_MS = 12000


# --- action builders (contract 7.3) -----------------------------------------------------------
def _id() -> str:
    return db.new_id()[:12]


def plays(lang: str, keys: list[str]) -> list[dict]:
    return [{"type": "play", "action_id": _id(), "audio_path": str(clip_path(lang, k))} for k in keys]


def keypad(max_digits: int = 1, timeout_ms: int = KEY_TIMEOUT_MS, terminator: str | None = None) -> dict:
    return {"type": "keypad", "action_id": _id(), "max_digits": max_digits, "timeout_ms": timeout_ms,
            "terminator": terminator}


def listen() -> dict:
    return {"type": "listen", "action_id": _id(), "max_ms": MAX_LISTEN_MS, "end_silence_ms": 2500}


def hangup() -> dict:
    return {"type": "hangup", "action_id": _id()}


# --- persistence ------------------------------------------------------------------------------
def log(call_id: str, who: str, kind: str, text: str, detail: dict | None = None) -> None:
    db.ex("INSERT INTO turns (call_id, at, who, kind, text, detail) VALUES (?, ?, ?, ?, ?, ?)",
          call_id, db.iso(), who, kind, text, json.dumps(detail or {}, ensure_ascii=False))


def load(call_id: str) -> tuple[dict, dict] | None:
    row = db.one("SELECT * FROM sessions WHERE call_id=?", call_id)
    return (row, json.loads(row["state"])) if row else None


def save(call_id: str, st: dict, **cols) -> None:
    sets = ", ".join(f"{k}=?" for k in ["state", "step", "lang", *cols])
    db.ex(f"UPDATE sessions SET {sets} WHERE call_id=?",
          json.dumps(st, ensure_ascii=False), st["step"], st["lang"], *cols.values(), call_id)


def respond(call_id: str, st: dict, lang: str, keys: list[str], final: dict, label: str) -> dict:
    """Build an action list, remember which action we await, and log what Bob says."""
    actions = plays(lang, keys) + [final]
    st["awaiting"] = final["action_id"]
    save(call_id, st)
    words = "(bilingual language menu)" if lang == SYSTEM and "lang_menu" in keys else text_of(lang, keys)
    log(call_id, "bob", label, words, {"clips": keys, "then": final["type"]})
    return {"actions": actions}


def _sys_or(lang: str | None, keys: list[str]) -> list[tuple[str, list[str]]]:
    return [(lang or SYSTEM, keys)]


# --- events -----------------------------------------------------------------------------------
def on_call_started(ev: dict) -> dict:
    call_id, phone = ev["call_id"], ev["phone"]
    hub_id = db.hub()["hub_id"]
    pkey = patient_key(phone)
    patient = db.one("SELECT * FROM patients WHERE patient_key=?", pkey)
    if not patient:
        patient = {"patient_id": db.new_id(), "preferred_lang": None, "village_id": None}
        db.ex("INSERT INTO patients VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?)",
              patient["patient_id"], hub_id, pkey, phone, db.iso())
    st = {"step": "menu", "lang": None, "tries": 0, "listen_tries": 0, "qid": None, "awaiting": None,
          "triage_id": None, "understanding": None, "session": session_to_dict(CallSession(None, phone=phone))}
    db.ex("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?, ?, ?, NULL, 'menu', '{}', ?, NULL, NULL)",
          call_id, hub_id, ev.get("missed_call_id"), patient["patient_id"], phone, ev.get("line_id"), db.iso())
    log(call_id, "system", "call_started", f"Callback placed on {ev.get('line_id')}")

    enabled = {lang["code"] for lang in languages()}
    if patient["preferred_lang"] in enabled:
        # A known caller skips the menu. who_is_sick repeats on timeout, so a partly missed start is fine.
        st["lang"], st["step"] = patient["preferred_lang"], "who"
        log(call_id, "system", "known_caller", f"Known caller: language {st['lang']}, menu skipped")
        return respond(call_id, st, st["lang"], ["welcome", "who_is_sick"], keypad(), "ask_who")
    return respond(call_id, st, SYSTEM, ["lang_menu"], keypad(timeout_ms=6000), "language_menu")


def on_action_result(ev: dict) -> dict:
    loaded = load(ev["call_id"])
    if not loaded:
        db.warn("conversation", f"action_result for unknown call {ev['call_id']}")
        return {"actions": [hangup()]}
    row, st = loaded
    call_id, status, digits = ev["call_id"], ev["status"], (ev.get("digits") or "").strip()
    if st.get("awaiting") and ev["action_id"] != st["awaiting"]:
        db.warn("conversation", f"{call_id}: result for {ev['action_id']}, expected {st['awaiting']}")
    if status == "caller_hung_up" or st["step"] == "done":
        return {"actions": [hangup()]}
    if digits:
        log(call_id, "patient", "keypad", digits, {"step": st["step"]})
    elif status != "ok":
        log(call_id, "patient", status, f"({status.replace('_', ' ')})", {"step": st["step"]})

    step = st["step"]
    if step == "menu":
        lang = lang_for_key(digits[:1]) if status == "ok" else None
        if lang:
            st.update(lang=lang, step="who", tries=0)
            db.ex("UPDATE patients SET preferred_lang=? WHERE patient_id=?", lang, row["patient_id"])
            return respond(call_id, st, lang, ["welcome", "who_is_sick"], keypad(), "ask_who")
        st["tries"] += 1
        if st["tries"] < MENU_TRIES:
            return respond(call_id, st, SYSTEM, ["lang_menu"], keypad(timeout_ms=6000), "language_menu")
        return give_up(call_id, st, "no language chosen")

    lang = st["lang"]
    s = session_from_dict(st["session"])

    if step == "who":
        if status == "ok" and digits[:1] in AGE_GROUPS:
            s.set_age(digits[:1])
            st.update(session=session_to_dict(s), step="listen", tries=0)
            return ask_describe(call_id, st, ["describe"])
        st["tries"] += 1
        if st["tries"] < KEY_TRIES:
            nudge = "invalid_key" if digits else "no_input"
            return respond(call_id, st, lang, [nudge, "who_is_sick"], keypad(), "ask_who")
        log(call_id, "bob", "note", "Age group not given; continuing (this keeps the case UNCERTAIN)")
        st.update(step="listen", tries=0)
        return ask_describe(call_id, st, ["describe"])

    if step == "listen":
        rec = ev.get("recording_path")
        if status == "ok" and rec and (ev.get("duration_ms") or 0) >= MIN_SPEECH_MS:
            return after_listen(call_id, st, s, Path(rec))
        _delete_recording(rec)
        st["listen_tries"] += 1
        if st["listen_tries"] < LISTEN_TRIES:
            return ask_describe(call_id, st, ["describe_retry"])
        log(call_id, "bob", "note", "No usable description; asking every question on the keypad")
        return next_question(call_id, st, s)

    if step == "question":
        q = Question(st["qid"], "", "days" if st["qid"].startswith("days:") else "yes_no")
        if q.kind == "days":
            s.answer(q, digits if status == "ok" else "#")
            return next_question(call_id, st, s)
        if status == "ok" and digits[:1] in ("1", "2", "3"):
            s.answer(q, digits[:1])
            return next_question(call_id, st, s)
        st["tries"] += 1
        if st["tries"] < KEY_TRIES:
            nudge = "invalid_key" if digits else "no_input"
            return respond(call_id, st, lang, [nudge, *question_keys(q.qid)], keypad(), "ask_question")
        s.answer(q, "3")  # never answered: "don't know", which keeps the case from looking safer than it is
        return next_question(call_id, st, s)

    db.warn("conversation", f"{call_id}: unexpected step {step}")
    return {"actions": [hangup()]}


def ask_describe(call_id: str, st: dict, keys: list[str]) -> dict:
    st["awaiting"] = None
    actions = plays(st["lang"], keys) + plays(SYSTEM, ["beep"]) + [listen()]
    st["awaiting"] = actions[-1]["action_id"]
    save(call_id, st)
    log(call_id, "bob", "ask_describe", text_of(st["lang"], keys) + " [beep]", {"clips": keys + ["beep"]})
    return {"actions": actions}


def after_listen(call_id: str, st: dict, s: CallSession, rec: Path) -> dict:
    sidecar = rec.with_suffix(".transcript.txt")
    side = sidecar.read_text(encoding="utf-8") if sidecar.exists() else None
    u = understand(rec, st["lang"], sidecar_transcript=side)
    _delete_recording(str(rec))  # raw audio is never kept once processed
    s.apply(u.transcript, u.extraction)
    understood = {k: v for k, v in s.case.source.items() if v == "description"}
    st["understanding"] = {"engine": u.engine, "ms": u.ms, "notes": u.notes, "rejected": u.extraction["rejected"]}
    log(call_id, "patient", "description", u.transcript or "(nothing understood)",
        {"engine": u.engine, "ms": u.ms})
    log(call_id, "bob", "understood",
        ", ".join(_label(k) for k in understood) or "nothing from the description",
        {"items": list(understood), "rejected": u.extraction["rejected"], "notes": u.notes,
         "log": [m for who, m in s.log if who == "bob"]})
    return next_question(call_id, st, s)


def next_question(call_id: str, st: dict, s: CallSession) -> dict:
    q = s.next_question()
    if q is None:
        return finish(call_id, st, s)
    st.update(step="question", qid=q.qid, tries=0, session=session_to_dict(s))
    final = keypad(3, DAYS_TIMEOUT_MS, "#") if q.kind == "days" else keypad()
    return respond(call_id, st, st["lang"], question_keys(q.qid), final, "ask_question")


# --- outcome ----------------------------------------------------------------------------------
def _label(key: str) -> str:
    base = key.removesuffix("_days")
    name = SYMPTOM_LABEL_EN.get(base) or RED_FLAGS.get(base, {}).get("en", base)
    return f"{name} duration" if key.endswith("_days") else name


def case_summary(s: CallSession, unknowns: list[str]) -> str:
    c = s.case
    parts = [AGE_LABEL_EN.get(c.age_group, "Age?")]
    syms = [SYMPTOM_LABEL_EN[k] + (f" {v['days']}d" if v["days"] else "") for k, v in c.symptoms.items()
            if v["present"] == YES]
    if syms:
        parts.append(", ".join(syms))
    red = [RED_FLAGS[f]["en"] for f, v in c.flags.items() if v == YES]
    if red:
        parts.append("RED: " + ", ".join(red))
    if unknowns:
        parts.append("UNSURE: " + ", ".join(unknowns[:4]) + ("..." if len(unknowns) > 4 else ""))
    return " | ".join(parts)


def finish(call_id: str, st: dict, s: CallSession, forced_reason: str | None = None) -> dict:
    """Classify, route, book or alert, sync, and tell the patient. Also used when a call ends early."""
    row = db.one("SELECT * FROM sessions WHERE call_id=?", call_id)
    result = classify(s.case)
    tier = result.tier
    reasons = list(result.reasons)
    if forced_reason:
        # The call ended before Bob could finish: never lower than what is known, at least UNCERTAIN.
        tier = max(tier, Tier.UNCERTAIN)
        reasons.append(f"Call ended before classification: {forced_reason} (UNCERTAIN, a clinician decides)")

    patient = db.one("SELECT * FROM patients WHERE patient_id=?", row["patient_id"]) if row else None
    clinic, skipped = clinics.choose(patient["village_id"] if patient else None)
    triage_id = db.new_id()
    appt = None
    if tier != Tier.EMERGENCY:
        appt = clinics.book(triage_id, clinic, tier, s.code)
    understanding = st.get("understanding") or {}
    engine = understanding.get("engine", "none")
    questions = len(s.asked)
    lang = st.get("lang")
    with db.tx() as c:
        c.execute("INSERT INTO triages VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            triage_id, db.hub()["hub_id"], call_id, s.code, config.PROTOCOL_VERSION, engine, lang, s.case.age_group,
            tier.name, json.dumps(reasons), json.dumps(result.unknowns),
            json.dumps({"symptoms": s.case.symptoms, "flags": s.case.flags, "source": s.case.source},
                       ensure_ascii=False),
            s.case.transcript, clinic["clinic_id"], json.dumps(skipped), "108" if tier == Tier.EMERGENCY else
            ("go_now" if tier >= Tier.UNCERTAIN else "appointment"), questions, understanding.get("ms"),
            db.iso(), int(bool(forced_reason))))
        if patient:
            c.execute("UPDATE patients SET last_clinic_id=? WHERE patient_id=?", (clinic["clinic_id"],
                                                                                   patient["patient_id"]))
    st.update(step="done", triage_id=triage_id, session=session_to_dict(s))
    save(call_id, st)

    route_note = f"Routed to {clinic['name']}" + (f"; skipped {', '.join(k['name'] + ' (' + k['reason'] + ')' for k in skipped)}"
                                                  if skipped else "")
    log(call_id, "bob", "triage", f"{tier.name}: " + "; ".join(reasons),
        {"tier": tier.name, "route": route_note, "skipped": skipped})
    if tier >= Tier.UNCERTAIN:
        alerts.raise_alert(tier=tier.name, kind="triage" if not forced_reason else "call_incomplete", code=s.code,
                           clinic_id=clinic["clinic_id"], summary=case_summary(s, result.unknowns),
                           phone=row["phone"] if row else None, triage_id=triage_id, call_id=call_id)
        log(call_id, "system", "alert", f"Clinician alert sent to {clinic['name']} (code {s.code})")
    started = db.parse(row["started_at"]) if row else db.now()
    try:
        sync.queue_triage(case={"age_group": s.case.age_group, "symptoms": s.case.symptoms, "flags": s.case.flags},
                          tier=tier, clinic_id=clinic["clinic_id"], questions=questions,
                          call_s=int((db.now() - started).total_seconds()), lang=lang, unknowns=len(result.unknowns),
                          engine=engine, patient_key=patient["patient_key"] if patient else "-",
                          forced=bool(forced_reason))
    except ValueError as e:
        db.warn("sync", str(e))

    if forced_reason or not lang:
        return {"actions": [hangup()]}
    keys = outcome_keys(tier, clinic["clinic_id"], (appt or {}).get("day") or "today", (appt or {}).get("hour") or 9,
                        s.code)
    return respond(call_id, st, lang, keys, hangup(), "outcome")


def give_up(call_id: str, st: dict, reason: str) -> dict:
    """Bob cannot continue the conversation: play the bilingual fallback and let a person follow up."""
    log(call_id, "bob", "note", f"Giving up: {reason}")
    s = session_from_dict(st["session"])
    finish(call_id, st, s, forced_reason=reason)
    actions = plays(SYSTEM, ["fallback"]) + [hangup()]
    return {"actions": actions}


def on_call_ended(ev: dict) -> dict:
    loaded = load(ev["call_id"])
    if not loaded:
        db.warn("conversation", f"call_ended for unknown call {ev['call_id']}")
        return {"ack": True}
    row, st = loaded
    db.ex("UPDATE sessions SET ended_at=?, end_reason=? WHERE call_id=?", db.iso(), ev["reason"], ev["call_id"])
    log(ev["call_id"], "system", "call_ended", f"Call ended: {ev['reason']}")
    if st["step"] != "done":
        interacted = db.one("SELECT 1 FROM turns WHERE call_id=? AND who='patient'", ev["call_id"])
        if ev["reason"] == "no_answer" and not interacted:
            # Stuart retries unanswered callbacks and reports callback_failed when it gives up;
            # that event raises the alert, so one patient does not produce one alert per attempt.
            log(ev["call_id"], "system", "note", "Not answered; waiting for Stuart's retry or callback_failed")
        else:
            finish(ev["call_id"], st, session_from_dict(st["session"]),
                   forced_reason={"caller_hung_up": "caller hung up", "failed": "call failed (Bob slow or unreachable)",
                                  "completed": "call completed without an outcome",
                                  "no_answer": "call dropped"}[ev["reason"]])
    return {"ack": True}


def on_callback_failed(ev: dict) -> dict:
    """Stuart could not reach a patient who asked for help: a person must try."""
    recent = db.one("SELECT 1 FROM alerts WHERE phone=? AND kind='callback_failed' AND acked_at IS NULL",
                    ev["phone"])
    if not recent:
        patient = db.one("SELECT * FROM patients WHERE patient_key=?", patient_key(ev["phone"]))
        clinic, _ = clinics.choose(patient["village_id"] if patient else None)
        code = f"{int(db.new_id()[:8], 16) % 10000:04d}"
        alerts.raise_alert(tier="UNCERTAIN", kind="callback_failed", code=code, clinic_id=clinic["clinic_id"],
                           summary=f"Missed call, callback failed after {ev['attempts']} attempts. Please call.",
                           phone=ev["phone"])
    return {"ack": True}


def _delete_recording(path: str | None) -> None:
    """Delete a processed recording, but only inside data/recordings (never an arbitrary path)."""
    if not path:
        return
    from .prompts import data_dir  # noqa: PLC0415
    p = Path(path).resolve()
    root = (data_dir() / "recordings").resolve()
    if root in p.parents:
        for f in (p, p.with_suffix(".transcript.txt")):
            f.unlink(missing_ok=True)
