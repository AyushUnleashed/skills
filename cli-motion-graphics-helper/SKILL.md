---
name: cli-motion-graphics-helper
description: Generates motion graphic animations for the shorts-ai-edit pipeline. Reads the approved EDL, picks a motion style with the user, writes animation briefs, then generates Remotion TSX components, renders them to mp4, and updates the EDL and workflow state. Requires the remotion-best-practices skill for Remotion code generation. Covers pipeline steps 6 (generate_motion_prompts), 7 (generate_motion_code), and 8 (render_motion). Trigger whenever the cli-shorts-orchestrator delegates motion graphics work, or when the user wants to generate motion graphics for an existing edit run.
compatibility:
  requires_skills:
    - remotion-best-practices
---

# CLI Motion Graphics Helper

You create motion graphics for the EDL — both standalone animations (MOTION-GRAPHIC) and speaker-enhanced animations (A-ROLL-ENHANCED). You write animation briefs, generate Remotion TSX code, render to mp4, and update the project state.

## Inputs

- **`REPO_DIR`** — shorts-ai-edit repo root (default: `/mnt/d/code_me/experiments/shorts-ai-edit`)
- **`RUN_DIR`** — the run directory containing `edl.json` and `workflow_state.json`

## Deliverables

For every MOTION-GRAPHIC and A-ROLL-ENHANCED section in the EDL, produce:

```
${RUN_DIR}/
├── aroll_clips/section_{id}.mp4          ← extracted speaker clip (A-ROLL-ENHANCED only)
├── motion_prompts/section_{id}.json      ← animation brief
├── remotion_components/Section{id}.tsx    ← working TSX code (archived)
├── motion_renders/section_{id}.mp4       ← rendered animation
├── edl.json                              ← asset_file updated to render path
└── workflow_state.json                   ← steps 6, 7, 8 marked completed
```

---

## Process

### 1. Read the EDL

Read `${RUN_DIR}/edl.json`. Each section looks like:
```json
{
  "section_id": 2, "start_seconds": 5.2, "end_seconds": 12.0,
  "script_text": "...", "edit_type": "MOTION-GRAPHIC" | "A-ROLL-ENHANCED" | "A-ROLL" | "ASSET",
  "asset_file": null, "layout": "FULL" | "SPLIT" | null
}
```

You generate for two types:

- **MOTION-GRAPHIC** — standalone animation, no speaker video. Remotion generates everything from scratch. Dimensions depend on layout: FULL = 1080x1920, SPLIT = 1080x960.
- **A-ROLL-ENHANCED** — the speaker's video clip is given to Remotion as input. Remotion controls the entire 1080x1920 frame and can do anything with the speaker: resize them, put them in a corner, add text alongside, apply effects, overlay kinetic typography, picture-in-picture — whatever makes the moment more engaging. The Remotion output IS the final clip (not overlayed on top later).

### 2. Pick a motion style

Present style options and recommend what fits each section's script:

| Style | Best for |
|---|---|
| **Kinetic Typography** | Taglines, strong statements, punchy words |
| **Visual Explainer** | Processes, how-things-work, step-by-step |
| **Data & Stats** | Numbers, metrics, comparisons |
| **Product UI Mockup** | Feature walkthroughs, simulated app screens |
| **Visual Metaphor** | Complex/emotional ideas, symbolic |
| **Abstract / Ambient** | Mood-setting, transitions, intros/outros |

Default: **Visual Explainer**.

### 3. Extract A-roll clips (A-ROLL-ENHANCED sections only)

For each A-ROLL-ENHANCED section, extract the speaker's video clip so Remotion can use it:

```bash
mkdir -p "${RUN_DIR}/aroll_clips"
ffmpeg -y -ss {start_seconds} -t {duration} -i "{aroll_path}" -c copy "${RUN_DIR}/aroll_clips/section_{id}.mp4"
```

Get `aroll_path` from `${RUN_DIR}/workflow_state.json` → `aroll_path` field.

Then copy the clip into Remotion's public folder so `staticFile()` works:
```bash
cp "${RUN_DIR}/aroll_clips/section_{id}.mp4" "${REPO_DIR}/remotion_project/public/aroll_section_{id}.mp4"
```

### 4. Write animation briefs

Read `${REPO_DIR}/references/guide_to_motion_graphics.md` for design principles.

For each section, calculate:
- **Duration:** `end_seconds - start_seconds` (preserve full precision — never round)
- **Dimensions:** A-ROLL-ENHANCED → always 1080x1920 (Remotion controls full frame). MOTION-GRAPHIC → SPLIT = 1080x960, FULL = 1080x1920.
- **Frames:** `round(duration * 30)` for Remotion's `durationInFrames`

