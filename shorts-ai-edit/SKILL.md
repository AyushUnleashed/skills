---
name: shorts-ai-edit
description: End-to-end AI video editor for 9:16 short-form content (1080x1920). Use this skill when the user wants to edit a video with B-roll, assets, or motion graphics — given a main A-roll video, a timestamped transcript, and optional image/video assets. Handles the full pipeline: analyzing assets visually, building an Edit Decision List (EDL), generating Remotion motion graphics for gaps, and FFMPEG assembly into a final edited video. Trigger whenever the user mentions editing a short-form video, adding B-roll, cutting to assets, creating Reels/TikTok/Shorts content, or provides a transcript + video together and wants them edited.
---

# Shorts AI Edit

Full pipeline to edit a 9:16 1080×1920 video with B-roll assets and motion graphics.

## Pipeline Overview

1. **Setup** — collect file paths from the user
2. **Asset Analysis** — understand what each asset contains (vision + frames)
3. **EDL Creation** — plan every section: A-roll, asset, or motion graphic
4. **EDL Approval** — show the plan to the user and get sign-off before generating anything
5. **Motion Graphics** — batch all prompts first, then generate Remotion animations
6. **Assemble** — FFMPEG edit using the finalized EDL → `edited_output.mp4`

---

## Phase 1: Setup

### 1a — Python environment (first time only)
The scripts require Python 3.10+ and a virtual environment. First, set the skill directory variable — this makes all subsequent commands path-independent:

```bash
SKILL_DIR="${HOME}/.claude/skills/shorts-ai-edit"
```

Check if a `.venv` already exists; if not, set it up:

```bash
python3 -m venv "${SKILL_DIR}/.venv"
"${SKILL_DIR}/.venv/bin/pip" install -r "${SKILL_DIR}/requirements.txt"
```

On Windows, activate with `"${SKILL_DIR}/.venv/Scripts/activate"` instead.

Before running **any** script in this skill, always set `SKILL_DIR` and activate the venv first:
```bash
SKILL_DIR="${HOME}/.claude/skills/shorts-ai-edit"
source "${SKILL_DIR}/.venv/bin/activate"
```

Also confirm `ffmpeg` is installed on the system:
```bash
ffmpeg -version
```
If missing, install via: `brew install ffmpeg` (Mac) or `sudo apt install ffmpeg` (Linux).

### 1b — Project folder and run folder

**Project folder structure:**
Each project lives in a dedicated folder. Inside it you'll find the source files (A-roll, transcript, assets) plus a subfolder for each past edit run. The same video can be edited multiple times — every run gets its own subfolder so nothing overwrites a previous edit.

```
my-project/
├── aroll.mp4              ← main video
├── transcript.txt         ← timestamped transcript
├── assets/                ← optional images/videos
│   ├── chart.jpg
│   └── demo.mp4
├── edit-1/                ← first edit run (all generated files go here)
├── edit-2/                ← second edit run
└── ...
```

**Step 1 — Get the project folder.**
Ask the user for the project folder path if not already provided. Then scan it to auto-detect:
- **Main video** — any `.mp4` or `.mov` at the top level (ask to confirm if multiple found)
- **Transcript** — any `.txt` file at the top level
- **Assets folder** — an `assets/` subfolder if present (optional)

Ask about anything that couldn't be auto-detected.

**Step 2 — Create this run's folder.**
Count existing `edit-N/` subfolders and create the next one:

```bash
PROJECT_DIR="<project_folder_path>"
RUN_NUM=$(ls -d "${PROJECT_DIR}"/edit-* 2>/dev/null | wc -l)
RUN_NUM=$((RUN_NUM + 1))
RUN_DIR="${PROJECT_DIR}/edit-${RUN_NUM}"
mkdir -p "${RUN_DIR}"
```

All files generated during this edit — `.md` analysis files, `edl.md`, `motion_prompts.md`, motion graphic `.mp4`s, and the final `edited_output.mp4` — are saved inside `$RUN_DIR`. Nothing is written outside of it.

**IMPORTANT: Never read or reference files from previous edit runs (e.g. `edit-1/`, `edit-2/`) unless the user explicitly asks you to. Every edit starts completely fresh from the source assets, A-roll video, and transcript.**

Confirm the run folder path with the user before proceeding: e.g. _"Starting edit-2 in `/path/to/project/edit-2/`. Go?"_

---

## Phase 2: Asset Analysis

Goal: understand every asset so you can match them to the right transcript sections.

### Images
For each image file in the assets folder:
1. Read it visually using your vision capability
2. Write `<filename>.md` into `$RUN_DIR` (not next to the asset) with:
   - What's shown (objects, people, text on screen, mood, colors)
   - What topic/concept it could illustrate in a video
   - Recommended layout: `FULL` or `SPLIT` (see layout tips in Phase 3)

### Videos
For each video file in the assets folder:
1. Extract frames using the auto-sampling script:
   ```bash
   python "${SKILL_DIR}/scripts/extract_frames.py" "<asset_path>"
   ```
   The script detects duration and picks the interval automatically — targeting ~30 frames total, floor of 1fps. Frames saved to `/tmp/frames/<filename>/`.
