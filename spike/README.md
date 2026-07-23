# Phase 0 spikes (run on the Mac)

Three spikes gate Phase 0, in order of uncertainty. Record everything in `RESULTS.md`.

## 1. System-audio capture — CoreAudio process tap (highest risk, do first)

This gates Phase 4 and has no workaround other than the Muesli bridge, so prove it before investing anywhere else.

- Clone Muesli (github.com/Muesli-HQ/muesli, MIT) and read its CoreAudio process-tap implementation (`CATapDescription` / `AudioHardwareCreateProcessTap` path) and its ScreenCaptureKit fallback.
- Build/run enough of it (or the extracted tap code) to capture a Teams call: confirm **remote participants land on the system track and your mic stays separate**, with AirPods connected — Bluetooth routing is exactly where SCK-only approaches fail.
- Pass = a 2-minute Teams call captured to two clean tracks. Note macOS version, permission prompts encountered, and whether AirPods switched profiles.

## 2. STT latency — Parakeet v3 via FluidAudio

```bash
cd spike/TranscribeCLI
swift run -c release TranscribeCLI path/to/sample-16k-mono.wav
```

First run downloads the Parakeet CoreML models via FluidAudio's own fetcher (~450 MB). The CLI prints model-load time, transcription latency, and RTFx.

> The FluidAudio API surface moves; if `AsrModels.downloadAndLoad()` / `AsrManager` don't compile as written, fix up against the current README examples — the measurement scaffold is the point.

Record: cold model-load time, latency for a ~5s utterance, RTFx, peak RSS (`footprint` or Xcode gauge). Target: utterance latency well under 1s; Muesli reports ~0.13s dictation latency on this stack.

Also record a handful of real dictated task utterances (including Hinglish ones) and eyeball transcript quality — STT errors compound into extraction errors and the eval set assumes clean transcripts.

## 3. SLM extraction — eval gate

```bash
brew install llama.cpp
# validate the grammar compiles before burning eval time:
llama-gbnf-validator grammars/task.gbnf <<< '{"tasks":[{"title":"x","description":null,"owner":"me","urgency":"small","due":null,"effort_minutes":5,"waiting_on":null,"discuss_with":null,"confidence":0.9}]}'

llama-server -m ~/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096
python3 eval/run_extraction.py --out eval/predictions-qwen3b.jsonl
python3 eval/score.py eval/predictions-qwen3b.jsonl --gate
```

Run Qwen 2.5 3B, Gemma 3 4B, and one larger control (e.g. Qwen 2.5 7B Q4) to see how much headroom size buys. If a candidate misses the gate, iterate the system prompt (`prompts/extraction_system.txt`) before reaching for a bigger model — and note in RESULTS.md what was tuned, since the eval set is no longer blind for that model.

## Exit criteria (from PLAN.md)

- [ ] ≥90% hard-field accuracy on `eval/utterances.jsonl` for the chosen SLM
- [ ] <2s extraction latency per utterance (p95, on-device)
- [ ] System-audio tap proven: Teams audio on "others" track, mic separate, AirPods OK
- [ ] SLM chosen and recorded in RESULTS.md; its manifest entry in `models/catalog.json` gets real `sha256`/`size_bytes`
