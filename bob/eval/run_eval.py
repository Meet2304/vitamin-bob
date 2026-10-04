"""Run every vignette through the full call flow with a simulated patient, then report per language.

    python eval/run_eval.py                         # keyword baseline, text (no model needed)
    python eval/run_eval.py --mode gemma            # Gemma form filling on the reference text
    python eval/run_eval.py --mode audio            # Gemma on the recordings (transcribe + fill), the real path
    python eval/run_eval.py --mode all              # all three; writes eval/results_summary.json for the dashboard

The simulated patient answers each keypad question from the vignette's ground truth
(1 = yes, 2 = no, 3 = don't know; days then #), exactly like a real caller would.

Metrics, in order of importance:
  missed_urgent   expected EMERGENCY/HIGH but Bob said MEDIUM/LOW. Target: 0.
  emerg_to_clinic expected EMERGENCY but Bob said something else (clinic, not 108).
  accuracy        exact tier match.
  uncertain_rate  share of calls handed to a clinician as UNCERTAIN. The metric to drive down.
  avg_questions   keypad questions per call. Lower = understanding did more of the work.
  misreads        values filled from the description that contradict ground truth.

Data: eval/vignettes.jsonl (Hindi, 38 synthetic, written by the team), vignettes_gu.jsonl (Gujarati,
16 synthetic), vignettes_recorded.jsonl (10 real recordings by the team; audio in data/eval_audio).
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vitamin_bob.extract import KeywordExtractor  # noqa: E402
from vitamin_bob.protocol import RED_FLAGS, SYMPTOMS  # noqa: E402
from vitamin_bob.prompts import data_dir  # noqa: E402
from vitamin_bob.rules import NO, UNKNOWN, YES, Case, classify  # noqa: E402
from vitamin_bob.session import CallSession  # noqa: E402

URGENT = {"EMERGENCY", "HIGH"}
EVAL_DIR = Path(__file__).parent


def truth_of(v: dict) -> dict:
    sym = {}
    for s in SYMPTOMS:
        if s in v["symptoms"]:
            d = v["symptoms"][s]
            sym[s] = {"present": YES, "days": d if isinstance(d, int) else None}
        elif s in v.get("unknown_symptoms", []):
            sym[s] = {"present": UNKNOWN, "days": None}
        else:
            sym[s] = {"present": NO, "days": None}
    flags = {}
    for f in RED_FLAGS:
        if f in v["flags"]:
            flags[f] = YES
        elif f in v.get("unknown_flags", []):
            flags[f] = UNKNOWN
        else:
            flags[f] = NO
    return {"symptoms": sym, "flags": flags}


def patient_key(q, truth) -> str:
    kind, item = q.qid.split(":", 1)
    if kind == "days":
        d = truth["symptoms"][item]["days"]
        return f"{d}#" if d else "#"
    val = truth["symptoms"][item]["present"] if kind == "symptom" else truth["flags"][item]
    return {YES: "1", NO: "2", UNKNOWN: "3"}[val]


def audio_path(v: dict) -> Path:
    return data_dir() / "eval_audio" / v["lang"] / f"{v['id']}.wav"


def run_one(v: dict, mode: str) -> dict:
    truth = truth_of(v)
    s = CallSession(None)
    s.set_age(v["age"])
    t0 = time.time()
    transcript = v["transcript"]
    if mode == "keyword":
        ext = KeywordExtractor()(transcript)
    elif mode == "gemma":
        from vitamin_bob.understand import GemmaExtractor  # noqa: PLC0415
        ext = GemmaExtractor(v["lang"])(transcript)
    else:  # audio: the real path, recording -> transcript -> form, with every fallback
        from vitamin_bob.understand import understand  # noqa: PLC0415
        u = understand(audio_path(v), v["lang"])
        transcript, ext = u.transcript, u.extraction
    ms = int((time.time() - t0) * 1000)
    s.apply(transcript, ext)
    while (q := s.next_question()) is not None:
        s.answer(q, patient_key(q, truth))
    result = classify(s.case)

    misreads = []
    for sym in SYMPTOMS:
        got, exp = ext["symptoms"][sym], truth["symptoms"][sym]
        if got["present"] != UNKNOWN and exp["present"] != UNKNOWN and got["present"] != exp["present"]:
            misreads.append(f"{sym}={got['present']}")
        if got["days"] is not None and exp["days"] is not None and got["days"] != exp["days"]:
            misreads.append(f"{sym}_days={got['days']}(truth {exp['days']})")
    for f in RED_FLAGS:
        got, exp = ext["flags"][f], truth["flags"][f]
        if got != UNKNOWN and exp != UNKNOWN and got != exp:
            misreads.append(f"{f}={got}")
    return {"id": v["id"], "lang": v["lang"], "expected": v["expected"], "got": result.tier.name,
            "questions": len(s.asked), "misreads": misreads, "rejected": ext.get("rejected", []),
            "added_by_keyword": ext.get("added_by_keyword", []), "ms": ms,
            "transcript": transcript if mode == "audio" else None}


def rules_audit(vignettes) -> list[str]:
    """Do the rules, given perfect information, agree with the human label? Checks the protocol."""
    issues = []
    ages = {"1": "infant_under_2m", "2": "child_under_5", "3": "older_child_or_adult"}
    for v in vignettes:
        t = truth_of(v)
        tier = classify(Case(age_group=ages[v["age"]], symptoms=t["symptoms"], flags=t["flags"])).tier.name
        if tier != v["expected"]:
            issues.append(f"{v['id']}: label {v['expected']}, rules give {tier}")
    return issues


def summarise(name: str, rows: list[dict], verbose: bool = True) -> dict:
    n = len(rows)
    missed = [r for r in rows if r["expected"] in URGENT and r["got"] in {"MEDIUM", "LOW"}]
    e2c = [r for r in rows if r["expected"] == "EMERGENCY" and r["got"] != "EMERGENCY"]
    summary = {
        "set": name, "n": n, "missed_urgent": len(missed), "emerg_to_clinic": len(e2c),
        "accuracy": round(sum(r["expected"] == r["got"] for r in rows) / n, 3),
        "uncertain_rate": round(sum(r["got"] == "UNCERTAIN" for r in rows) / n, 3),
        "avg_questions": round(sum(r["questions"] for r in rows) / n, 2),
        "misreads": sum(len(r["misreads"]) for r in rows),
        "avg_understand_s": round(sum(r["ms"] for r in rows) / n / 1000, 1),
    }
    print(f"\n=== {name} ===")
    for k, val in summary.items():
        if k != "set":
            print(f"  {k:17} {val}")
    if verbose:
        conf = Counter((r["expected"], r["got"]) for r in rows)
        print("  confusion (expected -> got):")
        for (e, g), c in sorted(conf.items()):
            mark = "" if e == g else ("   <-- MISSED URGENT" if e in URGENT and g in {"MEDIUM", "LOW"} else "   <-")
            print(f"    {e:10} -> {g:10} x{c}{mark}")
        for r in rows:
            if r["expected"] != r["got"] or r["misreads"] or r["added_by_keyword"]:
                print(f"    {r['id']}: expected {r['expected']}, got {r['got']}, q={r['questions']}"
                      + (f", misreads {r['misreads']}" if r["misreads"] else "")
                      + (f", dropped (no evidence) {r['rejected']}" if r["rejected"] else "")
                      + (f", keyword added {r['added_by_keyword']}" if r["added_by_keyword"] else ""))
    return summary


def load(name: str) -> list[dict]:
    rows = [json.loads(line) for line in open(EVAL_DIR / name, encoding="utf-8") if line.strip()]
    for v in rows:
        v.setdefault("lang", "hi")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["keyword", "gemma", "audio", "all"], default="keyword")
    ap.add_argument("--lang", choices=["hi", "gu", "all"], default="all")
    ap.add_argument("--out", default=str(EVAL_DIR / "results.json"))
    args = ap.parse_args()
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    text_sets = load("vignettes.jsonl") + load("vignettes_gu.jsonl")
    recorded = load("vignettes_recorded.jsonl")
    langs = ["hi", "gu"] if args.lang == "all" else [args.lang]
    print(f"{len(text_sets)} synthetic text vignettes, {len(recorded)} real recordings (written/recorded by the team)")
    issues = rules_audit(text_sets + recorded)
    print(f"\nRules audit with perfect information: {len(issues)} disagreement(s)")
    for i in issues:
        print(f"  {i}")

    modes = ["keyword", "gemma", "audio"] if args.mode == "all" else [args.mode]
    if any(m != "keyword" for m in modes):
        from vitamin_bob.understand import model_available  # noqa: PLC0415
        if not model_available(timeout=2):
            print("\nGemma is not running (tools/start_model.cmd); only the keyword baseline can run.")
            modes = ["keyword"]

    results, summaries = {}, []
    for mode in modes:
        for lang in langs:
            if mode == "audio":
                vs = [v for v in recorded if v["lang"] == lang and audio_path(v).exists()]
                label = f"{mode} / {lang} / real recordings"
            else:
                vs = [v for v in text_sets + recorded if v["lang"] == lang]
                label = f"{mode} / {lang} / text"
            if not vs:
                continue
            rows = [run_one(v, mode) for v in vs]
            s = summarise(label, rows)
            s.update(mode=mode, lang=lang)
            summaries.append(s)
            results[label] = {"summary": s, "rows": rows}

    json.dump(results, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    (EVAL_DIR / "results_summary.json").write_text(json.dumps(
        {"at": time.strftime("%Y-%m-%d %H:%M"), "summaries": summaries}, indent=1), encoding="utf-8")
    print(f"\nSaved {args.out} and eval/results_summary.json")
    print("\n  set                                  n  missed  e->clinic  accuracy  uncertain  questions  misreads")
    for s in summaries:
        print(f"  {s['set']:35} {s['n']:3} {s['missed_urgent']:6} {s['emerg_to_clinic']:9} {s['accuracy']:9.0%}"
              f" {s['uncertain_rate']:10.0%} {s['avg_questions']:10} {s['misreads']:9}")


if __name__ == "__main__":
    main()
