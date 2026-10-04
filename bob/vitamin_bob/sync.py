"""What Bob sends to Central (via Stuart's SMS data link). Bob decides WHAT; Stuart decides HOW.

Every payload is compact JSON <= 200 bytes with short field names, and never contains a raw phone
number, a name or free text (checked by contract.sync_payload_problems before queueing).

triage        {h hub, d yymmdd, tm HHMM, c clinic, r tier E/H/U/M/L, a age i/c/a, s symptoms "F3C21D?",
               f red flags as 2-letter codes "CVFB", u unknown count, q keypad questions, du call seconds, l lang,
               o outcome 108/now/appt, x 1 if the call ended before classification,
               pv protocol, mv model, pk patient key (keyed hash)}
clinic_status {h, c clinic, st o/c/f/u, src s(ms)/m(issed call)/d(ashboard), d, tm}
daily_summary {h, d yymmdd, n cases, t {E,H,U,M,L}, ua unacknowledged alerts, q avg questions}
"""

from . import config, db, stuart_client
from .protocol import Tier

SYM = {"fever": "F", "cough": "C", "diarrhea": "D"}
FLAG = {"convulsions": "CV", "altered_consciousness": "AC", "severe_breathing_difficulty": "SB",
        "unable_to_drink": "UD", "vomits_everything": "VE", "stiff_neck": "SN", "fast_breathing": "FB",
        "blood_in_stool": "BS", "dehydration_signs": "DH"}
AGE = {"infant_under_2m": "i", "child_under_5": "c", "older_child_or_adult": "a"}


def _when() -> dict:
    # Date and time kept apart: a 10-digit run would look like a phone number to the privacy check.
    n = db.now()
    return {"d": n.strftime("%y%m%d"), "tm": n.strftime("%H%M")}


def model_code(engine: str) -> str:
    if engine.startswith("gemma"):
        return "g4e2b" if "e2b" in config.MODEL_NAME else "g4e4b" if "e4b" in config.MODEL_NAME else "gemma"
    return "kw1"


def triage_payload(*, case: dict, tier: Tier, clinic_id: str | None, questions: int, call_s: int,
                   lang: str | None, unknowns: int, engine: str, patient_key: str, forced: bool) -> dict:
    syms = "".join(SYM[s] + (str(v["days"]) if v["days"] else "?") for s, v in case["symptoms"].items()
                   if v["present"] == "yes")
    payload = {
        "h": db.hub()["hub_id"], **_when(), "c": clinic_id or "-", "r": tier.name[0], "a": AGE.get(case["age_group"], "?"),
        "s": syms, "f": "".join(FLAG[f] for f, v in case["flags"].items() if v == "yes"),
        "u": unknowns, "q": questions, "du": call_s, "l": lang or "?",
        "o": "108" if tier == Tier.EMERGENCY else "now" if tier >= Tier.UNCERTAIN else "appt",
        "pv": config.PROTOCOL_VERSION.replace("imci-draft-", "d"), "mv": model_code(engine), "pk": patient_key,
    }
    if forced:
        payload["x"] = 1
    # Safety valve: never exceed the contract's 200 bytes; drop the least important fields first.
    from .contract import MAX_SYNC_PAYLOAD_BYTES, compact  # noqa: PLC0415
    for optional in ("du", "u", "q", "pv", "l"):
        if len(compact(payload).encode()) <= MAX_SYNC_PAYLOAD_BYTES:
            break
        payload.pop(optional, None)
    return payload


def queue_triage(**kw) -> str:
    return stuart_client.queue_sync("triage", triage_payload(**kw))


def queue_clinic_status(clinic_id: str, status: str, source: str) -> str:
    src = {"sms": "s", "missed_call": "m", "dashboard": "d"}.get(source, source[:1])
    return stuart_client.queue_sync("clinic_status", {"h": db.hub()["hub_id"], "c": clinic_id, "st": status[0],
                                                      "src": src, **_when()})


def queue_daily_summary() -> str:
    today = db.now().strftime("%Y-%m-%d")
    rows = [r for r in db.q("SELECT tier, questions, created_at FROM triages") if r["created_at"].startswith(today)]
    tiers = {t: 0 for t in "EHUML"}
    for r in rows:
        tiers[r["tier"][0]] += 1
    unacked = db.one("SELECT COUNT(*) AS n FROM alerts WHERE acked_at IS NULL")["n"]
    avg_q = round(sum(r["questions"] or 0 for r in rows) / len(rows), 1) if rows else 0
    return stuart_client.queue_sync("daily_summary", {"h": db.hub()["hub_id"], "d": db.now().strftime("%y%m%d"),
                                                      "n": len(rows), "t": tiers, "ua": unacked, "q": avg_q})


def snapshot(limit: int = 25) -> dict:
    counts = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) AS n FROM sync_outbox GROUP BY status")}
    recent = db.q("SELECT record_id, kind, payload, status, created_at, acked_at FROM sync_outbox "
                  "ORDER BY created_at DESC LIMIT ?", limit)
    for r in recent:
        r["bytes"] = len(r["payload"].encode())
    return {"counts": counts, "recent": recent}
