---
name: highlight-text-animation
description: Generate animated text highlight overlays on images using Remotion. Use this skill whenever the user wants to highlight, underline, or draw attention to specific text lines in a screenshot, tweet, blog post, article, or any image containing text — with an animated wipe/marker effect. Also use when the user says "highlight this part", "animate this text", "text highlight animation", or wants to create a kinetic typography effect over a screenshot.
---

## What this skill does

Takes any image containing text (tweet screenshot, blog post, article, documentation, etc.), detects the text lines using OCR, and generates a Remotion animation component that highlights specified lines with an animated wipe effect — like a highlighter pen sweeping across the text.

The default highlight style uses `mixBlendMode: 'difference'` with a white overlay, which inverts the colors underneath the highlight. This produces high-contrast, visually striking results on both dark and light backgrounds. A colored "marker" style is available if the user explicitly requests it.

## Prerequisites

This skill depends on `/remotion-best-practices` — invoke that skill before writing any Remotion code.

## Skill path

This skill is located at the directory containing this SKILL.md file. When the skill is loaded, you know the path. Use it to reference bundled scripts:
- `<this-skill-directory>/scripts/detect_lines.py` — OCR detection, image dimensions, style defaults
- `<this-skill-directory>/scripts/generate_component.py` — generates the TSX component from coords JSON
- `<this-skill-directory>/scripts/manage_compositions.py` — register/unregister/archive compositions in Root.tsx
- `<this-skill-directory>/scripts/requirements.txt` — Python dependencies

Throughout this document, `SKILL_DIR` refers to the directory containing this SKILL.md.

## What the scripts handle vs what needs LLM judgment

The scripts handle all deterministic work — OCR, component generation, Root.tsx management. This saves tokens and avoids mistakes. The LLM's job is:
- Understanding what the user wants (which lines, any preferences)
- Presenting the plan and interpreting user feedback
- Making adjustments when the user asks for changes (editing the generated TSX directly)

**When the user asks for changes** (e.g., "make it slower", "use pink instead", "shift the highlight down a bit"), edit the generated TSX file directly. The component is a standard React file — tweak the constants, coordinates, or style values as needed. You don't need to re-run the scripts for small adjustments. Only re-run `generate_component.py` if the user wants to start over with different lines or a fundamentally different setup.

## Core principle: one plan, one approval

Do not ask the user multiple questions across multiple turns. Instead, gather all information from the OCR script, make smart defaults for everything, and present a single consolidated plan. The user approves or modifies the plan in one shot. This keeps the interaction tight and gives the user full visibility without being peppered with questions.

## Important: do not read the image file visually

Never use the Read tool to view/inspect the image. The OCR script (`detect_lines.py`) is the single source of truth for text detection, coordinates, image dimensions, and style recommendations. Reading the image visually is unreliable and unnecessary — rely only on script output.

## Re-run awareness

This skill may be invoked multiple times in the same project — different images, revised highlights, or the user coming back after a break. Before doing any setup work, check what already exists:

1. **Remotion project**: Look for `remotion.config.ts` or `"remotion"` in `package.json` in the current working directory. If found, you're already inside a Remotion project — skip scaffolding entirely.
2. **Python venv**: Check if `tmp/.venv/bin/python` exists and works (`tmp/.venv/bin/python --version`). If it does, skip venv creation and pip install.
3. **Previous components**: Check `src/text-highlights/` for existing `.tsx` files. These are from prior runs — the `manage_compositions.py replace` command handles archiving them, so you don't need to clean up manually, but knowing they exist tells you this isn't a first run.
4. **OCR coords**: If `tmp/highlight_coords.json` exists, it's from a previous run. Don't reuse it — always re-run detection for the current request. But its presence confirms the venv and Tesseract are working.

The goal: on a re-run, the only steps that actually execute are detection (Step 3), planning (Step 4), and generation (Step 5). Steps 1-2 should be near-instant checks that confirm "already done" and move on.

## Workflow

### Step 1: Check for Remotion project

Look for `remotion.config.ts` or `"remotion"` in `package.json` **in the current working directory**. If found, skip to Step 2 — you're already in a Remotion project.

If neither exists, scaffold one into a `text-highlights/` directory (always use this name so re-runs can find it):

```bash
npx --yes create-video@latest --yes --blank text-highlights
cd text-highlights && npm i
```

