---
name: clip-condenser
description: "Use this skill whenever the user wants to condense, tighten, or trim a video clip for short-form content — Reels, TikTok, Shorts, or any format where under 60 seconds is the target. Triggers: 'tighten this clip', 'condense this', 'make this shorter', 'trim the fat', 'cut this down to 60 seconds', 'tighten this for a reel', 'this clip is too long, shorten it'. Input is a video file + transcript with timestamps (or a folder containing both). Output is a condensed video file via ffmpeg + the cut list explaining what was removed and why. The target duration is ALWAYS under 60 seconds unless the user explicitly states otherwise. Do NOT use for finding clips in long-form content (that's pod-clips), color grading, audio mixing, captioning, or motion graphics."
---

# Clip Condenser — Tighten a Clip to Under 60 Seconds

Take a source clip and its transcript, decide what to cut, then execute the edit with ffmpeg. The goal is a clip that stands alone as a complete short-form piece — nothing extraneous, nothing missing.

**Target: under 60 seconds. Always.**

## Step 0: Gather Inputs

Ask the user for:
1. **Video file** — path to the source clip (mp4, mov, webm, etc.)
2. **Transcript with timestamps** — a text file with timestamps marking when each line is spoken

If the user gives you a folder, look inside it for the video and transcript files.

Verify both files exist before proceeding. If the transcript is missing timestamps, tell the user — you need timestamps to build the ffmpeg command.

**Transcript format:** Each line has a start timestamp and optionally an end timestamp — e.g. `[MM:SS-MM:SS] text` or just `[MM:SS] text`. Both are supported. When the end timestamp is present, use it directly. When it's absent, treat the end of a line as the start of the next line — because that's what it is.

---

## Step 1: Read the Transcript as Text

Do not start thinking about timestamps yet. Read the full transcript as if it were a paragraph of text. Ask yourself: **which sentences would I put in a tweet?** Everything else is a candidate for removal.

This gives you the **spine** — the irreducible sequence of ideas the clip cannot exist without.

---

## Step 2: Identify the Layers

Every clip contains these layers. Label each line of the transcript:

| Layer | What it is | Default action |
|---|---|---|
| **Hook** | The first line that earns attention | KEEP — always |
| **Setup** | Context needed to understand the payoff | KEEP if load-bearing, CUT if the viewer can infer it |
| **Payload** | The actual insight, story, or punchline | KEEP — always |
| **Filler** | Ums, pauses, restarts, "you know", "like", "sort of" | CUT — always |
| **Tangent** | A branch that doesn't return to the spine | CUT unless it makes the payload land harder |
| **Tail** | Trailing hedges, "anyway", "that's just me", host acknowledgments | CUT — always |
| **Landing** | The final sentence that closes the idea | KEEP — always, end on this |

The Hook and Landing are non-negotiable anchors. If the original hook is weak, flag it but do not invent a new one.

---

## Step 3: Apply the Cutting Rules

### Rule 1 — Cut the Runway
Speakers take 3-10 seconds to warm up. The first sentence is almost always cuttable.
> "So I've been thinking about this for a while, and I think..." → Start at the actual idea.

### Rule 2 — Cut Filler Words Within Sentences
"It's like... you know... essentially a timing problem" → "It's a timing problem"
These are sub-second cuts. Done right, nobody notices.

### Rule 3 — Cut the Tail
Hedges and disclaimers at the end deflate the clip.
> "...or something like that." / "I don't know, maybe." / "Anyway, yeah." → End on the strongest sentence.

### Rule 4 — Cut Tangents, Protect the Spine
Does the tangent make the payload land harder, or dilute it? Dilutes → cut the whole branch.

### Rule 5 — Protect Emotional Beats
A laugh, a cracked voice, a deliberate pause before a key line — these carry emotion. Never cut them. If you're over duration, cut words surrounding the beat, not the beat itself.

### Rule 6 — Test Logical Connectors
Words like "but", "so", "that's why" are sometimes load-bearing. When you remove the sentence before them, check if the connector still makes sense. If not, either restore the preceding sentence or remove the connector too.

---

## Step 4: Check Duration

Do this in two passes:

**Pass 1 — Quick triage (word count):** Before doing any timestamp arithmetic, count the words in all KEEP lines and estimate total runtime:
- **Average pace**: 140 wpm (conversational podcast)
- **Fast talker** (tech founders, excited): 160 wpm
- **Slow talker** (deliberate, pausing): 110 wpm
- Formula: `word count ÷ wpm × 60 = estimated seconds`
- Add 1-3 seconds per emotional beat or deliberate pause

If this estimate is already over 60 seconds, go back and cut more — don't proceed to the timestamp check yet.

**Pass 2 — Accurate duration (timestamps):** Once word count suggests you're in range, sum the actual timestamp ranges of all KEEP segments. For each segment: start = start of the first kept line, end = start of the next line after the last kept line (since a line ends where the next begins). This is the number that matters — use it as the final duration.

**If still over 60 seconds after timestamps**: find the weakest keeper on the spine. Does the clip make sense without it? If yes, cut it. If no, it's load-bearing — look elsewhere.

---

## Step 5: Coherence Check

Read the final kept lines as a stranger who has never seen the source. Ask:

- Does it make sense without knowing what came before or after?
- Is there a moment where you'd feel lost?
- Does the hook earn the payoff?
- Does the logic chain hold? (A → B → C, not A → C with B missing)
- Does it end on the strongest possible line?

If a gap creates confusion, restore the minimum context needed — usually one sentence is enough.

---

## Step 6: Produce the Output

### 6a. Cut List

Present a table to the user:

| # | Timestamp | Line (abbreviated) | Action | Reason |
|---|---|---|---|---|
| 1 | 00:00-00:03 | "First line of clip..." | KEEP | Hook |
| 2 | 00:03-00:07 | "Yeah so, I mean..." | CUT | Runway filler |
| ... | ... | ... | ... | ... |

### 6b. Spine Summary
One paragraph: what is the core idea, what's the hook, what's the landing.

### 6c. Estimated Runtime
Show the calculation or the sum of kept timestamp ranges.

### 6d. Final Read-Through Script
The kept lines in sequence as continuous text. This is the coherence proof.

### 6e. Jump Cut Warnings

Every significant cut produces a visible jump on screen. Flag them:

| Severity | Gap removed | What to expect |
|---|---|---|
| Minor | < 5 seconds | Barely noticeable, standard short-form aesthetic |
| Moderate | 5-30 seconds | Visible body/head shift, viewer may notice |
| Major | > 30 seconds | Very obvious, may feel jarring |

These are informational only — the skill does straight cuts, no zoom effects or B-roll. The user can decide how to handle major jumps in post.

---

## Step 7: Wait for User Approval

**Do not run ffmpeg until the user approves the cut list.** They may want to adjust — keep something you marked for cutting, or cut something you kept. Incorporate their feedback and update the cut list before proceeding.

---

## Step 8: Execute with FFmpeg

Once the user approves, build and run the ffmpeg command.

### Strategy: Extract kept segments and concatenate

1. **Create a segment list** from the approved KEEP timestamps.
   - `START` = start timestamp of the first kept line in the segment
   - `END` = **end timestamp of the last kept line** in the segment
     - If the transcript has `[MM:SS-MM:SS]` format: use the second timestamp on that last line
     - If the transcript has `[MM:SS]` only: use the start timestamp of the first line after the segment
   - Never use the start of the last kept line as END — that cuts the line off before it's spoken

2. **Extract each segment** using ffmpeg with stream copy (no re-encoding for speed):
   ```bash
   ffmpeg -i input.mp4 -ss START -to END -c copy -avoid_negative_ts make_zero segment_N.mp4
   ```
3. **Create a concat file** (`segments.txt`):
   ```
   file 'segment_0.mp4'
   file 'segment_1.mp4'
   file 'segment_2.mp4'
   ```
4. **Concatenate**:
   ```bash
   ffmpeg -f concat -safe 0 -i segments.txt -c copy output.mp4
   ```

### Important ffmpeg notes

- Use `-c copy` (stream copy) whenever possible — it's fast and lossless. Only re-encode if the concat produces glitches at cut points (which happens when cuts don't land on keyframes).
- If stream copy produces artifacts, fall back to re-encoding:
  ```bash
  ffmpeg -f concat -safe 0 -i segments.txt -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k output.mp4
  ```
- Name the output file descriptively: `{original_name}_condensed.mp4`
- Save in the same directory as the source video unless the user specifies otherwise
- Clean up temporary segment files after successful concatenation

### Verify the output

After ffmpeg finishes:
1. Check the output file exists and has a reasonable file size
2. Get the duration with: `ffprobe -v error -show_entries format=duration -of csv=p=0 output.mp4`
3. Report the final duration to the user and confirm it's under 60 seconds

---

## What Never to Cut

| Element | Why |
|---|---|
| The hook (first strong sentence) | Lose it, lose the viewer in 3 seconds |
| The pause before the key line | Builds anticipation — cutting it flattens the punchline |
| Emotionally weighted words | "We *almost* failed" — cutting "almost" changes everything |
| The sentence that makes the conclusion make sense | If the payoff sounds insane without setup, keep the setup |
| The landing (closing line) | Always end on the speaker, not on "yeah" or "right" from the host |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Over-cutting setup → payoff makes no sense | Restore one sentence of setup |
| Cutting emotional beats → lines land flat | Restore the pause/reaction before the key line |
| Ending on the host's "yeah" or "totally" | End on the guest's last strong sentence |
| Clip at 90s, can't let go of content | Find the weakest keeper, force-test removing it |
| Logic gap (A → C, skipping B) | Either keep B or flag the gap for the user |

---

## Source-Specific Notes

### Podcast / Interview
- Hook must land in first 3 seconds — if it's weak, scan for the real hook
- Viewer has zero context — keep one sentence of setup rather than cutting it
- Cut all host acknowledgments ("yeah", "right", "totally") unless they add momentum
- End on the guest's most quotable line

### Monologue / Conference Talk
- Find the single insight or framework statement first, build the 60s around it
- Cut all preamble and housekeeping ruthlessly
- Budget extra time for within-sentence tightening — monologues have denser filler

### Reaction / Social Video
- Emotional beats ARE the product — protect them above all
- Cut setup aggressively to get to the reaction faster
