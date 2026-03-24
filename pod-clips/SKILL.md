---
name: pod-clips
description: "Extract viral short-form clips from YouTube interviews and podcasts. Use this skill whenever the user wants to cut clips from a YouTube video, find the best moments in a podcast, extract highlights from an interview, create Reels/Shorts/TikTok from a long-form video, or provides a YouTube URL and wants clips pulled from it. Also trigger when: 'find the best parts of this video', 'clip this podcast', 'get me the highlights', 'cut this into shorts'."
---

# Pod Clips

Extract viral short-form clips from long-form YouTube content (interviews, podcasts, talks). Works as a pipeline: validate → transcript → analyze → QA → finalize → approve → cut → per-clip transcripts.

## Skill Location

All scripts and reference files live at: `~/.claude/skills/pod-clips/`

- `scripts/validate_prerequisites.sh` — Checks yt-dlp, ffmpeg, python3, and validates the YouTube URL
- `scripts/fetch_transcript.py` — Downloads and formats the transcript with timestamps
- `scripts/cut_clips.sh` — Downloads a time range from YouTube and converts to MP4
- `references/clip_cutting_rules.md` — How to find clean start/end points for clips
- `references/viral_clip_criteria.md` — What makes a clip worth extracting

## Pipeline Overview

```
Step 1: Validate     → Run prerequisites script
Step 2: Setup        → Create directory structure
Step 3: Transcript   → Fetch and save formatted transcript
Step 4: Analyze      → Read transcript + reference files, suggest clips (capture FULL stories)
Step 5: QA           → Sub-agent reviews each clip for story completeness
Step 5b: Finalize    → Update clip_suggestions.md with QA corrections + final transcript excerpts
Step 6: Present      → Show clips to user for approval
Step 7: Cut          → Download approved clips as MP4
Step 7b: Transcripts → Generate per-clip .txt with exact timestamps (source of truth)
```

**Key principle:** Always capture COMPLETE stories. A clip with full context that's a bit long is far better than a tight clip that lost its setup. Duration tightening is a separate concern — the user can use `/clip-condenser` after this pipeline if needed.

---

## Step 1: Validate Prerequisites

Before anything else, run the validation script. This catches missing tools early instead of failing mid-pipeline.

```bash
bash ~/.claude/skills/pod-clips/scripts/validate_prerequisites.sh "<youtube_url>"
```

If any check fails, tell the user what to install and stop. Do not proceed with a broken setup.

## Step 2: Create Directory Structure

Create a dedicated directory for this video inside the current working directory. Use the video title slug from the metadata.

```
clip_cut/
└── <video-slug>/
    ├── transcript/
    │   ├── full_transcript.txt
    │   ├── raw_subtitle.en.json3
    │   └── video_metadata.txt
    ├── analysis/
    │   ├── clip_suggestions.md       ← single source of truth (updated after QA)
    │   └── qa_report.md
    └── clips/
        ├── clip1_<name>.mp4
        ├── clip1_<name>.txt          ← per-clip transcript
        ├── clip2_<name>.mp4
        ├── clip2_<name>.txt
        └── ...
```

If the user has already provided a directory or there's an existing `clip_cut/` folder, use it. Don't create a new root — nest under what's there.

## Step 3: Fetch Transcript

Run the transcript fetcher script:

```bash
python3 ~/.claude/skills/pod-clips/scripts/fetch_transcript.py "<youtube_url>" "clip_cut/<video-slug>/transcript"
```

This creates `full_transcript.txt` with `[MM:SS-MM:SS] text` format (each line has both start and end timestamp, where end = start of next line) and `video_metadata.txt` with title/duration/url.

## Step 4: Analyze Transcript and Suggest Clips

This is the core creative step. Before analyzing, load the two reference files into context:

1. Read `~/.claude/skills/pod-clips/references/clip_cutting_rules.md`
2. Read `~/.claude/skills/pod-clips/references/viral_clip_criteria.md`

Then read the full transcript. Go through it carefully and identify clip-worthy moments.

**Critical principle: Capture the WHOLE story, not a trimmed highlight.**

