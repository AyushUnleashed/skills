---
name: creator-style-analyzer
description: Analyze any YouTube creator's short-form video style and produce a copywriter brief. Use this skill whenever the user wants to analyze a creator's style, study how a YouTuber writes scripts, reverse-engineer a creator's short-form content strategy, create a writing guide based on someone's videos, or build a style brief from YouTube Shorts/Reels. Also triggers when the user provides a YouTube channel URL and wants to understand their content patterns. Works for any creator — not limited to specific channels.
---

# Creator Style Analyzer

Analyze any YouTube creator's short-form videos to produce a detailed copywriter brief that captures **what works structurally** — not a clone of their voice.

## Prerequisites

- `yt-dlp` installed and accessible in PATH
- `agent-browser` skill available (for scraping YouTube)
- Python 3 available

## Workflow Overview

```
Step 1: Get inputs (channel URL, video count, time range)
Step 2: Scrape Shorts from YouTube channel via agent-browser
Step 3: Download transcriptions via yt-dlp helper script
Step 4: Analyze all transcriptions for style mechanics
Step 5: Produce copywriter brief
```

---

## Step 1: Get Inputs

Ask the user for:

1. **YouTube channel URL** (required) — e.g., `https://www.youtube.com/@ChannelName`
2. **How many videos?** (default: 50) — top N most popular shorts
3. **How recent?** (default: 1 year) — only consider videos from the last N months/years

If the user already provided the channel URL in their message, don't re-ask. Just confirm the defaults:
> "I'll grab the top 50 most popular Shorts from the last year. Want to adjust the count or time range?"

Derive a short `creator_slug` from the channel name (e.g., `@VarunMayya` → `varun_mayya`). This is used for output filenames.

---

## Step 2: Scrape Shorts Links

Use `agent-browser` to collect video links from the creator's Shorts tab.

### 2a. Open the Shorts tab

```bash
agent-browser open "https://www.youtube.com/@{ChannelName}/shorts" && agent-browser wait --load networkidle && agent-browser wait 3000
```

### 2b. Scroll to load enough videos

YouTube lazy-loads Shorts. Scroll aggressively to load at least 2x the target count (to have room for filtering):

```bash
agent-browser scroll down 5000 && agent-browser wait 2000
```

Repeat scrolling 4-8 times depending on target count. After scrolling, verify the count with:

```javascript
document.querySelectorAll("ytd-rich-item-renderer").length
```

If not enough, scroll more.

### 2c. Extract video data

The Shorts tab doesn't expose titles/views the same way as the Videos tab. Use `innerText` extraction:

```javascript
Array.from(document.querySelectorAll("ytd-rich-item-renderer")).map(el => {
    const link = el.querySelector("a[href*='/shorts/']");
    const href = link ? link.getAttribute("href") : null;
    const text = el.innerText.trim();
    const lines = text.split("\n").filter(l => l.trim());
    const title = lines[0] || null;
    const views = lines[1] || null;
    return { title, views, href };
})
```

### 2d. Process and save

Write a Python snippet (inline or via bash) that:
1. Parses view counts to numeric values (handle "1.2M", "456K", etc.)
2. Sorts by views descending
3. Takes the top N
4. Saves to `{creator_slug}_links.txt` in the working directory

**Output format** (one entry per video):
```
CREATOR NAME - TOP {N} SHORTS
Sorted by views, descending.
===================================================================

#01. Video Title Here | 1.2M views
https://www.youtube.com/shorts/XXXXXXXXXXX

#02. Another Video Title | 890K views
https://www.youtube.com/shorts/YYYYYYYYYYY
```

Close the browser when done:
```bash
agent-browser close
```

---

## Step 3: Download Transcriptions

Run the bundled helper script:

```bash
python {skill_path}/scripts/fetch_transcripts.py {creator_slug}_links.txt {creator_slug}_transcriptions.txt
```

Where `{skill_path}` is the path to this skill directory: `/home/ayush/.claude/skills/creator-style-analyzer`

This script:
- Reads the links file
- Downloads auto-generated English subtitles via yt-dlp
- Parses SRT to clean text (removes timestamps, deduplicates auto-sub repetitions)
- Compiles everything into one file

**If yt-dlp fails for some videos**, that's normal — some Shorts have no auto-captions. The script handles this gracefully. As long as 60%+ succeed, proceed with analysis.

Tell the user the progress: "Downloaded transcriptions for X out of Y videos. Starting analysis..."

---

## Step 4: Analyze Style

Read the full transcriptions file. Then read the analysis guide at `references/analysis-guide.md` (relative to this skill's directory) and follow its approach.

Read through ALL transcriptions before writing anything. Don't go in with a fixed checklist — let the patterns emerge from the content. Every creator is different. What makes one creator's content work might be completely different from another.

Your job is to discover what's actually distinctive and effective about THIS creator's scripts, and explain the underlying mechanics — not catalog their specific phrases or verbal tics.

---

## Step 5: Produce the Brief

Write the final brief to `{creator_slug}_style_brief.md` in the working directory.

Organize the brief by whatever dimensions actually matter for this specific creator. Don't force a standard template — if the creator's biggest strength is something unexpected, that should be the first section, not buried under a generic "Hook Mechanics" header.

Each section should:
- **Lead with the principle** — what the mechanic is and why it works
- **Illustrate with examples** — 2-3 concrete examples from the transcriptions
- **End with guidance** — what the copywriter should do (and avoid)

Close with a short checklist (8-12 items) a copywriter can use to validate a draft.

The brief should feel like it was written by someone who deeply understands this specific creator — not a generic short-form video guide with a name swapped in.

### Deliverables Summary

Tell the user what was created:
1. `{creator_slug}_links.txt` — Video links with titles and view counts
2. `{creator_slug}_transcriptions.txt` — Full transcriptions
3. `{creator_slug}_style_brief.md` — The copywriter brief

All files are saved in the current working directory.