2. Read every frame the script produced — the count is already manageable.
3. Write `<filename>.md` into `$RUN_DIR` (not next to the asset) with:
   - What happens (action, subject, mood, key moments)
   - Duration and pacing
   - What topic it could illustrate
   - Recommended layout: `FULL` or `SPLIT`

### Asset Master
After analyzing all assets, save `asset-master.md` to `$RUN_DIR` (not the assets folder — keep source files untouched):

```markdown
# Asset Master

## Images
- `product_shot.jpg` → [product_shot.md] — App dashboard close-up. Best for: feature demos. Layout: SPLIT
- `cost_compare.jpg` → [cost_compare.md] — Infographic: traditional team vs AI cost. Best for: pain point sections. Layout: FULL

## Videos
- `demo_screen.mp4` → [demo_screen.md] — Product walkthrough, 12s. Best for: "here's how it works". Layout: FULL
```

---

## Phase 3: EDL Creation

Goal: divide the transcript into sections and assign each one a visual treatment.

### Parse the transcript
Each line starts with a `[MM:SS]` timestamp. Group consecutive lines into logical **sections** — typically one thought, sentence, or idea (3–15 seconds each). A section under 2 seconds is too short to cut to; merge it with an adjacent one.

### For each section, decide the edit type

**A-ROLL** — show only the speaker. Use when:
- It's a personal, emotional, or direct-to-camera moment
- The speaker's authenticity carries the message
- No asset meaningfully illustrates what's being said (closing CTAs almost always land better as A-roll)

**ASSET** — cut to or overlay a provided asset. Check `asset-master.md` first. Use when an existing asset directly and clearly illustrates the concept being discussed. The connection should be obvious, not forced.

**MOTION-GRAPHIC** — generate a Remotion animation. Use when no asset fits but a visual would genuinely help the viewer understand — abstract concepts, step-by-step processes, comparisons, stats.

### Layout tips

> **FULL** (asset fills entire 1080×1920 screen):
> Use when the asset IS the story for that moment and needs space to breathe — infographics, charts, process flows, product demos that need to be seen clearly. The speaker disappears; the visual takes over completely. Best for high-impact visual punches.
>
> **SPLIT** (asset top 1080×960 / speaker bottom 1080×960):
> Use when you want to *show something while the speaker keeps talking* — and both matter. The speaker's presence adds credibility and context to what's on screen. Good for: "here's the feature I'm talking about", walking through a UI, showing a stat while explaining it. The viewer can look at the asset and glance down at the speaker's face.
>
> **A-ROLL only**:
> Don't feel pressure to always cut away. Moments of direct eye contact and authentic speech are often the most engaging thing you can show. Reserve B-roll for moments where a visual genuinely adds information or emotion — not just to avoid showing the speaker.

### Image display — FULL layout
When an image is used in FULL layout, **do not always crop it to fill the screen**. Instead, the build script will:
- Scale the image to fit entirely within the frame (no cropping)
- Add dark padding around it (20px)
- Apply rounded corners (30px radius)

This is the right approach for screenshots, infographics, charts, and anything where the full image content matters. The script handles this automatically for images (`.jpg`, `.png`, `.webp`). Videos in FULL layout still use crop-to-fill.

### Save the EDL
Save as `edl.md` inside `$RUN_DIR`. See `references/edl_format.md` for the exact format and examples. Make sure every second of the video is covered with no gaps or overlaps.

---

## Phase 3.5: EDL Approval

Before generating anything, show the user what you're planning. Present the EDL as a clear table:

```
## EDL — Ready for Your Approval

| # | Time | Script | Type | Visual |
|---|------|--------|------|--------|
| 1 | 00:00–00:09 | "Most founders waste months hiring..." | ASSET / FULL | cost_compare.jpg — infographic showing traditional team vs AI cost |
| 2 | 00:09–00:15 | "ReelsAI changes that. AI handles..." | A-ROLL | (speaker only) |
| 3 | 00:15–00:22 | "Here's the workflow — script, film..." | MOTION-GRAPHIC / FULL | Animated 4-step flow: Script→Film→Edit→Post, dark bg, neon green accents, 7s |
| 4 | 00:22–00:27 | "Your first video ships in an hour..." | ASSET / FULL | demo_screen.mp4 — product walkthrough |
| 5 | 00:27–00:30 | "Try it free at ReelsAI.pro." | A-ROLL | (speaker only) |

Motion graphics to generate: 1
Reply with "approved" or tell me what to change.
```

Wait for explicit approval before proceeding. If the user requests changes, update the EDL and show the table again.

---

## Phase 4: Motion Graphics Generation

### Step 4a: Ask the user about motion graphic style

Before writing any prompts, ask the user what visual style they want for the motion graphics. Present the options below and **recommend what you think fits best** based on what each section is actually saying.

**Style options:**