The goal at this stage is to extract complete story arcs — the full narrative from setup through payoff. Do NOT optimize for short duration here. Your job is to find the right boundaries of each story — where it naturally begins and where it naturally ends.

**How to analyze:**

1. Read the entire transcript start to finish. Don't skim.
2. Mark moments that match the viral criteria (contrarian takes, vivid analogies, surprising facts, origin stories, vulnerability, actionable frameworks).
3. For each candidate clip, identify the **full story arc**: where does the story ACTUALLY begin (not just the hook — the earliest context a viewer needs), where is the SETUP, where is the PAYOFF?
4. Apply every rule from the clip cutting rules — especially: read 30 lines before your start (to make sure you're not in the tail of a prior answer) and 30 lines after your end (to make sure you're not cutting before the punchline).
5. Aim for roughly 1 clip per 7–8 minutes of source video, but prioritize quality over hitting a number.
6. **Do NOT trim clips to fit a short duration target.** If a complete story runs 90 seconds or even 2 minutes, that's fine. Cutting too tight at this stage loses context that can never be recovered. **Hard ceiling: 2 minutes (120s).** If a story runs longer, find a tighter entry point or split it into two clips.

**Save to `analysis/clip_suggestions.md`** with this format for each clip:

```markdown
## Clip N: "<Title>"
- **Start:** MM:SS  ← start timestamp of the first kept line
- **End:** MM:SS    ← start timestamp of the line IMMEDIATELY AFTER the last kept line (this is what ffmpeg cuts to)
- **Duration:** ~Xs
- **Hook (first 3 sec):** "<exact words that open the clip>"
- **Punchline (last line):** "<exact words that close the clip>"
- **Why it works:** <1-2 sentences on why this will perform as short-form>
- **Story arc:** HOOK: <what> → SETUP: <what> → PAYOFF: <what>
- **Transcript excerpt:** <paste the exact transcript lines from start to end, preserving [MM:SS-MM:SS] timestamps>
```

