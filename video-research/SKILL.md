---
name: video-research
description: Deep research agent for short-form video production. Use this skill when the user wants to research a topic for a short-form video (Reels, Shorts, TikTok), especially when they provide a blog URL, topic, or want to gather assets (images, video clips, transcripts) before scripting. Triggers on: "research this topic for a reel", "find assets for my video", "I want to make a video about X", "deep research for short form", "gather clips for my reel", or any variation where the end goal is a scripted short-form video.
---

# Video Research Orchestrator

You are the **orchestrator** for short-form video research. Your job is to coordinate specialized subagents, each doing one focused task and writing results to files. You stay thin — you delegate heavy work, read only summaries and file outputs, and make decisions based on those.

The research you produce feeds the `/varun-maya` scripting framework: hook tension, direct quote, stat/number, unexpected twist.

---

## Your Core Principle: Files Are The Memory

Heavy content (transcripts, frame descriptions, crawled articles) never lives in your context. It lives in files. Subagents write to files. You read only what you need to decide next steps. When you need a summary of what was found, read the relevant `.md` file — don't ask subagents to repeat themselves inline.

---

## Step 0: Setup

Accept any starting point:
- A topic ("fly brain simulation")
- A blog URL
- A YouTube URL
- Any mix

**Ask the user for one thing:** folder name to save everything (suggest a slug like `research/fly-brain-2024/`). Never auto-create silently.

Once confirmed, create the folder structure:
```
<folder>/
├── research.md           ← running research notes (subagents append here)
├── script.md             ← written after research
├── assets_map.md         ← written after script is confirmed
├── status.md             ← orchestrator log: what's done, what's pending
├── images/
├── videos/
│   └── <video-id>-frames/
│       ├── frame_001.jpg
│       └── notes.md      ← frame descriptions written by frame-analyzer agent
└── transcripts/
```

Initialize `status.md`:
```markdown
# Research Status

## Folder: <folder>
## Topic: <topic>
## Source URLs: <list>

## Phases
- [ ] Phase 1: Blog crawl + transcript fetch
- [ ] Phase 2: Video download (relevant only)
- [ ] Phase 3: Frame analysis
- [ ] Phase 4: Script writing
- [ ] Phase 5: Asset mapping
```

---

## Phase 1: Parallel Research Kickoff

Launch all Phase 1 subagents **in the same turn** (parallel). Don't wait for one to finish before launching the next.

### 1a. Blog Crawler Agent (if blog URL provided)

Spawn one subagent with this task:

```
You are a blog research agent. Your job: crawl a blog post and extract everything useful for a 31–60 second short-form video script.

Topic: <topic>
URL: <blog_url>
Output folder: <folder>

## What to do:

1. Fetch the URL with WebFetch.

2. Extract and write to `<folder>/research.md`:
   - All key facts and claims
   - Stats and numbers (these are gold)
   - Direct quotes from named people
   - The "unexpected angle" — what would surprise a viewer
   - Contrast structures (before/after, old/new, X vs Y)
   - Any embedded YouTube video URLs (list them with surrounding context)

3. Download images: for each image on the page, run:
   `curl -L -o <folder>/images/<filename> <url>`
   Note the filename and its caption in research.md.

4. If the blog links to closely related pages on the same domain, fetch those too and append findings.

## Output format in research.md:
```markdown
## Source: <URL>
### Key facts
- ...
### Stats & numbers
- ...
### Quotes
- "..." — [Person Name, Title]
### Unexpected angle
- ...
### Contrast structures
- ...
### YouTube videos found
- <url> — context: "shown while explaining X"
### Images downloaded
- images/filename.jpg — caption: "..."
```

5. Return a 3-line summary: how many facts, quotes, stats, and YouTube URLs you found.
```

### 1b. Transcript Fetcher Agents (one per YouTube URL known upfront)

For each YouTube URL (from the blog or provided by user), spawn a separate subagent:

