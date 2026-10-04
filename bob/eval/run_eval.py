"""Run every vignette through the full call flow with a simulated patient, then report.

    python eval/run_eval.py --extractor keyword
    python eval/run_eval.py --extractor llm
    python eval/run_eval.py --extractor both      # side-by-side: does the AI earn its place?

The simulated patient answers each keypad question from the vignette's ground truth
(1 = yes, 2 = no, 3 = don't know), exactly like a real caller would.

Metrics, in order of importance:
  missed_urgent   expected EMERGENCY/HIGH but Bob said MEDIUM/LOW. Target: 0.
  emerg_to_clinic expected EMERGENCY but Bob said HIGH/UNCERTAIN (sent to clinic, not 108).
  accuracy        exact tier match.
  uncertain_rate  share of calls handed to a clinician. The metric to drive down.
  avg_questions   keypad questions per call. Lower = understanding did more of the work.
  misreads        values the extractor filled that contradict ground truth (should be ~0).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vitamin_bob.extract import KeywordExtractor, LLMExtractor  # noqa: E402
from vitamin_bob.protocol import RED_FLAGS, SYMPTOMS, Tier  # noqa: E402
from vitamin_bob.rules import NO, UNKNOWN, YES, Case, classify  # noqa: E402
from vitamin_bob.session import CallSession  # noqa: E402

URGENT = {"EMERGENCY", "HIGH"}


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


def run_one(v: dict, extractor) -> dict:
    truth = truth_of(v)
    s = CallSession(extractor)
    s.set_age(v["age"])
    ext = s.describe(v["transcript"])
    while (q := s.next_question()) is not None:
        s.answer(q, patient_key(q, truth))
    out = s.finish()

    misreads = []
    for sym in SYMPTOMS:
        got = ext["symptoms"][sym]
        exp = truth["symptoms"][sym]
        if got["present"] != UNKNOWN and got["present"] != exp["present"] and exp["present"] != UNKNOWN:
            misreads.append(f"{sym}={got['present']}")
        if got["days"] is not None and exp["days"] is not None and got["days"] != exp["days"]:
            misreads.append(f"{sym}_days={got['days']}(truth {exp['days']})")
    for f in RED_FLAGS:
        got, exp = ext["flags"][f], truth["flags"][f]
        if got != UNKNOWN and exp != UNKNOWN and got != exp:
            misreads.append(f"{f}={got}")
    return {
        "id": v["id"],
        "expected": v["expected"],
        "got": out["tier"],
        "questions": out["questions_asked"],
        "misreads": misreads,
        "rejected": ext["rejected"],
    }


def rules_audit(vignettes) -> list[str]:
    """Do the rules, given perfect information, agree with the human label? Checks the protocol."""
    issues = []
    for v in vignettes:
        t = truth_of(v)
        c = Case(age_group={"1": "infant_under_2m", "2": "child_under_5", "3": "older_child_or_adult"}[v["age"]],
                 symptoms=t["symptoms"], flags=t["flags"])
        tier = classify(c).tier.name
        if tier != v["expected"]:
            issues.append(f"{v['id']}: label {v['expected']}, rules give {tier}")
    return issues


def report(name: str, rows: list[dict]) -> dict:
    n = len(rows)
    missed = [r for r in rows if r["expected"] in URGENT and r["got"] in {"MEDIUM", "LOW"}]
    e2c = [r for r in rows if r["expected"] == "EMERGENCY" and r["got"] != "EMERGENCY" and r not in missed]
    correct = sum(r["expected"] == r["got"] for r in rows)
    unc = sum(r["got"] == "UNCERTAIN" for r in rows)
    misreads = sum(len(r["misreads"]) for r in rows)
    summary = {
        "extractor": name,
        "n": n,
        "missed_urgent": len(missed),
        "emerg_to_clinic": len(e2c),
        "accuracy": round(correct / n, 3),
        "uncertain_rate": round(unc / n, 3),
        "avg_questions": round(sum(r["questions"] for r in rows) / n, 2),
        "misreads": misreads,
    }
    print(f"\n=== {name} ===")
    for k, val in summary.items():
        print(f"  {k:16} {val}")
    conf = Counter((r["expected"], r["got"]) for r in rows)
    print("  confusion (expected -> got):")
    for (e, g), c in sorted(conf.items()):
        mark = "" if e == g else ("   <-- MISSED URGENT" if e in URGENT and g in {"MEDIUM", "LOW"} else "   <-")
        print(f"    {e:10} -> {g:10} x{c}{mark}")
    for r in rows:
        if r["expected"] != r["got"] or r["misreads"]:
            print(f"    {r['id']}: expected {r['expected']}, got {r['got']}, q={r['questions']}"
                  f"{', misreads ' + str(r['misreads']) if r['misreads'] else ''}"
                  f"{', dropped ' + str(r['rejected']) if r['rejected'] else ''}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", choices=["keyword", "llm", "both"], default="both")
    ap.add_argument("--file", default=str(Path(__file__).parent / "vignettes.jsonl"))
    ap.add_argument("--out", default=str(Path(__file__).parent / "results.json"))
    args = ap.parse_args()

    vignettes = [json.loads(l) for l in open(args.file, encoding="utf-8") if l.strip()]
    print(f"{len(vignettes)} vignettes (synthetic, written by the team)")

    issues = rules_audit(vignettes)
    print(f"\nRules audit with perfect information: {len(issues)} disagreement(s)")
    for i in issues:
        print(f"  {i}")

    extractors = {"keyword": [KeywordExtractor()], "llm": [LLMExtractor()],
                  "both": [KeywordExtractor(), LLMExtractor()]}[args.extractor]
    results = {}
    for ex in extractors:
        rows = [run_one(v, ex) for v in vignettes]
        results[ex.name] = {"summary": report(ex.name, rows), "rows": rows}
    json.dump(results, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