| Style | What it looks like | Best for |
|---|---|---|
| **Kinetic Typography** | Words, phrases, and key terms animate onto screen — bold, fast, punchy | Taglines, strong statements, moments where the *words themselves* are the message |
| **Visual Explainer** | Icons, simple illustrations, arrows, diagrams that walk through a concept step by step | Processes, how-things-work, multi-step explanations |
| **Data & Stats** | Animated numbers, bar charts, counters, comparisons growing/revealing | Proving a point with numbers, before/after, growth metrics |
| **Product UI Mockup** | Simulated app screens, browser windows, UI interactions | Feature walkthroughs, product demos when no real asset exists |
| **Visual Metaphor** | Symbolic objects or abstract shapes that represent a concept emotionally | Complex/emotional ideas where the literal words would be too abstract or dry |
| **Abstract / Ambient** | Geometric shapes, gradients, particles, flowing motion | Mood-setting, transitions, intro/outro moments with no specific concept to explain |

How to present it:
```
I need to create [N] motion graphic(s). Here's what I'm thinking for each:

- Section 3 ("Here's the workflow..."): Visual Explainer — a step-by-step flow
  makes sense since you're literally describing a process.
- Section 6 ("2x faster than hiring a team"): Data & Stats — the claim is
  number-driven, so an animated comparison would land hard.

Do these styles work? Or would you prefer something different?
You can also choose one style for everything if you want visual consistency.
```

Wait for the user's response before writing any prompts.

### Step 4b: Write all prompts to motion_prompts.md

Before writing prompts, read `references/guide_to_motion_graphics.md`. It contains the graphic design foundation (visual hierarchy, contrast, typography rules), motion physics (easing, overshoot, secondary action), worked examples of multiple approaches for the same audio line, and the 12 motion design principles checklist. Use it to make prompts specific and visually intentional — not generic.

With the style confirmed, write detailed prompts for every MOTION-GRAPHIC section and save to `$RUN_DIR/motion_prompts.md`. Incorporate the chosen style into each prompt:

```markdown
# Motion Graphic Prompts

## Section 3 — 00:15–00:22 (7s / FULL)
**Style**: Visual Explainer
**Prompt**: Animated 4-step flow: Script → Film → Edit → Post. Each step pops onto
screen with a bounce, connected by arrows. Dark background (#111111), neon green
(#00FF88) accent color. Clean sans-serif labels. Duration: 7 seconds.
**Output file**: motion_graphic_s3.mp4
**Resolution**: 1080×1920 (FULL)

## Section 6 — 00:45–00:52 (7s / SPLIT)
**Style**: Data & Stats
**Prompt**: Animated bar chart. Left bar: "Old way: 3 weeks" grows tall slowly.
Right bar: "ReelsAI: 1 hour" shoots up fast. Bold numbers count up. Dark bg,
neon green accent. Duration: 7 seconds.
**Output file**: motion_graphic_s6.mp4
**Resolution**: 1080×960 (SPLIT — top half only)
```

Show this file to the user and confirm before generating.

### Step 4c: Generate all animations in parallel

Once prompts are approved, **spawn all animations simultaneously** — do not wait for one to finish before starting the next. Launch one subagent per motion graphic, all at the same time:

Each subagent task:
```
First, load the remotion-best-practices skill by calling ToolSearch with query "select:remotion-best-practices". Then use it to build and render this animation:

Style: <style>
Prompt: <full prompt text>
Resolution: <1080×1920 or 1080×960>
Duration: <N> seconds → durationInFrames = <N × 30>
Save rendered .mp4 to: <RUN_DIR>/motion_graphic_sN.mp4
```

Wait for all subagents to complete, then collect their output file paths.

**Resolution reminder** (critical for each subagent):
- `FULL` layout → **1080×1920** (full 9:16)
- `SPLIT` layout → **1080×960** (top half only — build script stacks speaker below)

### Step 4d: Update the EDL
Once all animations are confirmed saved, update `edl.md` — replace every `[to be generated]` with the actual file path.

---

## Phase 5: Assemble with FFMPEG

Once all `Asset File` fields in the EDL have real paths, run:

```bash
python "${SKILL_DIR}/scripts/build_edit.py" \
  --video "<main_video_path>" \
  --edl "${RUN_DIR}/edl.md" \
  --output "${RUN_DIR}/edited_output.mp4" \
  --assets-dir "<assets_folder>"
```

What the script does per layout:
- **A-ROLL**: trims the main video at those timestamps, scales to 1080×1920
- **FULL (video asset)**: scales/crops asset to fill 1080×1920, A-roll audio continues
- **FULL (image asset)**: scales image to fit (contain, no crop), dark padding, rounded corners, A-roll audio
- **SPLIT**: asset (1080×960, top) + speaker (1080×960, bottom) stacked; A-roll audio throughout

If an asset file is missing or still `[to be generated]`, the script falls back to A-ROLL for that section and prints a warning.

---

## Output

Tell the user:
- Path to the final video
- Total sections: how many A-ROLL / ASSET / MOTION-GRAPHIC
- Any warnings (missing assets, fallbacks)
