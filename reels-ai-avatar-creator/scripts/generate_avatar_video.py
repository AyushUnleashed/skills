#!/usr/bin/env python3
"""
Generate a lipsync avatar video from a text script.

Pipeline (with state management — safe to re-run):
  1. Generate TTS audio (skipped if cached)
  2. Upload audio to FAL (skipped if already uploaded)
  3. Submit FAL sync-lipsync (resumes if already in-flight)
  4. Download output video (skipped if already done)

State is persisted to .avatar_state.json in the working directory so that
re-running the same command resumes from where it left off.
"""

import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import aiohttp
import fal_client
from dotenv import find_dotenv, load_dotenv

# ── Load actors from CSV ─────────────────────────────────────────────────────
ACTORS_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "actors.csv")


def load_actors():
    """Load actor config from actors.csv. Returns dict keyed by actor name."""
    actors = {}
    with open(ACTORS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            actors[row["actor"].strip().lower()] = {
                "video_url": row["video_url"].strip(),
                "default_voice_provider": row["default_voice_provider"].strip(),
                "default_voice": row["default_voice"].strip(),
                "elevenlabs_voice_id": row["elevenlabs_voice_id"].strip() if row["elevenlabs_voice_id"].strip() else None,
            }
    return actors


ACTORS = load_actors()

# ── Voice mappings ────────────────────────────────────────────────────────────
OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

ELEVENLABS_VOICES = {
    "alice": "Xb7hH8MSUJpSbSDYk0k2",
    "aria": "9BWtsMINqrJLrRacOk9x",
    "bill": "pqHfZKP75CvOlQylNhV4",
    "brian": "nPczCjzI2devNBz1zQrb",
    "callum": "N2lVS1w4EtoT3dr4eOWO",
    "charlie": "IKne3meq5aSn9XLyUdCD",
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "chris": "iP95p4xoKVk53GoZ742B",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "eric": "cjVigY5qzO86Huf0OWal",
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "jessica": "cgSgspJ2msm6clMCkdW9",
    "laura": "FGY2WhTYpPnrIDTdsKH5",
    "liam": "TX3LPaxmHKxFdv7VOQHJ",
    "lily": "pFZP5JQG7iQjIQuC4Bku",
    "matilda": "XrExE9yKIg1WjnnlVkGX",
    "river": "SAz9YHcvj6GT2YYXdXww",
    "roger": "CwhRBWXzGAHq8TQ4Fs17",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
    "will": "bIHbv24MWmeRgasZH58o",
    "ayush": "gtVylSAXuNzydSb0uL4b",
}

# ── Step ordering for resume logic ───────────────────────────────────────────
STEPS = ["init", "audio_generated", "audio_uploaded", "lipsync_submitted", "lipsync_complete", "done"]


def step_gte(current: str, target: str) -> bool:
    """Return True if current step is at or past target."""
    return STEPS.index(current) >= STEPS.index(target)


# ── State management ─────────────────────────────────────────────────────────
def compute_hash(script_text: str, actor: str, voice_provider: str, voice: str) -> str:
    """Deterministic hash for a specific script+actor+voice combo."""
    key = f"{script_text}|{actor}|{voice_provider}|{voice}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def state_file_path(state_dir: str) -> str:
    return os.path.join(state_dir, ".avatar_state.json")


def load_state(state_dir: str, script_hash: str) -> dict | None:
    """Load state for a given hash, or None if not found."""
    path = state_file_path(state_dir)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = json.load(f)
    if data.get("script_hash") != script_hash:
        return None
    return data


def save_state(state_dir: str, state: dict) -> None:
    """Persist state to disk."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = state_file_path(state_dir)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def init_state(state_dir: str, script_hash: str, actor: str, voice_provider: str,
               voice: str, output_path: str, sync_mode: str, model: str) -> dict:
    """Create a fresh state dict."""
    return {
        "script_hash": script_hash,
        "actor": actor,
        "voice_provider": voice_provider,
        "voice": voice,
        "step": "init",
        "audio_path": None,
        "audio_fal_url": None,
        "fal_request_id": None,
        "output_video_url": None,
        "output_path": output_path,
        "sync_mode": sync_mode,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── TTS generation ────────────────────────────────────────────────────────────
async def generate_openai_tts(script: str, voice: str, output_path: str) -> None:
    """Generate TTS audio via OpenAI API (tts-1-hd)."""
    api_key = os.environ["OPENAI_API_KEY"]
    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": "tts-1-hd", "input": script, "voice": voice}

    timeout = aiohttp.ClientTimeout(total=300, sock_read=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"OpenAI TTS failed ({resp.status}): {body}")
            with open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024):
                    f.write(chunk)
    print(f"  TTS audio saved: {output_path}")


async def generate_elevenlabs_tts(script: str, voice_id: str, output_path: str) -> None:
    """Generate TTS audio via ElevenLabs API (eleven_flash_v2_5)."""
    api_key = os.environ["ELEVEN_LABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": script,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {
            "speed": 1.1,
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    timeout = aiohttp.ClientTimeout(total=300, sock_read=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"ElevenLabs TTS failed ({resp.status}): {body}")
            with open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024):
                    f.write(chunk)
    print(f"  TTS audio saved: {output_path}")


# ── FAL lipsync (queue-based with resume) ────────────────────────────────────
def submit_lipsync(video_url: str, audio_url: str, model: str, sync_mode: str) -> tuple[str, str]:
    """Submit lipsync job to FAL queue. Returns (request_id, request_id) without waiting."""
    print(f"  Submitting lipsync job (model={model}, sync_mode={sync_mode})...")
    handle = fal_client.submit(
        "fal-ai/sync-lipsync",
        arguments={
            "video_url": video_url,
            "audio_url": audio_url,
            "model": model,
            "sync_mode": sync_mode,
        },
    )
    print(f"  Submitted! request_id={handle.request_id}")
    return handle.request_id


def poll_lipsync(request_id: str) -> str:
    """Poll an existing lipsync job until complete. Returns output video URL."""
    APP_ID = "fal-ai/sync-lipsync"
    print(f"  Resuming/polling lipsync job {request_id}...")

    # Check current status
    status = fal_client.status(APP_ID, request_id, with_logs=True)
    status_name = type(status).__name__
    print(f"  Current status: {status_name}")

    if status_name == "Completed":
        result = fal_client.result(APP_ID, request_id)
        video_url = result["video"]["url"]
        print(f"  Lipsync already complete: {video_url}")
        return video_url

    # Poll until done
    while True:
        time.sleep(5)
        status = fal_client.status(APP_ID, request_id, with_logs=True)
        status_name = type(status).__name__
        if hasattr(status, "logs") and status.logs:
            for log in status.logs:
                msg = log["message"] if isinstance(log, dict) else str(log)
                print(f"  [FAL] {msg}")
        print(f"  Status: {status_name}")
        if status_name == "Completed":
            break
        if status_name not in ("Queued", "InProgress"):
            raise RuntimeError(f"Unexpected lipsync status: {status_name}")

    result = fal_client.result(APP_ID, request_id)
    video_url = result["video"]["url"]
    print(f"  Lipsync complete: {video_url}")
    return video_url


# ── Download helper ───────────────────────────────────────────────────────────
async def download_file(url: str, output_path: str) -> None:
    """Download a file from URL to local path."""
    timeout = aiohttp.ClientTimeout(total=300, sock_read=180, connect=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Download failed ({resp.status}): {url}")
            with open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)
    print(f"  Video downloaded: {output_path}")


# ── Main pipeline ─────────────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="Generate lipsync avatar video from a text script")
    parser.add_argument("--script-file", required=True, help="Path to .txt file with the script")
    parser.add_argument("--voice", default="nova", help="Voice name (default: nova)")
    parser.add_argument("--voice-provider", default="openai", choices=["openai", "elevenlabs"], help="TTS provider")
    parser.add_argument("--actor", default="candace", help="Actor name (from built-in list) or a video URL")
    parser.add_argument("--output", default="./output.mp4", help="Output video path (default: ./output.mp4)")
    parser.add_argument("--sync-mode", default="loop", choices=["cut_off", "loop", "bounce", "silence", "remap"], help="Lipsync sync mode (default: loop)")
    parser.add_argument("--model", default="lipsync-1.9.0-beta", choices=["lipsync-1.8.0", "lipsync-1.7.1", "lipsync-1.9.0-beta"], help="FAL lipsync model version")
    parser.add_argument("--state-dir", default=None, help="Directory for state/cache files (default: cwd)")
    args = parser.parse_args()

    # Track whether user explicitly set voice/provider (vs using defaults)
    user_set_provider = "--voice-provider" in sys.argv
    user_set_voice = "--voice" in sys.argv

    # Load .env
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path)
        print(f"Loaded .env from: {env_path}")
    else:
        print("WARNING: No .env file found, relying on existing environment variables")

    # Set FAL_KEY for fal_client
    fal_key = os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")
    if not fal_key:
        print("ERROR: FAL_API_KEY not set")
        sys.exit(1)
    os.environ["FAL_KEY"] = fal_key

    # Read script
    with open(args.script_file, "r") as f:
        script_text = f.read().strip()
    if not script_text:
        print("ERROR: Script file is empty")
        sys.exit(1)
    print(f"Script loaded ({len(script_text)} chars)")

    # Resolve actor from CSV config
    actor_key = args.actor.lower()
    actor_config = ACTORS.get(actor_key)
    if actor_config:
        actor_url = actor_config["video_url"]
        if not user_set_provider:
            args.voice_provider = actor_config["default_voice_provider"]
        if not user_set_voice:
            args.voice = actor_config["default_voice"]
        if actor_config["elevenlabs_voice_id"] and args.voice_provider == "elevenlabs" and args.voice == actor_config["default_voice"]:
            actor_elevenlabs_id = actor_config["elevenlabs_voice_id"]
        else:
            actor_elevenlabs_id = None
        print(f"Actor: {actor_key} (from actors.csv)")
        print(f"  Video: {actor_url}")
        print(f"  Voice: {args.voice_provider}/{args.voice}")
    elif args.actor.startswith("http"):
        actor_url = args.actor
        actor_elevenlabs_id = None
        print(f"Actor: custom URL -> {actor_url}")
    else:
        print(f"ERROR: Unknown actor '{args.actor}'. Available: {', '.join(ACTORS.keys())}")
        print("  Or provide a direct video URL starting with http")
        sys.exit(1)

    # ── State setup ──────────────────────────────────────────────────────────
    state_dir = args.state_dir or os.getcwd()
    cache_dir = os.path.join(state_dir, ".avatar_cache")
    os.makedirs(cache_dir, exist_ok=True)

    script_hash = compute_hash(script_text, actor_key, args.voice_provider, args.voice)
    state = load_state(state_dir, script_hash)

    if state:
        print(f"\nResuming from state: step={state['step']} (hash={script_hash})")
    else:
        print(f"\nFresh run (hash={script_hash})")
        state = init_state(state_dir, script_hash, actor_key, args.voice_provider,
                           args.voice, args.output, args.sync_mode, args.model)
        save_state(state_dir, state)

    # ── Step 1: Generate TTS audio ───────────────────────────────────────────
    audio_path = os.path.join(cache_dir, f"audio_{actor_key}_{script_hash}.wav")

    if step_gte(state["step"], "audio_generated") and os.path.exists(audio_path):
        print(f"\n[Step 1/4] TTS audio already cached: {audio_path} — SKIPPED")
    else:
        print("\n[Step 1/4] Generating TTS audio...")
        if args.voice_provider == "openai":
            if args.voice.lower() not in OPENAI_VOICES:
                print(f"ERROR: Unknown OpenAI voice '{args.voice}'. Available: {', '.join(OPENAI_VOICES)}")
                sys.exit(1)
            await generate_openai_tts(script_text, args.voice.lower(), audio_path)
        else:
            voice_id = actor_elevenlabs_id or ELEVENLABS_VOICES.get(args.voice.lower())
            if not voice_id:
                print(f"ERROR: Unknown ElevenLabs voice '{args.voice}'. Available: {', '.join(ELEVENLABS_VOICES.keys())}")
                sys.exit(1)
            await generate_elevenlabs_tts(script_text, voice_id, audio_path)

        state["audio_path"] = audio_path
        state["step"] = "audio_generated"
        save_state(state_dir, state)

    # ── Step 2: Upload audio to FAL ──────────────────────────────────────────
    if step_gte(state["step"], "audio_uploaded") and state.get("audio_fal_url"):
        print(f"\n[Step 2/4] Audio already uploaded to FAL — SKIPPED")
        audio_fal_url = state["audio_fal_url"]
    else:
        print("\n[Step 2/4] Uploading audio to FAL...")
        audio_fal_url = fal_client.upload_file(audio_path)
        print(f"  Uploaded: {audio_fal_url}")

        state["audio_fal_url"] = audio_fal_url
        state["step"] = "audio_uploaded"
        save_state(state_dir, state)

    # ── Step 3: Run lipsync ──────────────────────────────────────────────────
    if step_gte(state["step"], "lipsync_complete") and state.get("output_video_url"):
        print(f"\n[Step 3/4] Lipsync already complete — SKIPPED")
        output_video_url = state["output_video_url"]
    elif step_gte(state["step"], "lipsync_submitted") and state.get("fal_request_id"):
        print(f"\n[Step 3/4] Resuming lipsync job...")
        try:
            output_video_url = poll_lipsync(state["fal_request_id"])
        except Exception as e:
            print(f"  Previous job failed or expired ({e}), re-submitting...")
            request_id = submit_lipsync(actor_url, audio_fal_url, args.model, args.sync_mode)
            state["fal_request_id"] = request_id
            state["step"] = "lipsync_submitted"
            save_state(state_dir, state)
            output_video_url = poll_lipsync(request_id)

        state["output_video_url"] = output_video_url
        state["step"] = "lipsync_complete"
        save_state(state_dir, state)
    else:
        print("\n[Step 3/4] Submitting lipsync job...")
        request_id = submit_lipsync(actor_url, audio_fal_url, args.model, args.sync_mode)

        state["fal_request_id"] = request_id
        state["step"] = "lipsync_submitted"
        save_state(state_dir, state)

        output_video_url = poll_lipsync(request_id)

        state["output_video_url"] = output_video_url
        state["step"] = "lipsync_complete"
        save_state(state_dir, state)

    # ── Step 4: Download output ──────────────────────────────────────────────
    output_path = args.output
    if step_gte(state["step"], "done") and os.path.exists(output_path):
        print(f"\n[Step 4/4] Output video already exists: {output_path} — SKIPPED")
    else:
        print("\n[Step 4/4] Downloading output video...")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        await download_file(output_video_url, output_path)

        state["step"] = "done"
        save_state(state_dir, state)

    print(f"\nDone! Output video: {os.path.abspath(output_path)}")
    print(f"State saved to: {state_file_path(state_dir)}")


if __name__ == "__main__":
    asyncio.run(main())
