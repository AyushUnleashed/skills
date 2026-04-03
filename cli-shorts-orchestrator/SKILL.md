---
name: cli-shorts-orchestrator
description: End-to-end orchestrator for shorts-ai-edit. Runs the full 9-step pipeline to produce a final 9:16 edited video from an A-roll video and optional assets. Steps 1-5 run via the Python CLI (setup, transcribe, analyze assets, create EDL, approve EDL). Steps 6-8 are delegated to the cli-motion-graphics-helper skill (motion prompts, Remotion code, rendering). Step 9 runs via the Python CLI (FFmpeg assembly). Trigger when the user wants to create or edit a short-form video, run the shorts pipeline, make a Reel/TikTok/Short, or says anything about editing a video end-to-end.
---

# CLI Shorts Orchestrator

You run the full shorts-ai-edit pipeline step by step. Each step is run individually via the CLI so you can see progress, skip already-completed steps, and recover from failures without starting over.

The Python CLI handles steps 1-5 and 9. The `cli-motion-graphics-helper` skill handles steps 6-8.

## Setup

```
REPO_DIR="/mnt/d/code_me/experiments/shorts-ai-edit"
```

Before any Python command:
```bash
cd "${REPO_DIR}" && source .venv/bin/activate
```

## Get project info

Ask the user for the project name or path. Projects live in `${REPO_DIR}/projects/`. If it's a new project:
```bash
mkdir -p "${REPO_DIR}/projects/<name>/assets"
```
Then the user copies in `aroll.mp4` and optional asset files.

---

## Phase 1: Steps 1–4 (run each step individually)

Run each step one at a time using `--stop-after`. This gives you visibility into what's happening and lets you skip steps that are already done.

### Check for existing run

Before starting, check if there's already a run directory with progress:
```bash
ls -td "${REPO_DIR}/projects/<name>"/edit-* 2>/dev/null | head -1
```

If a run exists, read its state to see what's already completed:
```bash
cat "${RUN_DIR}/workflow_state.json" | python -m json.tool | grep -A20 '"steps"'
```

Any step showing `"completed"` can be skipped — the CLI's `resume` command handles this automatically.

### Starting fresh (no existing run)

```bash
cd "${REPO_DIR}" && source .venv/bin/activate
python cli.py run "<project_name>" --stop-after setup
```

Find the run directory:
```bash
RUN_DIR=$(ls -td "${REPO_DIR}/projects/<name>"/edit-* | head -1)
echo "Run dir: ${RUN_DIR}"
```

### Step 2: Transcribe

```bash
cd "${REPO_DIR}" && source .venv/bin/activate
python cli.py resume "${RUN_DIR}" --stop-after transcribe
```

This uploads the A-roll to AssemblyAI and waits for transcription. Shows a progress timer.

### Step 3: Analyze Assets

```bash
cd "${REPO_DIR}" && source .venv/bin/activate
python cli.py resume "${RUN_DIR}" --stop-after analyze_assets
```

Analyzes each asset via vision AI. Shows per-asset progress (1/N, 2/N, ...) with timing.

If there are no assets, this completes instantly.

### Step 4: Create EDL

```bash
cd "${REPO_DIR}" && source .venv/bin/activate
python cli.py resume "${RUN_DIR}" --stop-after create_edl
```

Calls the LLM to generate the Edit Decision List. The LLM now receives:
- The full transcript text
- **Sentence-level timestamps** (exact start/end for every sentence from the transcription)
- **Video duration**
- Available assets with descriptions

This ensures EDL section boundaries align with actual speech timing instead of inventing round-number timestamps.

### Resuming a partially-completed run

If any step was already completed (e.g., transcription was done in a previous session), `resume` automatically skips it and picks up from the next pending step. So you can always just run:
```bash
python cli.py resume "${RUN_DIR}" --stop-after <target_step>
```
and it will only run what's needed.

## Phase 1.5: EDL Approval (step 5 — you handle this)

Read `${RUN_DIR}/edl.md` and show the EDL table to the user. Also read `${RUN_DIR}/transcript.json` to cross-check that the EDL timestamps align with actual sentence boundaries.

Ask if they approve or want changes.

- If approved: update `${RUN_DIR}/workflow_state.json` — set `steps.approve_edl` to `"completed"`, set `edl_approved` to `true`, and set `current_step` to `"approve_edl"`.
- If the user wants changes: rerun just `create_edl`:
  ```bash
  python cli.py rerun "${RUN_DIR}" create_edl --stop-after create_edl
  ```
  Then show the new EDL again. Repeat until approved.

### EDL Quality Checks

When reviewing the EDL, verify:
1. **Timestamps match transcript** — section boundaries should fall on natural sentence/phrase boundaries from `transcript.json`, not round numbers.
2. **Asset relevance** — each ASSET section's image/video should obviously match what's being said. Don't force assets where the connection isn't instant. Better to leave an asset unused than place it poorly.
3. **No gaps or overlaps** — section N's end must equal section N+1's start.
4. **First section starts at 0.0**, last section ends at video duration.
5. **Every section >= 2 seconds**.

---

## Phase 2: Steps 6–8 via cli-motion-graphics-helper

Invoke the `cli-motion-graphics-helper` skill with:
- `REPO_DIR` = the repo root
- `RUN_DIR` = the run directory from phase 1

The skill reads the approved EDL, asks the user for a motion style, writes animation briefs, generates Remotion TSX components, renders them, and updates the EDL + workflow state.

**Word-level timestamps**: The transcription step produces word-by-word timing data in `${RUN_DIR}/transcript.json`. The Python pipeline automatically threads this through to motion graphics generation — each section's words are filtered and offset to section-relative timing, then passed to both the animation brief LLM and the Remotion code generation LLM. This enables precise speech-synced animations (kinetic typography, word reveals, etc.). No manual intervention needed — the CLI handles the data flow.

---

## Phase 3: Step 9 via CLI (assemble)

Resume the pipeline to run FFmpeg assembly:

```bash
cd "${REPO_DIR}" && source .venv/bin/activate
python cli.py resume "${RUN_DIR}"
```

Steps 1-8 are already completed — this runs only step 9 (assemble), producing `${RUN_DIR}/final_output.mp4`. Shows a progress bar for each section being built.

### How Assembly Works (important for debugging)

The assembler avoids both **black screens** and **lip-sync drift**:

1. **Per-section clips WITH audio** — each clip is built with its own audio slice from the A-roll at the exact same `-ss`/`-t` timestamps as the video. This keeps audio perfectly synced per-section (no frame-rounding drift that would accumulate across sections).
2. **No `-shortest` flag** — both video and audio streams use explicit `-t` duration, so nothing gets truncated.
3. **Concatenate with re-encode** — clips are joined with re-encoding (`-c:v libx264`), not stream copy (`-c copy`). This prevents keyframe boundary glitches that cause flickers between sections.

Why NOT extract-full-audio-and-mux-at-end: video clips are quantized to 30fps frame boundaries (~33ms per frame). Each clip's duration rounds slightly, and these errors accumulate across 18+ sections, causing noticeable lip-sync drift by the end. Per-section audio slicing avoids this because each clip's audio is trimmed from the exact same A-roll position.

If the user reports black screens or flickers, check:
- Motion graphic renders have sufficient duration (must be >= the EDL section duration)
- All asset files exist at the paths specified in `edl.json`
- No section has a duration of 0 or negative

---

## Report

Tell the user:
- Final video path
- Specs: 1080x1920, 30fps, H.264
- Section breakdown: how many A-ROLL / ASSET / MOTION-GRAPHIC / A-ROLL-ENHANCED
