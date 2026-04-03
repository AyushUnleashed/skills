---
name: asset-crawler
description: >
  Research a topic, find all relevant articles/blogs/sources online, crawl each source
  for images and video links, then bulk-download everything into an organized folder.
  Use this skill whenever the user wants to gather visual assets (images, videos, clips)
  for a topic — for video production, presentations, research, content creation, etc.
  Triggers on: "find assets for", "gather images and videos about", "crawl for media",
  "download all images/videos about", "research assets for", "find visuals for",
  or any request to collect media from multiple web sources about a topic.
---

# Asset Crawler

You research a topic across the web, extract every image and video link from relevant
sources, then bulk-download them into `asset-downloads/` in the user's working directory.

The workflow has three phases: **you do the research** (web search + page crawling),
**the bundled script does the downloading** (concurrent, handles YouTube/Twitter/direct
URLs automatically), and **you deduplicate contextually** (grouping assets by what they
actually depict, not just by URL). You write a file in the format the script reads —
that's the handoff between phases 1 and 2.

## Phase 1: Research & Extract

### Step 1 — Search broadly

Given the user's topic, run 3-5 WebSearch queries from different angles to maximize
coverage. Vary your queries:
- The topic verbatim
- Key technical terms + year
- Related project/org names
- "video" or "images" variants if relevant

Collect every unique URL that looks relevant. Deduplicate by content (different
subdomains of the same org hosting the same article = keep one).

### Step 2 — Write master_links.txt

Write all discovered links to `master_links.txt` in the working directory. Format:

```
# Master Links: "<topic>"
# Collected: <date>

## <CATEGORY NAME>
[R] https://example.com/article-1
[R] https://example.com/article-2
[X] https://example.com/duplicate  (duplicate of above)
```

Tags: `[R]` = relevant, `[X]` = filtered out (duplicate/irrelevant), `[?]` = unsure.
Only crawl `[R]` links in the next step.

### Step 3 — Crawl each source for assets

For every `[R]` link, use WebFetch to extract images and videos. Use this prompt
with WebFetch:

> Extract ALL image URLs and video URLs from this page. For each image, provide
> the full URL and its alt text or caption. For each video, provide the full URL
> and description. Look for: img tags, video tags, iframe embeds (YouTube etc),
> figure elements. Format as: IMAGE | full_url | alt_text_or_caption and
> VIDEO | full_url | description

Run WebFetch calls in parallel (batch 5-6 at a time) to go fast. Some pages will
403 or fail — that's fine, note them and move on.

### Step 4 — Write assets.txt

Consolidate all extracted assets into a single file called `assets.txt` in the
working directory. This is the file the downloader script reads.

**The format is strict** — one asset per line:

```
IMAGE | https://example.com/photo.jpg | Description of the image
VIDEO | https://youtu.be/abc123 | Description of the video
```

Rules:
- Line must start with `IMAGE` or `VIDEO`
- Fields separated by ` | ` (space-pipe-space)
- URL must be a real URL (not a placeholder like "(embedded, no URL)")
- Skip lines that don't have a real downloadable URL
- Deduplicate — same URL appearing from multiple sources = keep one entry
- Skip site logos, navigation icons, author avatars, and other non-content images
- Keep: article headers, diagrams, visualizations, photos, infographics, video embeds
- For YouTube embed URLs like `/embed/XYZ`, write the full URL — the script normalizes it
- Any other line format (comments, headers, blank lines) is ignored by the script

#### Light pre-download dedup

Don't try to aggressively filter images before downloading — you can't see them yet,
and filenames are unreliable (two files with similar names can have completely different
compositions). At this stage, only skip an image if:

- The **exact same URL** already appears (trivial dedup)
- The captions from two different sites are **word-for-word identical** and clearly
  describe the same stock photo (e.g., both say "Shutterstock image #12345")

Everything else — including images that *sound* similar — should be downloaded. The
real subject-level deduplication happens in Phase 3, after you have the actual files
on disk and can compare them properly.

## Phase 2: Download

The bundled downloader script handles everything from here. Run it via Bash:

```bash
python3 <skill-scripts-dir>/downloader.py \
  --input assets.txt \
  --output asset-downloads \
  --workers 15
```

Where `<skill-scripts-dir>` is the `scripts/` directory inside this skill's folder.

The script:
- Reads `assets.txt` (the file you wrote in Step 4)
- Classifies each URL: platform video (YouTube, Twitter, Vimeo, TikTok, etc.) → `yt-dlp`, everything else → `curl`
- Downloads all assets concurrently (async curl + thread pool for yt-dlp)
- Saves to `asset-downloads/images/`, `asset-downloads/videos/`, `asset-downloads/audio/`
- Filenames include a slug from the caption for easy identification
- Writes `asset-downloads/manifest.json` with status of every download

