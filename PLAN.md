# Personal Productivity App — Development Plan (macOS)

## 1. Product summary

A local-first macOS menu-bar app that turns spoken input and meeting audio into structured, triaged tasks — and then actively surfaces the right work at the right time. All inference on-device (STT + SLM). Single user (me). No cloud, no accounts, no fees.

Three jobs, in priority order:
1. **Capture** — speak a task (mine or delegated), get a fully structured, triaged entry with zero typing.
2. **Surface** — daily brief, today-only view, fire-task escalation, delegation follow-up nudges. The app decides what I see and when.
3. **Meetings** — transcribe meetings locally, extract MoM + action items with owners, one-tap approve into the task store.

Design constraints: dopamine-positive UI (juicy completions, combos, no shame states, no overdue counters), max 3–5 items visible at once, every nudge forces a one-tap decision.

## 2. Architecture at a glance

```
┌─────────────────────────────────────────────────────┐
│ Menu-bar app (SwiftUI)                              │
│  ├── Capture popover (mic → task cards → confirm)   │
│  ├── Today panel (3–5 tasks, fire lane pinned)      │
│  ├── Sweep mode (small-task queue, combo counter)   │
│  ├── People pages (per-reportee: delegated, 1:1)    │
│  └── Meeting mode (live transcript, MoM review)     │
├─────────────────────────────────────────────────────┤
│ Core services (Swift)                               │
│  ├── AudioService     — mic + system-audio capture  │
│  ├── ModelManager     — catalog, on-demand HF       │
│  │                      download, cache, activation │
│  ├── STTService       — Parakeet TDT via FluidAudio │
│  │                      (CoreML / Neural Engine)    │
│  ├── LLMService       — SLM via llama.cpp / MLX,    │
│  │                      constrained JSON decoding   │
│  ├── ExtractionEngine — prompt assembly, schema     │
│  │                      validation, people resolver │
│  ├── Scheduler        — nudges, escalation, EOD     │
│  │                      sweep, morning brief timers │
│  └── StatsEngine      — streaks, combos, PBs        │
├─────────────────────────────────────────────────────┤
│ Storage: SQLite (GRDB, WAL) — tasks as event log +  │
│ materialized current-state table; transcripts on    │
│ disk, referenced by task/meeting id; models in      │
│ ~/Library/Application Support/<app>/models/         │
└─────────────────────────────────────────────────────┘
```

Key decisions to lock before HLD:
- **STT**: Parakeet TDT v3 via **FluidAudio** (Swift package, CoreML on the Apple Neural Engine) rather than sherpa-onnx. Same path Muesli uses to hit ~0.13s dictation latency, and one dependency also gives Silero VAD and pyannote diarization — which Phase 4 needs anyway. Fallback/high-accuracy option: WhisperKit (Whisper Large Turbo, also CoreML/ANE) for post-meeting re-pass.
- **SLM**: Qwen 2.5 3B or Gemma 3 4B via llama.cpp with GBNF grammar (or MLX + outlines-style constrained decoding) to guarantee valid JSON. Benchmark both on the extraction eval set (see Phase 0). Runtime bundled in app (~tens of MB), weights lazy-downloaded.
- **Meeting audio**: **CoreAudio process tap** as the primary system-audio path with **ScreenCaptureKit `SCStream` as fallback** (Muesli's approach — the process tap handles Bluetooth/AirPods correctly, which SCK alone does not). Mic via AVAudioEngine. Both sides of the call land on separate tracks: mic = me, system = others.
- **Data model**: append-only event log (`task_created`, `triaged`, `delegated`, `followed_up`, `snoozed`, `completed`, `dropped`) + a projection table for fast queries. Buys undo, stats, and future device sync for free.
- **Reference implementation**: Muesli (github.com/Muesli-HQ/muesli) is MIT-licensed and solves the capture half of this problem well. Read its CoreAudio tap, model-download, and VAD-chunking code rather than re-deriving. Its bundled `muesli-cli` returns stable JSON for meetings/transcripts — viable as a Phase 4 bridge (consume its output for extraction) before building own meeting capture.

## 2b. Model management (Muesli pattern)

Ship a small binary; download weights only when a model is actually selected.

- **Bundle in the app**: inference runtimes only — FluidAudio/CoreML framework, llama.cpp or MLX runtime. Keeps the .dmg small.
- **Lazy weights**: models pull on demand from HuggingFace on first selection, cached to `~/Library/Application Support/<app>/models/<model-id>/`. Reference sizes: Parakeet v3 ~450 MB, Whisper Large Turbo ~626 MB, a 3B GGUF SLM ~2 GB.
- **Catalog as data**: static JSON manifest per model — `id`, `hf_repo`, `files[]`, `size_bytes`, `sha256`, `runtime` (coreml | llamacpp | mlx), `role` (stt | slm | vad | diarization), `languages`. Adding a model = adding a manifest entry, not code.
- **Download service**: background `URLSession` with resume support, progress reporting, checksum verification, atomic move into place on completion. Downloads never block the UI.
- **Download state ≠ active state.** Two independent flags. Downloading a model does not activate it; activation is an explicit selection in Settings. Settings always displays which model currently owns each role.
- **Models pane**: list with per-model download / delete / select, disk usage, and current-role badges.
- **Onboarding wizard** (steal wholesale): model selection → real OS permission verification (Microphone, System Audio Recording, Accessibility, Input Monitoring, Notifications) → hotkey config → **live end-to-end test: speak a sample task, see the extracted card**. Progress saved per step so it survives quits. For an app whose whole value is trust in the pipeline, first-run must prove the pipeline.
- **Distribution**: self-built `.dmg`, drag to /Applications. Unsigned personal build → `sudo xattr -cr /Applications/<App>.app` if Gatekeeper complains. Note macOS ties permissions to app path + signature: keep exactly one copy in /Applications or hotkey/paste permissions silently break.

## 3. Task schema (extraction target)

```json
{
  "title": "string",
  "description": "string | null",
  "owner": "me | <person_id>",
  "urgency": "fire | scheduled | small",
  "due": "ISO date | null",
  "effort_minutes": "int (model-estimated)",
  "waiting_on": "<person_id> | null",
  "discuss_with": "<person_id> | null",
  "source": "voice | meeting | manual",
  "confidence": "float"
}
```

People resolver: static contact list (name, aliases, role) injected into the extraction prompt; model must output `person_id` from the list or `unknown` — never free text. Low-confidence fields render highlighted on the confirm card for one-tap correction.

## 4. Phases

### Phase 0 — Spike & eval harness (weekend 1)
- Wire FluidAudio into a throwaway Swift CLI: Parakeet v3 transcription end-to-end, measure latency and RAM on my Mac. Same for candidate SLMs via llama.cpp/MLX.
- Spike the CoreAudio process tap for system audio capture early — this is the highest-uncertainty piece and it gates Phase 4. Confirm Teams audio lands on the "others" track.
- Build a 40–60 utterance eval set: real phrasings I'd actually say (English + code-switched Hinglish/Kanglish as applicable), covering delegation, fires, vague deadlines, multi-task utterances.
- Score Qwen 3B vs Gemma vs one larger model on field-level extraction accuracy. Pick the model. **Exit criteria: ≥90% field accuracy on eval set, <2s extraction latency, system-audio tap proven.**

### Phase 1 — Capture MVP (weeks 1–2)
- Menu-bar app skeleton, global hotkey → popover → hold-to-talk.
- ModelManager: catalog manifest, background download with checksum + resume, Models settings pane, download-vs-active split.
- Onboarding wizard: model pick → permission verification → hotkey → live end-to-end capture test.
- STT → ExtractionEngine → confirm card (editable fields, one-tap save).
- SQLite event log + projection table. People list management (simple settings screen).
- Today panel: fire lane + today list, manual complete with full haptic/animation/sound treatment (juicy from day one — this is not polish, it's core).
- **Exit criteria: I stop noting tasks in WhatsApp/Teams. Capture-to-saved under 10 seconds.**

### Phase 2 — Surfacing & rituals (weeks 3–4)
- Morning brief (SLM-generated, personality microcopy) at first unlock / configurable time.
- Evening sweep: forced decision per open task (tomorrow / this week / delegate / drop).
- Notifications with action buttons (Do now / 1 hr / Tomorrow / Drop); fire escalation curve.
- Small-task sweep queue with combo counter + end-of-sweep stat card.
- Triage lanes: today / this week / someday / delegated-waiting. Home shows today only.
- **Exit criteria: zero tasks silently rolling over; I open the brief ≥5 days/week unprompted.**

### Phase 3 — Delegation layer (week 5)
- Per-reportee pages: open delegated tasks, status, `last_followed_up`, days-to-due.
- Follow-up nudges at half-life and morning-of; one-tap generates a paste-ready Teams message.
- Waiting-on tracking (things others owe me) with its own nudge cycle.
- 1:1 agenda builder: `discuss_with` items accumulate per person, exportable as text.
- **Exit criteria: no delegated task goes >3 days without a logged follow-up.**

### Phase 4 — Meeting mode (weeks 6–8)
- CoreAudio process tap (SCK fallback) for system audio + mic capture; live local transcription in a floating panel.
- VAD-driven chunk rotation: Silero VAD (via FluidAudio) splits audio at natural speech pauses instead of fixed intervals, so transcription runs *during* the meeting and no chunk cuts mid-sentence.
- Post-meeting: optional Whisper Large Turbo re-pass, then SLM chunked map-reduce over transcript → MoM (summary, decisions, action items with owner + due, open questions).
- Review screen: approve/edit/reject each action item; approved ones enter the task store tagged with meeting id; MoM saved as markdown, copyable to Teams.
- Speaker attribution v1 = channel-based (mic = me, system = them). v2 = pyannote diarization via FluidAudio to split "others" into Speaker 1/2/N, then map to people list.
- **Bridge option**: if the capture stack fights back, run Muesli for transcription and consume `muesli-cli meetings get <id>` JSON as ExtractionEngine input. Ships Phase 4 value without owning the audio pipeline.
- **Exit criteria: after a 30-min meeting, reviewed MoM + tasks in under 3 minutes.**

### Phase 5 — Dopamine & stats polish (ongoing, timeboxed)
- Streaks for rituals (with weekly auto-applied streak insurance), personal bests, weekly recap card.
- Variable completion animations (4–5 variants), fire-clear celebration, progress scene on Today panel.
- Microcopy system prompt tuning for the brief/nudge personality.

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Extraction accuracy too low → trust collapses | Phase 0 eval gate before building UI; confidence-highlighted confirm card so errors cost one tap, not trust |
| System-audio capture friction / macOS updates breaking it | CoreAudio process tap primary + ScreenCaptureKit fallback; spiked in Phase 0; last resort = mic-only with speaker on, or Muesli bridge |
| macOS permissions silently break (paste/hotkey stop working) | Permissions bind to app path + signature: exactly one copy in /Applications, never launch from Downloads; onboarding verifies each permission for real, not just prompts |
| Model downloads fail / corrupt / half-complete | Checksums in the manifest, resumable background URLSession, atomic move on completion, re-download button per model |
| Disk bloat from multiple models | Models pane shows per-model disk usage with delete; only the active model per role is required on disk |
| SLM latency during meetings competing with Teams for compute | Extraction runs post-meeting, not live; live path is STT-only on the ANE |
| I abandon the app (the meta-risk) | Phase-gated exit criteria are behavioral, not technical; juicy completion ships in Phase 1, not last; no-shame design throughout |
| Scope creep before HLD | Anything not in Phases 0–4 goes to a `later.md`, not the plan |

## 6. Deliverables before coding

1. HLD: module boundaries, event-log schema, service interfaces, ModelManager contract, notification/timer design.
2. LLD per phase: Phase 0–1 first (ExtractionEngine prompt spec, GBNF grammar, DB schema DDL, model catalog manifest schema, popover state machine). Later phases get LLDs just-in-time.
3. Eval set file (`eval/utterances.jsonl`) — write this before the HLD; it defines what "working" means.
4. `models/catalog.json` — first entries: Parakeet v3 (stt), Silero VAD, chosen SLM. Adding models later should never touch code.

## 7. References

- Muesli — github.com/Muesli-HQ/muesli (MIT). Read: CoreAudio process tap, model download/management, VAD chunk rotation, onboarding flow, `muesli-cli` JSON contract.
- FluidAudio — github.com/FluidInference/FluidAudio. Parakeet TDT, Silero VAD, pyannote diarization on CoreML/ANE.
- WhisperKit — github.com/argmaxinc/WhisperKit. Whisper on CoreML/ANE, for the high-accuracy re-pass.
- NVIDIA Parakeet TDT — huggingface.co/nvidia/parakeet-tdt-0.6b-v3.
