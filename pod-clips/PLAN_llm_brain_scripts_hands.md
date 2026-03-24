# Plan: pod-clips — LLM as Brain, Scripts as Hands

## Context
The pod-clips skill currently burns ~135K tokens per run because Claude manually handles three steps that are purely mechanical: applying QA decisions (Step 5b), presenting clips (Step 6), and generating per-clip transcript files (Step 7b). The worst offender is Step 5b — it re-reads the full 40K-token transcript a third time just to do timestamp updates and line extraction (pure string operations). The fix: add two Python scripts for the mechanical work, enforce structured output formats from Claude's remaining steps, and update SKILL.md to wire it all together.

**LLM boundary after this change:**
- Claude ONLY: identify viral moments (Step 4) + QA clip boundaries (Step 5 sub-agent)
- Scripts handle everything else

**Token savings: ~44K–49K fewer tokens per run (~33–35% reduction)**

---

## Files to Change

| File | Action |
|---|---|
| `SKILL.md` | Update Step 4 output format, Step 5 QA prompt, replace Steps 5b/6/6b/7b |
| `scripts/apply_qa.py` | **Create new** — applies QA decisions, re-extracts transcript excerpts |
| `scripts/generate_clip_transcripts.py` | **Create new** — writes per-clip .txt files |

Reference files (`clip_cutting_rules.md`, `viral_clip_criteria.md`) — **no changes**.

---

## 1. Structured Output Format: `clip_suggestions.md`

Claude (Step 4) must output this format exactly — machine-parsed by `apply_qa.py`:

```
<!-- CLIP_SUGGESTIONS_V1 -->

===CLIP_START===
ID: CLIP_1
TITLE: "Why Stealth Mode Companies Always Lose"
START: 14:22
END: 16:45
DURATION_SEC: 143
HOOK: First line of the clip
PUNCHLINE: Last line of the clip
WHY_IT_WORKS: One sentence reasoning
STORY_ARC: HOOK: ... → SETUP: ... → PAYOFF: ...
TRANSCRIPT_EXCERPT:
[14:22-14:25] text line one
[14:25-14:31] text line two
===CLIP_END===
```

- All fields on their own line: `KEY: value`
- No markdown bold/bullets for machine-readable fields
- `TRANSCRIPT_EXCERPT:` is a sentinel — all `[MM:SS-MM:SS]` lines until `===CLIP_END===` are the excerpt

---

## 2. Structured Output Format: `qa_report.md`

Sub-agent (Step 5) must output this format exactly — machine-parsed by `apply_qa.py`:

```
<!-- QA_REPORT_V1 -->

===QA_START===
ID: CLIP_1
VERDICT: PASS
NOTES: Optional free text
===QA_END===

===QA_START===
ID: CLIP_2
VERDICT: ADJUST
NEW_START: 13:55
NEW_END: 17:02
REASONING: Optional free text
===QA_END===

===QA_START===
ID: CLIP_3
VERDICT: DROP
REASONING: Optional free text
===QA_END===
```

- `ID` and `VERDICT` are mandatory in every block
- For `ADJUST`: `NEW_START` and `NEW_END` are mandatory (MM:SS format)
- `NOTES` / `REASONING` are free text, ignored by script

---

## 3. New Script: `apply_qa.py`

**Invocation (Step 5b in new SKILL.md):**
```bash
python3 ~/.claude/skills/pod-clips/scripts/apply_qa.py \
    "clip_cut/<slug>/analysis/clip_suggestions.md" \
    "clip_cut/<slug>/analysis/qa_report.md" \
    "clip_cut/<slug>/transcript/full_transcript.txt"
```

**Logic:**
1. Parse all `===CLIP_START===` blocks from `clip_suggestions.md` → dict keyed by `ID`
2. Parse all `===QA_START===` blocks from `qa_report.md` → dict keyed by `ID`
3. Load `full_transcript.txt` → list of `(start_sec, end_sec, raw_line)` tuples (parse `[MM:SS-MM:SS]` regex)
4. For each clip in order:
   - `PASS` → copy block unchanged
   - `DROP` → skip entirely, log `[DROP] CLIP_N: <title>`
   - `ADJUST` → update `START`, `END`, `DURATION_SEC`, re-extract `TRANSCRIPT_EXCERPT` lines where `start_sec >= new_start AND start_sec < new_end`. Keep `TITLE`, `WHY_IT_WORKS`, `STORY_ARC` unchanged. Update `HOOK` from first kept line, `PUNCHLINE` from last.
5. Renumber remaining clips sequentially (CLIP_1, CLIP_2, ...)
6. Backup original as `clip_suggestions_pre_qa.md`, overwrite `clip_suggestions.md`
7. Print: `Applied QA: N passed, M adjusted, K dropped. Final: X clips.`

**Error conditions (exit non-zero):**
- QA references an ID not in clip_suggestions
- ADJUST block missing NEW_START or NEW_END
- NEW_START >= NEW_END

