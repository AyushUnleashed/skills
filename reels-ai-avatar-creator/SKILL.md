---
name: reels-ai-avatar-creator
description: >
  Generate lipsync avatar videos from a text script. Takes a .txt script file,
  generates TTS audio (OpenAI or ElevenLabs), then creates a lipsync video using
  FAL AI's sync-lipsync API. Actors and their voice/audio defaults are configured
  in actors.csv — the script auto-resolves everything per actor.
  Resumable: re-running the same command skips completed steps (cached audio, uploaded files, in-flight lipsync jobs).
  Triggers: "create avatar video", "lipsync video", "generate talking head", "avatar from script".
---

# Reels AI Avatar Creator

Generate a lipsync avatar video from a text script using FAL AI.

## Skill Directory

`~/.claude/skills/reels-ai-avatar-creator/`

## Available Actors

All actors are defined in `~/.claude/skills/reels-ai-avatar-creator/actors.csv`.
Read this file to see the current list of actors and their defaults.

Each actor has pre-configured: video URL, default voice provider, default voice name, and (optionally) a dedicated ElevenLabs voice ID.

**IMPORTANT:** When a user picks a known actor (e.g. "ayush", "candace"), do NOT ask for:
- Video URL — it's in the CSV
- Voice provider — it's in the CSV
- Voice name — it's in the CSV

The script auto-resolves all of these from `actors.csv`. Only ask if the user wants to **override** the defaults.

To add a new actor, add a row to `actors.csv` with: actor name, video URL, default voice provider, default voice name, and optionally an ElevenLabs voice ID.

## How to Use

### 1. Gather inputs from the user

**Only ask for the script file path.** Everything else has smart defaults from the actor config.

| Input | Required | Default |
|-------|----------|---------|
| Script file path (.txt) | Yes | — |
| Actor | No | `candace` (first actor in CSV) |
| Output path | No | `./output.mp4` |
| Sync mode | No | `loop` |

The user may optionally override voice provider or voice name, but **do not ask** — the actor's CSV defaults handle this automatically.

For custom actors not in the CSV, the user can provide a direct video URL as the `--actor` value (must start with `http`). Only in this case, ask about voice provider and voice name.

**OpenAI voices:** alloy, echo, fable, onyx, nova, shimmer
**ElevenLabs voices:** alice, aria, ayush, bill, brian, callum, charlie, charlotte, chris, daniel, eric, george, jessica, laura, liam, lily, matilda, river, roger, sarah, will

### 2. Verify environment

Run the env check script (do NOT read or print the .env file).
Determine the provider from the actor's CSV config (read `actors.csv` if unsure):

```bash
cd <project-working-directory> && bash ~/.claude/skills/reels-ai-avatar-creator/scripts/verify_env.sh --provider <openai|elevenlabs>
```

If it fails, tell the user which env vars are missing and stop.

### 3. Run the generator

```bash
cd <project-working-directory> && ~/.claude/skills/reels-ai-avatar-creator/.venv/bin/python ~/.claude/skills/reels-ai-avatar-creator/scripts/generate_avatar_video.py \
  --script-file <path-to-script.txt> \
  --actor <actor-name> \
  --output <output-path.mp4> \
  --sync-mode <loop|cut_off|bounce|silence|remap>
```

**Do NOT pass `--voice` or `--voice-provider`** unless the user explicitly asked to override them. The script reads `actors.csv` and auto-resolves the correct voice provider, voice name, and voice ID for each actor.

### Resume & State Management

The script is **safe to re-run**. It persists state to `.avatar_state.json` in the working directory and caches audio in `.avatar_cache/`. On re-run:

- **TTS audio**: Skipped if the cached `.wav` file already exists for the same script+actor+voice combo
- **FAL upload**: Skipped if the audio was already uploaded (URL saved in state)
- **Lipsync job**: If a FAL `request_id` was saved, it resumes polling that job instead of submitting a new one. If the old job expired/failed, it auto-resubmits.
- **Download**: Skipped if the output file already exists and state is `done`

This means:
- If the script times out or is interrupted mid-lipsync, just re-run the same command — it picks up where it left off
- If you want a fresh run with the same script, delete `.avatar_state.json` and `.avatar_cache/` first
- Each unique (script, actor, voice_provider, voice) combo gets its own hash, so changing any of these triggers a fresh run

The pipeline steps and their state values:
`init` → `audio_generated` → `audio_uploaded` → `lipsync_submitted` → `lipsync_complete` → `done`

### 4. Report result

Tell the user the output video path and confirm it was created successfully. If steps were skipped (cached), mention that.

## Important Notes

- The script reads `.env` from the current working directory. Make sure you `cd` into the project directory before running.
- FAL lipsync typically takes 1-3 minutes depending on audio length.
- The `loop` sync mode repeats the actor video if the audio is longer than the video. Use `cut_off` to trim audio to video length instead.
- Never read or print the contents of `.env` files.
- To see all available actors and their config: `cat ~/.claude/skills/reels-ai-avatar-creator/actors.csv`
- State file: `<project-dir>/.avatar_state.json` — you can read this to check current pipeline status
- Audio cache: `<project-dir>/.avatar_cache/` — cached TTS audio files
