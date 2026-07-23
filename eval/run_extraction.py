#!/usr/bin/env python3
"""Run the extraction eval against a llama.cpp server.

Start the server first, e.g.:
    llama-server -m Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096

Then:
    python3 eval/run_extraction.py --out eval/predictions-qwen3b.jsonl

Writes one line per utterance: {"id", "predicted", "latency_ms", "error"}.
Score with eval/score.py.
"""

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_system_prompt(reference_date: str) -> str:
    template = (ROOT / "prompts" / "extraction_system.txt").read_text()
    people = json.loads((ROOT / "eval" / "people.json").read_text())["people"]
    people_lines = "\n".join(
        f'- id: {p["id"]} — {p["name"]} ({p["role"]}, {p["relationship"]}), aliases: {", ".join(p["aliases"])}'
        for p in people
    )
    weekday = dt.date.fromisoformat(reference_date).strftime("%A")
    return (
        template.replace("{{TODAY}}", reference_date)
        .replace("{{WEEKDAY}}", weekday)
        .replace("{{PEOPLE}}", people_lines)
    )


def call_server(base_url: str, system: str, utterance: str, grammar: str, timeout: float) -> str:
    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": utterance},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "grammar": grammar,  # llama-server extension; ignored by servers that lack it
        "cache_prompt": True,
    }
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--no-grammar", action="store_true", help="skip the GBNF grammar (for servers without grammar support)")
    args = ap.parse_args()

    grammar = "" if args.no_grammar else (ROOT / "grammars" / "task.gbnf").read_text()
    utterances = [json.loads(l) for l in (ROOT / "eval" / "utterances.jsonl").read_text().splitlines() if l.strip()]

    results = []
    for i, u in enumerate(utterances, 1):
        system = build_system_prompt(u["reference_date"])
        row = {"id": u["id"], "predicted": None, "latency_ms": None, "error": None}
        t0 = time.monotonic()
        try:
            raw = call_server(args.server, system, u["utterance"], grammar, args.timeout)
            row["latency_ms"] = round((time.monotonic() - t0) * 1000)
            row["predicted"] = json.loads(raw)
        except Exception as e:  # noqa: BLE001 — record and continue; score.py counts failures as wrong
            row["latency_ms"] = round((time.monotonic() - t0) * 1000)
            row["error"] = f"{type(e).__name__}: {e}"
        results.append(row)
        status = "ok" if row["error"] is None else "FAIL"
        print(f"[{i}/{len(utterances)}] {u['id']} {status} {row['latency_ms']}ms", file=sys.stderr)

    out = pathlib.Path(args.out)
    out.write_text("".join(json.dumps(r) + "\n" for r in results))
    latencies = sorted(r["latency_ms"] for r in results if r["error"] is None)
    if latencies:
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
        print(f"wrote {out} — {len(latencies)}/{len(results)} ok, latency p50={p50}ms p95={p95}ms", file=sys.stderr)
    else:
        print(f"wrote {out} — all {len(results)} requests failed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