---

## 4. New Script: `generate_clip_transcripts.py`

**Invocation (Step 7b in new SKILL.md):**
```bash
python3 ~/.claude/skills/pod-clips/scripts/generate_clip_transcripts.py \
    "clip_cut/<slug>/analysis/clip_suggestions.md" \
    "clip_cut/<slug>/clips"
```

**Logic:**
1. Parse `clip_suggestions.md` for all clips: `ID`, `TITLE`, `START`, `END`, `DURATION_SEC`, `TRANSCRIPT_EXCERPT` lines
2. Read `video_metadata.txt` from `../../transcript/video_metadata.txt` relative to clip_suggestions for source URL
3. For each clip, derive filename slug (must match `cut_clips.sh`): lowercase title, strip non-alphanumeric, spaces→underscores, truncate 40 chars → `clip<N>_<slug>.txt`
4. Write to `<clips_dir>/clip<N>_<slug>.txt`:
```
# Clip: "Title"
# Source: https://youtube.com/watch?v=...
# Timestamps: 14:22 - 16:45 (original video)
# Duration: ~143s

[14:22-14:25] text...
...
```

**Extra mode:**
```bash
python3 generate_clip_transcripts.py clip_suggestions.md clips/ --print-names
```
Prints exact filenames (no extension) for each clip — used in Step 6b so cut_clips.sh gets matching names.

---

## 5. Updated SKILL.md Pipeline

### Step 4 changes
Add to output instructions:
> Output clip_suggestions.md in the structured V1 format (see CLIP_SUGGESTIONS_V1 header). All machine-readable fields use `KEY: value` on their own lines. No markdown formatting for these fields.

### Step 5 changes
Add to sub-agent prompt:
> Output qa_report.md in the structured V1 format (see QA_REPORT_V1 header). Every block needs ID and VERDICT. For ADJUST, NEW_START and NEW_END are mandatory in MM:SS format.

### Step 5b (REPLACE entirely)
```
## Step 5b: Apply QA Decisions

python3 ~/.claude/skills/pod-clips/scripts/apply_qa.py \
    "clip_cut/<slug>/analysis/clip_suggestions.md" \
    "clip_cut/<slug>/analysis/qa_report.md" \
    "clip_cut/<slug>/transcript/full_transcript.txt"

Verify output: "Applied QA: N passed, M adjusted, K dropped."
clip_suggestions.md is now the final source of truth.
```

### Step 6 (SIMPLIFY)
```
## Step 6: Present to User

Read clip_suggestions.md. For each CLIP block, show:
  CLIP_1: "Title" [14:22–16:45, ~143s]
  CLIP_2: "Title" [22:10–24:30, ~140s]

Ask: "Which clips to cut? (all / numbers / none)"
```

### Step 6b (NEW — before cutting)
```
## Step 6b: Get Exact Clip Names

python3 ~/.claude/skills/pod-clips/scripts/generate_clip_transcripts.py \
    "clip_cut/<slug>/analysis/clip_suggestions.md" \
    "clip_cut/<slug>/clips" --print-names

Use these exact names as CLIP_NAME in cut_clips.sh calls.
```

### Step 7b (REPLACE entirely)
```
## Step 7b: Generate Per-Clip Transcripts

python3 ~/.claude/skills/pod-clips/scripts/generate_clip_transcripts.py \
    "clip_cut/<slug>/analysis/clip_suggestions.md" \
    "clip_cut/<slug>/clips"

Verify: ls -lh clip_cut/<slug>/clips/
```

---

## Token Budget: Before vs After

| Step | Before | After |
|---|---|---|
| Step 4 Analyze | ~43K in, ~3K out | ~43K in, ~3K out (unchanged) |
| Step 5 QA sub-agent | ~45K in, ~1K out | ~45K in, ~0.5K out (tighter format) |
| Step 5b Apply QA | ~44K in (incl. 40K transcript re-read!) | **0 — script** |
| Step 6 Present | ~3K in | ~3K in (minimal, just read structured file) |
| Step 7b Transcripts | ~3K in, ~2K out | **0 — script** |
| **Total** | **~138K tokens** | **~91K tokens** |

**~47K tokens saved (~34% reduction) per run.**

---

## Verification

1. Run full pod-clips on a test YouTube URL
2. After Step 4: verify `clip_suggestions.md` parses correctly (`apply_qa.py` will error if format is wrong)
3. After Step 5: verify `qa_report.md` has `QA_REPORT_V1` header and proper ID/VERDICT fields
4. Run `apply_qa.py` — confirm it prints clip count summary, backup file exists, `clip_suggestions.md` is updated
5. Run `generate_clip_transcripts.py --print-names` — confirm names match what you'll pass to `cut_clips.sh`
6. After cutting, run `generate_clip_transcripts.py` — confirm `.txt` files appear alongside `.mp4` files
