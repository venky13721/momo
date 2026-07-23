#!/usr/bin/env python3
"""Score extraction predictions against the gold eval set.

    python3 eval/score.py eval/predictions-qwen3b.jsonl [--gate]

Scoring:
- Predicted tasks are aligned to gold tasks per utterance by best title
  token-F1 (greedy). Unmatched gold tasks count every field as wrong.
- Hard fields (the Phase 0 ≥90% gate): title, owner, urgency, due,
  waiting_on, discuss_with.
    - title: token-F1 ≥ 0.5 after normalization.
    - owner / waiting_on / urgency / discuss_with: exact match (case-insensitive).
    - due: exact date match (null == null counts).
- effort_minutes is reported separately (correct within a factor of 2) —
  it is model-estimated and not part of the gate.
- description and confidence are not scored.

--gate exits 1 if hard-field accuracy < 0.90 (the Phase 0 exit criterion).
"""

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
HARD_FIELDS = ["title", "owner", "urgency", "due", "waiting_on", "discuss_with"]


def norm_tokens(s):
    return [t for t in re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).split() if t]


def token_f1(a, b):
    ta, tb = norm_tokens(a), norm_tokens(b)
    if not ta or not tb:
        return 0.0
    common = 0
    pool = list(tb)
    for t in ta:
        if t in pool:
            pool.remove(t)
            common += 1
    if common == 0:
        return 0.0
    p, r = common / len(ta), common / len(tb)
    return 2 * p * r / (p + r)


def norm_person(v):
    if v is None:
        return None
    return str(v).strip().lower()


def align(gold_tasks, pred_tasks):
    """Greedy best-title-F1 alignment; returns list of (gold, pred|None)."""
    pairs = sorted(
        ((token_f1(g.get("title", ""), p.get("title", "")), gi, pi)
         for gi, g in enumerate(gold_tasks)
         for pi, p in enumerate(pred_tasks)),
        reverse=True,
    )
    gold_used, pred_used, match = set(), set(), {}
    for _, gi, pi in pairs:
        if gi not in gold_used and pi not in pred_used:
            gold_used.add(gi)
            pred_used.add(pi)
            match[gi] = pi
    return [(g, pred_tasks[match[gi]] if gi in match else None) for gi, g in enumerate(gold_tasks)]


def score_field(field, gold, pred):
    if pred is None:
        return False
    g, p = gold.get(field), pred.get(field)
    if field == "title":
        return token_f1(g, p) >= 0.5
    if field in ("owner", "waiting_on", "discuss_with"):
        return norm_person(g) == norm_person(p)
    if field == "urgency":
        return norm_person(g) == norm_person(p)
    if field == "due":
        return (g is None and p is None) or (g is not None and p is not None and str(g) == str(p))
    raise ValueError(field)


def effort_ok(gold, pred):
    if pred is None:
        return False
    g, p = gold.get("effort_minutes"), pred.get("effort_minutes")
    if not isinstance(p, (int, float)) or not isinstance(g, (int, float)) or p <= 0:
        return False
    return g / 2 <= p <= g * 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("--gold", default=str(ROOT / "utterances.jsonl"))
    ap.add_argument("--gate", action="store_true", help="exit 1 if hard-field accuracy < 0.90")
    args = ap.parse_args()

    gold = {u["id"]: u for u in map(json.loads, pathlib.Path(args.gold).read_text().splitlines()) if u}
    preds = {r["id"]: r for r in map(json.loads, pathlib.Path(args.predictions).read_text().splitlines()) if r}

    field_stats = defaultdict(lambda: [0, 0])   # field -> [correct, total]
    cat_stats = defaultdict(lambda: [0, 0])     # category -> [correct, total] (hard fields)
    effort = [0, 0]
    count_exact = [0, 0]
    misses = []

    for uid, u in gold.items():
        row = preds.get(uid, {})
        ptasks = (row.get("predicted") or {}).get("tasks") or []
        ptasks = [p for p in ptasks if isinstance(p, dict)]
        count_exact[1] += 1
        count_exact[0] += int(len(ptasks) == len(u["tasks"]))
        for g, p in align(u["tasks"], ptasks):
            for f in HARD_FIELDS:
                ok = score_field(f, g, p)
                field_stats[f][0] += ok
                field_stats[f][1] += 1
                cat_stats[u["category"]][0] += ok
                cat_stats[u["category"]][1] += 1
                if not ok:
                    misses.append((uid, f, g.get(f), None if p is None else p.get(f)))
            effort[0] += effort_ok(g, p)
            effort[1] += 1

    hard_correct = sum(v[0] for v in field_stats.values())
    hard_total = sum(v[1] for v in field_stats.values())
    overall = hard_correct / hard_total if hard_total else 0.0

    print(f"\n== Overall hard-field accuracy: {overall:.1%} ({hard_correct}/{hard_total})  [gate: >=90%]\n")
    print("Per field:")
    for f in HARD_FIELDS:
        c, t = field_stats[f]
        print(f"  {f:<14} {c/t:>6.1%}  ({c}/{t})")
    print(f"  {'effort(x2 tol)':<14} {effort[0]/effort[1]:>6.1%}  ({effort[0]}/{effort[1]})  [reported, not gated]")
    print(f"  {'task count':<14} {count_exact[0]/count_exact[1]:>6.1%}  ({count_exact[0]}/{count_exact[1]})  [reported, not gated]")
    print("\nPer category (hard fields):")
    for cat, (c, t) in sorted(cat_stats.items()):
        print(f"  {cat:<14} {c/t:>6.1%}  ({c}/{t})")
    if misses:
        print(f"\nMisses ({len(misses)}):")
        for uid, f, g, p in misses:
            print(f"  {uid} {f}: gold={g!r} pred={p!r}")

    if args.gate and overall < 0.90:
        print("\nGATE FAILED: below 90% hard-field accuracy", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