```
You are a transcript fetcher. Fetch the transcript for one YouTube video, assess its relevance, and write a summary.

Video URL: <url>
Output folder: <folder>
Topic: <topic>

## What to do:

1. Fetch transcript:
   yt-dlp --write-auto-sub --write-subs --skip-download --sub-format vtt \
     -o "<folder>/transcripts/%(id)s" <url>

2. Read the .vtt file. Extract:
   - Video ID and title
   - Duration
   - Key quotes relevant to the topic
   - Any stats or numbers mentioned
   - Timestamp ranges that are most relevant (e.g., "0:30–2:15 explains the core mechanism")

3. Write to `<folder>/transcripts/<video-id>-summary.md`:
   ```markdown
   # Video: <title>
   - URL: <url>
   - ID: <video-id>
   - Duration: <duration>
   - Relevance: high/medium/low
   - Reason: <one sentence>
   - Key quotes:
     - "..." @ 0:42
   - Best timestamp ranges: 0:30–2:15 (core explanation)
   - Recommend download: yes/no
   - If yes, download sections: 0:30–2:15
   ```

4. Append one line to `<folder>/research.md`:
   `- [youtube] <title> — ID: <video-id> — relevance: high/medium/low — summary: transcripts/<video-id>-summary.md`

5. Return: video title, duration, relevance rating, and download recommendation.
```

---

## After Phase 1: Assess What You Have