**Why End = next line's start:** The transcript uses `[MM:SS-MM:SS]` format where each line's end timestamp is the start of the next line. Always set the clip End to the end timestamp of the last kept line (i.e., the start of the first line you're NOT including). This gives ffmpeg a clean, precise cut point — no guessing, no cutting mid-sentence.

Including the transcript excerpt is important — it lets the QA agent and user verify without jumping between files.

## Step 5: QA Review (Sub-Agent)

Launch a sub-agent whose job is to be a skeptical reviewer. The QA agent's prompt:

> You are a QA reviewer for short-form video clips cut from a long-form interview. Your job is to find problems with the suggested clips before they go to the user.
>
> **Critical context:** Your job is NOT to make clips shorter. Your job is to ensure each clip captures the COMPLETE story — full context, full arc, full payoff. It is much worse to cut too tight (losing story context) than to cut too loose (including extra material that can be trimmed later). Err on the side of INCLUDING more context, not less.
>
> Read the full transcript file at: `<path to full_transcript.txt>`
> Read the clip suggestions at: `<path to clip_suggestions.md>`
> Read the cutting rules at: `~/.claude/skills/pod-clips/references/clip_cutting_rules.md`
>
> For EACH suggested clip, check:
> 1. **Start point:** Read 30 lines before the clip start in the transcript. Is the clip starting mid-answer from a prior question? Is there leftover context from a different topic? Also check: is there essential setup BEFORE the suggested start that the viewer needs to understand the story? If so, recommend EXTENDING the start earlier.
> 2. **End point:** Read 30 lines after the clip end. Is there a better punchline or button we're missing? Does the clip end on a comma instead of a period? Does the story continue past the suggested end with material that completes the arc?
> 3. **Dangling context:** Would a stranger understand the first sentence without any prior context? Are there pronouns without antecedents?
> 4. **Scroll test:** Are the first 3 seconds compelling? Or are they "yeah", "um", filler? NOTE: A few seconds of runway before the hook is acceptable if it provides necessary story context.
> 5. **Story completeness:** Does the clip have a clear HOOK → SETUP → PAYOFF? Or is it a fragment? This is the MOST IMPORTANT check. If the story feels incomplete, recommend extending the clip boundaries, not dropping it.
>
> For each clip, output one of:
> - **PASS** — Clip captures the complete story as-is.
> - **ADJUST** — Clip idea is good but timestamps need fixing. Provide corrected start/end with reasoning. When adjusting, PREFER extending boundaries to capture more context over trimming to make it shorter.
> - **DROP** — Clip doesn't work as standalone short-form even with adjusted timestamps. Explain why.
>
> Save your full review to: `<path to analysis/qa_report.md>`

## Step 5b: Finalize clip_suggestions.md (Source of Truth)

After the QA agent finishes, read `qa_report.md` and **update `clip_suggestions.md`** to reflect the final state:

1. For any clip marked **ADJUST**: update the Start, End, Duration, Hook, and Punchline fields with the QA agent's corrected values.
2. For any clip marked **DROP**: remove it entirely from the file.
3. **Most importantly: update the Transcript excerpt** for every adjusted clip. Go back to `full_transcript.txt`, extract the exact lines between the NEW start and end timestamps, and replace the old excerpt.

After this step, `clip_suggestions.md` is the **single source of truth** — it contains the final timestamps AND the exact transcript for each clip. Everything downstream (presenting to user, cutting, generating per-clip transcripts) reads from this file.

## Step 6: Present to User

Show the user the final clip list from the updated `clip_suggestions.md`. For each clip, present:
- Title and timestamps
- The hook (first line) and punchline (last line)
- Duration
- QA status (passed / adjusted with reason)

Ask the user:
- Which clips to cut (all, specific numbers, or none)
- Whether any timestamps need manual adjustment

Do NOT proceed to cutting until the user explicitly approves.

## Step 7: Cut Approved Clips

For each approved clip, run the cut script:

```bash
bash ~/.claude/skills/pod-clips/scripts/cut_clips.sh \
    "<youtube_url>" \
    "clip_cut/<video-slug>/clips" \
    "clip<N>_<slug_name>" \
    "<start_time>" \
    "<end_time>"
```

Run clips in parallel (background) when possible — they're independent downloads.

After all clips are done, list the final files with sizes:

```bash
ls -lh clip_cut/<video-slug>/clips/*.mp4
```

## Step 7b: Generate Per-Clip Transcripts

After cutting, create a `.txt` file alongside each `.mp4` that contains the **exact transcript lines** for that clip. Pull these directly from the transcript excerpts already in `clip_suggestions.md` (which is the source of truth at this point).

Save as `clip_cut/<video-slug>/clips/<clip_name>.txt` with this format:

```
# Clip: "<Title>"
# Source: <youtube_url>
# Timestamps: MM:SS - MM:SS (original video)
# Duration: ~Xs
# Cut from: full_transcript.txt

[MM:SS-MM:SS] First line of the clip...
[MM:SS-MM:SS] Second line...
...
[MM:SS-MM:SS] Last line of the clip...
```

Each line preserves the `[start-end]` format from `full_transcript.txt`. The end timestamp on the last line is where the clip was cut — useful if this file is later passed to `/clip-condenser`.

**Important:** Use the FINAL timestamps from `clip_suggestions.md`. The transcript lines must match what's actually in the .mp4 file. These .txt files are the handoff point if the user later wants to condense clips.

---

## Important Behaviors

- **Never generate reference content at runtime.** The clip cutting rules and viral criteria are in the `references/` folder. Read them, don't recreate them.
- **Never dump files in the root directory.** Everything goes under `clip_cut/<video-slug>/` with proper subdirectories.
- **Always run the prerequisite check first.** It's a 2-second script that saves minutes of debugging.
- **The QA step is not optional.** Always run the QA sub-agent before presenting to the user. The whole point is catching mistakes before the user sees them.
- **`clip_suggestions.md` is the source of truth.** After QA, it must reflect the final timestamps and transcript excerpts. Never cut from stale/pre-QA data.
- **MP4 is the output format.** The cut script handles webm→mp4 conversion automatically. Don't output webm files to the user.
- **Save everything.** Transcript, suggestions, QA report, final clips, per-clip transcripts — all persisted in the directory structure. This makes it easy to come back later or iterate.
- **If clips need tightening after extraction**, the user can run `/clip-condenser` on any clip + its .txt transcript file.