The `--yes` flag skips all interactive prompts, and `--blank` creates an empty canvas project (no demo code). After scaffolding, run `npm i` to install dependencies.

If a `text-highlights/` directory already exists with a Remotion project inside it, `cd` into it and use it — do not create a second one.

### Step 2: Set up the OCR environment

**Quick check first** — if `tmp/.venv/bin/python` exists and `which tesseract` succeeds, skip this entire step. Everything is already set up from a previous run.

If not, proceed with setup:

**Check Python is available:**
```bash
python3 --version
```
If python3 is not found, tell the user they need Python 3.8+ installed and stop.

**System dependency — Tesseract binary:**

```bash
which tesseract
```

If missing, ask the user to install it. Do NOT try to run sudo yourself:
> "Tesseract OCR isn't installed. It's a system package needed for text detection. Can you run: `! sudo apt-get install -y tesseract-ocr`"

On macOS: `! brew install tesseract`

Wait for the user to confirm before proceeding.

**Python venv setup:**

Create a venv in the project's `tmp/` directory and install from the skill's requirements.txt:

```bash
mkdir -p tmp
python3 -m venv tmp/.venv
tmp/.venv/bin/pip install -r SKILL_DIR/scripts/requirements.txt
```

Always install from `requirements.txt` (not ad-hoc `pip install` commands) so versions are consistent. If pip fails (e.g., missing build tools), show the user the error and suggest fixes — don't silently skip.

### Step 3: Detect text lines and gather all data

**Ensure required directories exist:**
```bash
mkdir -p public src/text-highlights
```

Copy the image to `public/` (Remotion needs it there for `staticFile()`):
```bash
cp <image_path> public/
```

Run the detection script to get all lines, image dimensions, and style info:

```bash
tmp/.venv/bin/python SKILL_DIR/scripts/detect_lines.py <image_path>
```

This outputs:
- All detected text lines with their bounding boxes (as % of image dimensions)
- Image dimensions with suggested aspect ratio (closest common ratio under 1080p)
- Highlight style config (defaults to invert mode)
- Auto-calculated duration based on word count

**If OCR returns 0 lines:** The image might be too low-res, have unusual fonts, or be a format Tesseract struggles with. Suggest the user try a higher resolution version, converting to PNG, or checking that the image contains readable text.

Show the detected lines to the user so they can see what was found, then move directly to the plan.

### Step 4: Present the plan for approval

Based on the script output and the user's request, present ONE consolidated plan covering all decisions. The user told you which lines they want (or you infer from context) — combine that with smart defaults from the script output.

Format the plan like this:

> **Here's my plan:**
> - **Lines**: 13-16 ("The outcome is the final..." to "...environment's SQL database.")
> - **Duration**: 3.2s (auto-calculated from word count) 
> - **Style**: Inverted (white highlight, difference blend — high contrast)
> - **Resolution**: 1080x1080 (your image is near-square at 1.05:1)
> - **Background**: #f5f5f5 (light, matched to image edges)
>
> Want me to proceed, or change anything?

Key defaults to use:
- **Style**: Always default to `invert` (white, `mixBlendMode: 'difference'`, opacity 1.0). Only use `marker` mode if the user explicitly asks for colored highlights.
- **Resolution**: Use the `suggested_width` and `suggested_height` from the script output — it picks the closest common aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4) capped at 1080p.
- **Duration**: Use the auto-calculated duration from the script output. Show it in seconds so the user can easily judge if it feels right. If the user's context implies a specific duration (e.g., "make a 3-second highlight"), use that instead.
- **Background color**: `#000000` for dark images, `#f5f5f5` for light images (based on `bgBrightness` from script).

If the user already specified lines in their initial message, run the script with `--lines` to select them and include the selection in the plan. If they haven't specified lines yet, show the detected lines and ask which ones to highlight — but bundle this into the same turn where you show the plan for everything else.

Wait for the user to approve or request changes before proceeding.

### Step 5: Generate everything with scripts

Once the user approves the plan (or after applying their modifications), run the scripts to generate the component and manage Root.tsx. These are deterministic — no LLM judgment needed.

**5a. Run detection with line selection** (if not already done):

```bash
tmp/.venv/bin/python SKILL_DIR/scripts/detect_lines.py <image_path> --lines <start>-<end>
```

