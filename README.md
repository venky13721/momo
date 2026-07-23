# momo

Local-first macOS menu-bar app: speak a task, get a structured, triaged entry — plus daily surfacing rituals and on-device meeting transcription. All inference on-device. See [PLAN.md](PLAN.md) for the full development plan.

## Repo layout (Phase 0)

| Path | What |
|---|---|
| `PLAN.md` | Product plan, architecture, phases, exit criteria |
| `eval/` | Extraction eval set + scoring harness — the Phase 0 gate ([eval/README.md](eval/README.md)) |
| `prompts/extraction_system.txt` | System prompt template for the extraction SLM |
| `grammars/task.gbnf` | llama.cpp grammar guaranteeing schema-valid JSON output |
| `models/catalog.json` | Model catalog manifest consumed by ModelManager |
| `spike/` | Mac-side Phase 0 spikes: audio tap, STT latency, SLM eval ([spike/README.md](spike/README.md)) |

## Phase 0 status

Harness and assets are ready; the three Mac-side spikes in [spike/README.md](spike/README.md) remain (system-audio tap, STT latency, SLM eval runs). Results land in [spike/RESULTS.md](spike/RESULTS.md); Phase 1 starts when the exit criteria there are met.