### Dry run first

Always do a dry run first so the user can see what will be downloaded:

```bash
python3 <skill-scripts-dir>/downloader.py \
  --input assets.txt \
  --output asset-downloads \
  --dry-run
```

Show the user the dry run output. Then run the actual download.

### Optional filters

```bash
# Only images
python3 ... --type images

# Only videos
python3 ... --type videos
```

## Phase 3: Contextual Deduplication

This is where the real deduplication happens. Phase 1 only removed exact URL duplicates
— by design, because you can't reliably judge visual similarity from filenames and
captions alone. Now you have the actual files on disk and can compare properly.

Run this **after** downloading. You now have files on disk (for size comparison) plus
all the caption and credit metadata you collected during crawling.

### Two kinds of duplicates to catch

**Kind 1: Same image, different URLs** — The literal same photograph re-hosted across
sites. Signals (in order of reliability):

1. **Source URL patterns** — Same filename fragment across domains is a strong match.
2. **Credit / attribution** — Same credit line on different sites = almost certainly
   the same image re-hosted.
3. **File size and dimensions** — Very similar file sizes with same aspect ratio at
   different resolutions strongly suggest the same source image.

**Kind 2: Different images, same visual subject** — This is the one that matters most
and is easy to miss. These are technically different files by different photographers,
but they depict the same thing and serve the same purpose. When multiple news outlets
cover the same story, they each pick a generic stock photo of the topic — and you end
up with several interchangeable images that a video editor or designer would never use
side by side.

Signals for Kind 2 (use these to form candidate groups, then verify by inspecting
the actual downloaded files):
1. **Captions / descriptions describe the same scene** — If multiple images' captions
   all boil down to the same visual concept (same product on same type of device,
   same person in same setting, same landmark from similar angle), group them as
   candidates. This is your starting signal.
2. **Same role in their source articles** — If multiple files were each the hero/header
   image for articles covering the same news story, they're likely interchangeable
   stock photos. News outlets almost always pick generic stock images as hero art.
3. **Actual file inspection** — Once you have a candidate group, look at the downloaded
   files. Compare file sizes and dimensions. Very similar aspect ratios with similar
   content descriptions = strong match. But be careful: similar filenames do NOT mean
   similar images — two files with related names could have completely different
   compositions. The files themselves are the ground truth, not the names.

### How to decide what to keep

For each group of redundant assets (whether Kind 1 or Kind 2):

1. **Keep the one with the most visual information** — highest resolution, best
   quality, most detail visible.
2. **If two images in a group have meaningfully different compositions**, keep both
   (e.g., one is a close-up of the UI, the other is a wide shot of someone using
   the device). But "slightly different stock photo angle on the same concept" does
   NOT count as meaningfully different.
3. **Prioritize original/editorial content over stock photos** — a screenshot, diagram,
   or photo someone created specifically for their article is more valuable than a
   generic stock image of the same subject, even if the stock photo is higher resolution.

### Avoiding false positives

The main risk is grouping assets that share a subject but serve different visual
purposes. Before removing something, check:

- Does it show a **different UI state or screen** than the others? (e.g., settings
  page vs confirmation dialog vs inbox view — these are all different, keep them)
- Is it a **different medium**? (photo vs illustration vs diagram vs screenshot —
  keep one of each type)
- Does it show the subject in a **meaningfully different context**? (desktop vs
  mobile, or dark mode vs light mode — usually worth keeping both)

The simple test: if you'd struggle to explain to a video editor or designer why they
need both images, they're duplicates. When genuinely uncertain, keep both — but
"different photographer" alone is NOT a reason to keep both if the visual content
is interchangeable.

### What to do with duplicates

For each duplicate group:
1. **Keep** the highest-quality version (largest resolution / file size)
2. **Move** lower-quality duplicates to `asset-downloads/removed_duplicates/` — do
   not delete them outright, so the user can review and recover if needed

### Presenting the results

Show the user a table of duplicate groups before acting. For each group list:
- The filenames, sources, dimensions, and file sizes
- Which file you recommend keeping and why
- Your confidence level (HIGH / MEDIUM / LOW)

Let the user confirm or override before moving files. After dedup, report the final
asset count and space saved.

## What to tell the user

After everything completes, summarize:
- How many sources were found and crawled
- How many unique images and videos were extracted
- Download results (succeeded / failed / skipped)
- Deduplication results (groups found, files removed, space saved)
- Note any pages that couldn't be crawled (403s, etc.)

## Dependencies

- `curl` — almost always available
- `yt-dlp` — needed only if there are YouTube/Twitter/etc. platform videos. If not
  installed, those downloads are skipped with a clear message. Install: `pip install yt-dlp`