Flags: `--lines 3-7` for line range, or `--start "text" --end "text"` for text match. If the user requested a specific style, pass `--mode marker --color "#FF69B4" --opacity 0.5`.

This saves to `tmp/highlight_coords.json`.

**5b. Generate the TSX component:**

```bash
mkdir -p src/text-highlights
tmp/.venv/bin/python SKILL_DIR/scripts/generate_component.py \
  tmp/highlight_coords.json <image_filename> \
  --output src/text-highlights/<ComponentName>.tsx
```

If the user specified a duration, pass `--duration-seconds <N>`. Otherwise the script auto-calculates from word count.

The script outputs JSON with `component_name`, `output_path`, `duration_frames`, and `duration_seconds` — use these for the next step.

**5c. Archive old compositions and register the new one:**

```bash
python3 SKILL_DIR/scripts/manage_compositions.py replace \
  <ComponentName> <duration_frames> <width> <height> \
  --root-tsx src/Root.tsx
```

The `replace` action does three things in one command:
1. Finds all existing highlight compositions in Root.tsx
2. Unregisters them (removes imports + `<Composition>` entries)
3. Moves old TSX files to `src/text-highlights/_archive/`
4. Registers the new composition

Use `suggested_width` and `suggested_height` from the detect script output for the dimensions.

Other actions available if needed:
- `register` — just add a new composition without touching existing ones
- `unregister` — remove from Root.tsx but keep the file
- `archive` — unregister + move file to _archive/

### Step 6: Invoke `/remotion-best-practices`

Before the first run of this skill in a session, invoke the `/remotion-best-practices` skill. This ensures the LLM has the Remotion rules loaded for when the user asks for manual adjustments. Key rules:
- All animations driven by `useCurrentFrame()` — CSS transitions/animations are forbidden
- Use `spring()` for wipe effects
- Use `<Img>` from remotion, not `<img>` HTML
- Use `staticFile()` for assets in `public/`

This step is only relevant if the user will ask for adjustments. The generated component already follows all Remotion rules, so if the user is happy with the script output, no Remotion knowledge is needed.

### Step 7: Handle user adjustments

After generating and previewing, the user may ask for changes. Common requests and how to handle them:

**Re-run the scripts** for these (fundamentally different setup):
- Different lines ("actually highlight lines 5-8 instead")
- Different image
- Completely different duration

**Edit the generated TSX directly** for these (small tweaks):
- "Make it slower/faster" → adjust `delay` values in `HIGHLIGHT_LINES` or `HIGHLIGHT_START_FRAME`
- "Use a different color" → change `HIGHLIGHT_COLOR`, `HIGHLIGHT_OPACITY`, `BLEND_MODE`
- "The highlight is a bit too high/wide" → adjust individual `top`/`left`/`width`/`height` in `HIGHLIGHT_LINES`
- "Change background color" → update `backgroundColor` in `AbsoluteFill`
- "Make the wipe animation snappier/smoother" → adjust `damping` in spring config or `durationInFrames`
- "Highlight from right to left" → change `transformOrigin` from `'left center'` to `'right center'`
- "Add a glow/shadow" → add `boxShadow` to the highlight div style
- "Make highlights appear all at once" → set all `delay` values to `0`

**Edit Root.tsx** for these (composition-level changes):
- "Make it 16:9 / landscape / square" → update `width` and `height` on the `<Composition>`
- "Make it longer/shorter overall" → update `durationInFrames` on the `<Composition>`

Use `manage_compositions.py register` to re-register with new dimensions/duration if you prefer, or just edit Root.tsx directly — it's a one-line change either way.

The generated TSX is a standard React component with clearly named constants at the top — easy to read and modify. For anything not listed above, just read the component, understand its structure, and make the edit. It's not locked down.

### Step 9: Preview and render

Render a still frame first to verify positioning:
```bash
mkdir -p out
npx remotion still <CompositionId> --frame=<last_highlight_delay + HIGHLIGHT_START_FRAME + 14> out/preview.png
```

Show the rendered still to the user and ask if they want to:
1. **Render** the full video to mp4
2. **Preview** in the Studio (`npm run dev`)
3. **Adjust** anything about the positioning or style

If the user chooses to render:
```bash
npx remotion render <CompositionId> out/<original_image_name>_highlight.mp4
```
