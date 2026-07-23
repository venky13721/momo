# Phase 0 spike results

> Fill in as spikes complete. This file is the record the go/no-go decision is made from.

## Machine

- Mac model / chip / RAM:
- macOS version:

## 1. System-audio tap

- Date run:
- Approach tested (process tap / SCK fallback):
- Teams audio on system track, mic separate: yes / no
- AirPods behavior:
- Permission prompts hit:
- Verdict:

## 2. STT (Parakeet v3 via FluidAudio)

- Date run:
- Cold model load: __ s
- Latency, ~5s utterance: __ ms   RTFx: __
- Peak RSS: __ MB
- Transcript quality notes (incl. Hinglish):
- Verdict:

## 3. SLM extraction eval

| Model | Hard-field acc. | Latency p50 / p95 | Notes |
|---|---|---|---|
| Qwen 2.5 3B Q4_K_M | | | |
| Gemma 3 4B Q4_K_M | | | |
| (control) | | | |

- Prompt iterations made (and which models saw them):
- **Chosen SLM:**

## Go / no-go

- [ ] All exit criteria met → proceed to Phase 1
- Notes:
