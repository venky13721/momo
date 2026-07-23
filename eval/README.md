# Phase 0 eval harness

This directory defines what "working" means for the extraction pipeline. The Phase 0 exit gate: **≥90% hard-field accuracy** on this set, **<2s extraction latency** per utterance on the target Mac.

## Files

- `utterances.jsonl` — 52 utterances, 59 gold tasks, across 9 categories (`self`, `fire`, `delegation`, `waiting_on`, `discuss`, `vague`, `multi`, `small`, `code_switched`). Every line carries a fixed `reference_date` (2026-07-22, a Wednesday) so relative-date gold labels never rot.
- `people.json` — placeholder roster referenced by the gold labels. Keep ids stable while running the eval.
- `run_extraction.py` — feeds each utterance through a llama.cpp server with the system prompt (`prompts/extraction_system.txt`) and grammar (`grammars/task.gbnf`), writes predictions + latency.
- `score.py` — field-level scoring, per-category breakdown, miss list, and the `--gate` exit check.

## Running a model

```bash
# terminal 1 — any candidate SLM
llama-server -m ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096

# terminal 2
python3 eval/run_extraction.py --out eval/predictions-qwen3b.jsonl
python3 eval/score.py eval/predictions-qwen3b.jsonl --gate
```

Repeat per candidate (Qwen 2.5 3B, Gemma 3 4B, one larger control model) and compare the overall table. Prediction files (`predictions-*.jsonl`) are gitignored artifacts; commit conclusions to `spike/RESULTS.md`.

## Gold-label conventions

These are mirrored in the system prompt — if you change one, change both.

- **Dates** resolve against `reference_date`: weekday names → next occurrence; "next \<weekday\>" → following week; "end of week"/"this week" → Friday; weekend → Sunday; "end of month" → last day of month; fires → due today. Vague timing ("eventually", "next sprint", bare "next week") → `null`, never a guessed date.
- **urgency**: `fire` = drop-everything; `small` = under ~15 min quick task; `scheduled` = everything else (a `null` due does not make something `small`).
- **Delegation**: "ask/tell/get X to …" → `owner` = X, `waiting_on` null.
- **Waiting-on**: "X owes me / still waiting on X" → `owner` = X **and** `waiting_on` = X. The follow-up nudge cycle is the app's job, not a separate task.
- **Discuss**: "raise/align/discuss/give a heads-up to X" → `owner` = me, `discuss_with` = X.
- **Unknown people** (e.g. "finance") → the literal id `unknown`, never free text.
- `description` and `confidence` are unscored. `effort_minutes` is scored within a ×2 tolerance and reported outside the gate.

## Extending the set

Add real utterances as you catch yourself phrasing tasks — especially failure cases found after Phase 1 ships. Keep `reference_date` fixed for new entries and re-derive gold dates by hand. Aim to grow toward ~100 before tuning prompts against it (and hold out anything you tuned on).