**Word-level timestamps** are loaded from `${RUN_DIR}/transcript.json` and filtered per section. Each word's global timestamp is offset to be section-relative (e.g. a word at global 3.8s in a section starting at 3.2s → 0.6s relative). Frame values are `seconds * 30` kept as floats for sub-frame `interpolate()` precision — never rounded.

The Python pipeline (`generate_prompts.py`) handles this automatically. When running manually via the skill, the orchestrator passes the transcript through, so word timestamps appear in the motion prompt JSON and are forwarded to Remotion code generation.

Save as `${RUN_DIR}/motion_prompts/section_{id}.json`:
```json
{
  "section_id": 3,
  "script_text": "Here's how the workflow works",
  "duration_seconds": 6.8,
  "layout": "FULL",
  "width": 1080,
  "height": 1920,
  "animation_brief": "...",
  "output_filename": "section_3.mp4",
  "aroll_clip_path": null,
  "words": [
    {"word": "Here's", "start_seconds": 0.0, "end_seconds": 0.32, "start_frame": 0.0, "end_frame": 9.6},
    {"word": "how", "start_seconds": 0.32, "end_seconds": 0.58, "start_frame": 9.6, "end_frame": 17.4}
  ]
}
```

The animation brief should reference word timing for sync — e.g. "reveal each word as it's spoken", "trigger emphasis on frame X when keyword appears".

For A-ROLL-ENHANCED, set `aroll_clip_path` to the static file name (e.g. `"aroll_section_3.mp4"`) and make the brief aware that the speaker clip is available. The brief should describe how to use the speaker footage — resize, reposition, overlay text, effects, etc.

Show the user a summary of all briefs before proceeding.

### 5. Generate Remotion code and render

**First**, load the `remotion-best-practices` skill via ToolSearch (`"select:remotion-best-practices"`).

For each section:

**a) Write the TSX component**

Generate a self-contained Remotion React component:
- Named export: `export const Section{id}: React.FC = () => { ... }`
- Only imports from `remotion` and `react`
- Uses `useCurrentFrame()`, `useVideoConfig()`, `interpolate()`, `spring()`, `AbsoluteFill`, `Sequence` etc.

**For A-ROLL-ENHANCED sections**: the component uses `<Video>` from `@remotion/media` with `staticFile("aroll_section_{id}.mp4")` to include the speaker footage. The component controls everything — how the speaker appears, effects, text, layout. The Remotion output IS the final clip.

**For MOTION-GRAPHIC sections**: standalone animation, no video input.

**Word-level timestamps**: The motion prompt JSON includes a `words` array with section-relative timing. When generating the TSX component, embed this data directly as a const array inside the component so animations can sync to speech. The word timestamps are passed to the LLM as a JSON block in the Remotion code generation prompt — the LLM should use `interpolate()` or frame comparisons against these values to time reveals, kinetic typography, etc.

Save to `${REPO_DIR}/remotion_project/src/components/Section{id}.tsx`

**b) Register in Root.tsx**

Read `${REPO_DIR}/remotion_project/src/Root.template.tsx` and replace placeholders:
- `// {{IMPORTS}}` → `import { Section{id} } from "./components/Section{id}";`
- `{/* {{COMPOSITIONS}} */}` → a `<Composition>` entry with id, component, durationInFrames, fps=30, width, height

Write to `${REPO_DIR}/remotion_project/src/Root.tsx`

**c) Render**

```bash
cd "${REPO_DIR}/remotion_project" && npx remotion render src/index.ts "Section{id}" "${RUN_DIR}/motion_renders/section_{id}.mp4" --codec h264
```

**d) Archive and clean up**

Copy the working TSX to `${RUN_DIR}/remotion_components/Section{id}.tsx`. Delete the component file, Root.tsx, and any `aroll_section_*.mp4` from `public/`.

### 6. Update state

**edl.json** — for each rendered section, set `asset_file` to the absolute path of its mp4.

**workflow_state.json** — update:
- `steps.generate_motion_prompts` → `"completed"`
- `steps.generate_motion_code` → `"completed"`
- `steps.render_motion` → `"completed"`
- `current_step` → `"render_motion"`
- `motion_graphics` → array of `{"section_id", "prompt_path", "component_path", "render_path"}` per section

### 7. Report to the user

Tell them what was generated, file paths, and that the pipeline can continue with step 9 (assemble).