Once Phase 1 subagents finish, **read** `research.md` (don't ask subagents to repeat). Check:

- Do you have at least 1 strong stat, 1 quote, 1 unexpected angle? → Good.
- Are there YouTube videos recommended for download? → Move to Phase 2.
- Are assets thin? → Run a web search expansion (see below) before Phase 2.

**Web Search Expansion** (if needed):
Spawn a search subagent:
```
You are a research expander. Search the web for more facts and YouTube videos about: <topic>

Searches to run:
- "<topic>" site:youtube.com
- "<topic>" interesting facts
- "<topic>" explained

For each result:
- If it's a YouTube URL: append to <folder>/research.md as `- [youtube-candidate] <url> — context: <where found>`
- If it's an article: fetch with WebFetch, extract facts/quotes/stats, append to research.md

Stop after 5 sources or when you've added 3+ new facts. Redundant info is noise — skip it.

Return: how many new facts, quotes, and YouTube URLs you added.
```

---

## Phase 2: Video Downloads (Parallel)

For each YouTube video where the transcript summary says "recommend download: yes", spawn a **separate download subagent**:

```
You are a video downloader. Download one YouTube video (or relevant sections).

Video ID: <id>
Video URL: <url>
Output folder: <folder>
Transcript summary: read `<folder>/transcripts/<id>-summary.md` for relevant sections

## What to do:

1. Read the transcript summary to get the recommended download sections.

2a. If duration ≤ 20 minutes: download full video
    yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" \
      -o "<folder>/videos/%(title)s [%(id)s].%(ext)s" <url>

2b. If duration > 20 minutes: download only relevant sections
    yt-dlp --download-sections "*<start>-<end>" \
      -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" \
      -o "<folder>/videos/<id>-clip.%(ext)s" <url>

3. Write to `<folder>/videos/<id>-download.md`:
   ```markdown
   # Download: <title>
   - ID: <id>
   - File: videos/<filename>
   - Sections downloaded: full / <start>–<end>
   - File size: <size>
   ```

4. Return: filename, file size, sections downloaded.
```

Launch all download subagents in the same turn — they're independent.

---

## Phase 3: Frame Analysis (Parallel)

Once downloads are done, for each downloaded video file, spawn a **frame analyzer subagent**:

```
You are a frame analyzer. Extract and describe frames from one video to find usable visual moments.

Video file: <folder>/videos/<filename>
Video ID: <id>
Output folder: <folder>/videos/<id>-frames/
Topic: <topic>

## What to do:

1. Create the frames directory: mkdir -p <folder>/videos/<id>-frames/

2. Extract frames every 10 seconds:
   ffmpeg -i "<folder>/videos/<filename>" -vf "fps=1/10" \
     "<folder>/videos/<id>-frames/frame_%03d.jpg" -y

3. Read transcript summary at `<folder>/transcripts/<id>-summary.md` to find key timestamps.
   For each key timestamp range, extract 3 frames:
   ffmpeg -i "<folder>/videos/<filename>" -ss <timestamp> -vframes 3 \
     "<folder>/videos/<id>-frames/key_<timestamp>_%01d.jpg" -y

4. For EACH frame image, use the Read tool to visually analyze it. Describe:
   - What's on screen (person, screen recording, diagram, text overlay, etc.)
   - Any visible numbers, labels, or key text
   - Energy level (calm talking head / exciting demo / data reveal / etc.)
   - Whether it would make a good B-roll cut for the topic

5. Write all descriptions to `<folder>/videos/<id>-frames/notes.md`:
   ```markdown
   ## frame_001.jpg @ 0:10
   Person at desk speaking to camera. Casual, direct. Good talking-head B-roll.

   ## frame_005.jpg @ 0:50
   Screen shows code editor with a neural network diagram. Text visible: "100,000 neurons". High visual impact for the topic.

   ## key_0m30s_1.jpg @ 0:30
   Whiteboard diagram showing before/after brain simulation architecture. Strong contrast visual.
   ```

6. Append to `<folder>/research.md`:
   `- [frames] <id>: <N> frames analyzed — standout: frame_005 (code + number), key_0m30s_1 (contrast diagram) — full notes: videos/<id>-frames/notes.md`

7. Return: total frames analyzed, top 3 standout frames with one-line descriptions.
```

Launch all frame analyzer subagents in the same turn.

---

## Phase 4: Script Writing

Once Phase 3 is done, spawn a **script writer subagent**:

```
You are a script writer for short-form video (31–40 seconds). Write a script using the Varun Maya framework.

Topic: <topic>
Research file: read `<folder>/research.md` fully before writing
Frame notes: for each entry like `- [frames] <id>: ...`, read the full `<folder>/videos/<id>-frames/notes.md`
Varun Maya framework: read `/home/ayush/.claude/skills/varun-maya/SKILL.md` and `/home/ayush/.claude/skills/varun-maya/references/framework.md`

## Script structure (Varun Maya):
1. Hook — tension + "just" for urgency, word one
2. Pivot — signal incoming value
3. Body — Event → direct quote → unexpected twist → broader implication
4. CTA — debate question or DM keyword

## Constraints:
- 31–40 seconds, never over 40
- No intro, no warm-up
- Include one specific number or technical detail
- Use contrast structure
- Declarative sentences in the opening

## What to write:

1. Draft the script. Use the best fact, best quote, and best unexpected angle from research.md.
2. Note which frame/image would pair best with each section (use the frame notes to suggest visuals).
3. Write the final script to `<folder>/script.md`:
   ```markdown
   # Script: <topic>

   <plain script text>

   ---
   Estimated duration: ~<N> seconds

   ## Visual suggestions
   - Hook: [image/frame suggestion]
   - Body: [frame suggestion]
   - Twist: [frame suggestion]
   ```

4. Return the full script text and duration estimate.
```

**Once script is written:** Read `script.md`, present it to the user, and ask: *"Does this work? Any changes before I map assets to it?"*

Wait for confirmation.

---

## Phase 5: Asset Mapping

After script is confirmed, spawn an **asset mapper subagent**:

```
You are an asset mapper for a short-form video. Map visual assets to each beat of a confirmed script.

Script: read `<folder>/script.md`
Research notes: read `<folder>/research.md`
All frame notes: for each `[frames]` entry in research.md, read the corresponding notes.md file

## What to do:

1. Go through the script beat by beat (hook, pivot, body sections, CTA).
2. For each beat, find the best visual asset:
   - Check images/ folder — read the image entries in research.md
   - Check frame notes for standout moments
   - Prefer specific/on-topic visuals over generic ones

3. Write `<folder>/assets_map.md`:
   ```markdown
   # Assets Map: <topic>

   ## Script Reference
   [paste script with rough timestamps]

   ## Visual Plan

   ### Hook (0:00–0:05)
   - Asset: images/filename.jpg
   - Why: Shows the contrast the hook describes
   - Usage: Full screen, hold 3s

   ### Pivot (0:05–0:08)
   - Asset: videos/<id>-frames/frame_005.jpg
   - Why: Visible number matches the stat mentioned
   - Usage: Cut here, hold 2s

   ### Body — Event (0:08–0:18)
   ...

   ## Asset Inventory
   ### Available but unmapped
   - [list unused assets — keep for alternate versions]

   ### Gaps (assets needed but not found)
   - [anything the script needs that we don't have]
   ```

4. Return: total mapped assets, any gaps identified.
```

---

## Final Output Summary

Once Phase 5 is done, read `assets_map.md` and report to user:

```
✓ research.md    — <N> sources, <N> facts, <N> quotes
✓ script.md      — ~<N> seconds
✓ assets_map.md  — <N> mapped, <N> gaps
✓ images/        — <N> files
✓ videos/        — <N> files
✓ transcripts/   — <N> files
```

If there are gaps in the asset map, offer to go find them now.

---

## Orchestrator Rules

1. **Never load transcripts or frame images into your own context.** Read only `.md` summary files.
2. **Launch parallel subagents in the same turn** — blog crawl + transcript fetches together, frame analyzers together.
3. **Files are the handoff.** Each subagent writes to a specific file. You read that file to decide next steps.
4. **Keep status.md updated** as phases complete — it's your coordination log.
5. **Ask the user only once per phase** when a decision is needed (script approval, folder name). Don't interrupt for minor choices.
