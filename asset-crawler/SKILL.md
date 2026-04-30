---
name: asset-crawler
description: >
  Research a topic, find all relevant articles/blogs/sources online AND search X.com
  (Twitter) for relevant tweets, crawl each source for images and video links,
  screenshot notable tweets, then bulk-download everything into an organized folder.
  Use this skill whenever the user wants to gather visual assets (images, videos, clips,
  tweet screenshots) for a topic — for video production, presentations, research,
  content creation, etc. Triggers on: "find assets for", "gather images and videos about",
  "crawl for media", "download all images/videos about", "research assets for",
  "find visuals for", "find tweets about", "get screenshots of tweets",
  or any request to collect media from multiple web sources about a topic.
---

# Asset Crawler

You research a topic across the web, extract every image and video link from relevant
sources, then bulk-download them into `asset-downloads/` in the user's working directory.

The workflow has three phases: **you do the research** (web search + page crawling +
X.com tweet search & screenshots), **the bundled script does the downloading**
(concurrent, handles YouTube/Twitter/direct URLs automatically), and **you deduplicate
contextually** (grouping assets by what they actually depict, not just by URL). You
write a file in the format the script reads — that's the handoff between phases 1 and 2.

## Phase 0: Decompose the Brief

Before searching, figure out how many distinct visual concepts the user's input contains.

**Simple topic** (one line like "find assets about the Vision Pro"): This is already one
concept. Skip to Phase 1.

**Rich context** (a script, outline, multi-paragraph brief, or anything touching multiple
subjects): The user is describing many things that each need their own visuals. If you
only search the headline, you'll get 20 images of the same thing and nothing for the rest.

Read through the input and list out every distinct thing that would need its own visual
asset — not just the main subject, but people, places, products, data points, comparisons,
reactions, anything that a video editor would represent with a separate image or clip.

Write this as a simple checklist in `coverage_plan.md`. For each concept, note whether
you need a **video clip**, a **static image**, or **both** — this matters because video
clips are the most useful assets for video production and they're easy to miss if you
only search for images:

```
# Coverage Plan: "<topic>"

- [ ] Product hero shot (image)
- [ ] Dr. Smith (specific person mentioned in the brief) (image)
- [ ] Traditional surgery vs AR-assisted (the comparison) (video + image)
- [ ] Usage statistics / adoption data (image)
- [ ] Community reaction (video + image)
```

Every concept that involves action, process, or emotion should get a video clip, not
just a static image. Video editors need motion footage — screenshots alone don't cut it
for B-roll. This is your awareness of what needs covering. Use it during the search
phase, and after downloading, check which concepts still have gaps.

## Phase 1: Research & Extract

### Step 1 — Search broadly

Given the user's topic (and your coverage plan if you made one), run WebSearch queries
to maximize coverage across all the concepts you identified. Vary your queries:
- The topic verbatim
- Key technical terms + year
- Related project/org names
- "video" or "images" variants if relevant

Collect every unique URL that looks relevant. Deduplicate by content (different
subdomains of the same org hosting the same article = keep one).

### Step 1b — Search Mixkit for stock video B-roll

In addition to the broad web search above, explicitly search for **stock video clips**
to use as B-roll. This is a separate step because web searches and article crawling
mostly surface images (blog hero shots, screenshots, diagrams) — if you skip this step
you'll end up with lots of images and almost no video clips, which is a problem when
the user needs footage for video production.

Mixkit (mixkit.co) is the preferred source for stock B-roll because it serves direct
MP4 download URLs with no Cloudflare blocking — unlike Pexels and Pixabay which 403
on programmatic access. For each visual concept in your coverage plan that would benefit
from a video clip, search Mixkit:

```
site:mixkit.co/free-stock-video "<concept>"
```

Run 3-5 Mixkit searches covering the key concepts — e.g., "person recording video",
"frustrated at computer", "social media scrolling", "video editing timeline". Then
WebFetch each relevant Mixkit clip page to extract the direct `.mp4` download URL.
Look for URLs matching `https://assets.mixkit.co/.../*.mp4`.

Add every usable Mixkit clip to `assets.txt` as:
```
VIDEO | https://assets.mixkit.co/videos/preview/mixkit-...-1234-large-preview-720p.mp4 | Description
```

This step is specifically for stock footage gaps. You should still gather video assets
from all other sources too — YouTube embeds from articles, tweet videos, product demos,
etc. Mixkit just fills the "generic B-roll" need that blog crawling won't cover.

### Step 2 — Search X.com for relevant tweets

Search X.com (Twitter) for tweets related to the topic. This runs alongside your web
search — tweets often surface real-time reactions, product announcements, demos, and
media that blogs haven't picked up yet.

#### 2a. Find relevant tweets

Run 2-3 WebSearch queries scoped to X.com:
- `site:x.com "<topic>"`
- `site:x.com "<topic>" <key term or person>`
- `site:x.com "<topic>" <year>` (for recency)

From the search results, pick the **5-10 most relevant tweet URLs** — prioritize tweets
that have visual content (images, videos, infographics), high engagement, or come from
authoritative accounts. Skip reply threads and low-value retweets.

#### 2b. Screenshot each tweet

Use the `screenshots` skill to capture each relevant tweet. The goal is a clean capture
of the full tweet — author, text, any embedded media preview, and engagement metrics
(likes, retweets, replies).

Tips specific to X.com tweets:
- Target the `article` selector to isolate the tweet
- Use a narrow width (~650px) for a natural tweet-width frame
- X.com has a persistent login/signup banner at the bottom — crop it out
- Verify each screenshot and retake if overlays obscure the content

Save all tweet screenshots to `asset-downloads/tweets/` with descriptive names:
```
asset-downloads/tweets/
├── tweet-01-satya-announces-copilot.png
├── tweet-02-mkbhd-review-thread.png
├── tweet-03-official-launch-demo.png
```

#### 2c. Extract media URLs from tweets

While screenshotting, also note any images or videos embedded in the tweets. Add these
to `assets.txt` so the downloader can grab the actual media files:
- Tweet images: add as `IMAGE | https://pbs.twimg.com/media/... | Description`
- Tweet videos: add as `VIDEO | https://x.com/user/status/12345 | Description`
  (the downloader routes x.com URLs through yt-dlp automatically)

This way you get both the visual context (screenshot with engagement metrics) AND the
raw high-res media files.

### Step 3 — Write master_links.txt

Include X.com tweet URLs in the master links file alongside web sources. Tag them
with `[R]` like any other relevant link.

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

### Step 4 — Crawl each source for assets

For every `[R]` link, use WebFetch to extract images and videos. Use this prompt
with WebFetch:

> Extract ALL image URLs and video URLs from this page. For each image, provide
> the full URL and its alt text or caption. For each video, provide the full URL
> and description. Look for: img tags, video tags, iframe embeds (YouTube etc),
> figure elements. Format as: IMAGE | full_url | alt_text_or_caption and
> VIDEO | full_url | description

Run WebFetch calls in parallel (batch 5-6 at a time) to go fast. Some pages will
403 or fail — that's fine, note them and move on.

### Step 5 — Write assets.txt

Consolidate all extracted assets into a single file called `assets.txt` in the
working directory. This is the file the downloader script reads.

**Before writing this file, do a sanity check**: look at your coverage plan and make
sure you have VIDEO entries for every concept tagged as needing video. If you only
have IMAGE entries, you missed the Mixkit search step — go back and do it. A common
failure mode is gathering 40 images and 0 videos because the crawling phase only
finds `<img>` tags on blog posts. The Mixkit step (1b) exists specifically to prevent
this — it should produce the bulk of your video assets.

**The format is strict** — one asset per line:

```
IMAGE | https://example.com/photo.jpg | Description of the image
VIDEO | https://youtu.be/abc123 | Description of the video
VIDEO | https://assets.mixkit.co/videos/preview/mixkit-...-large-preview-720p.mp4 | Description
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
- Mixkit direct `.mp4` URLs go as `VIDEO | <url> | <description>` — the downloader
  handles them via curl (no yt-dlp needed)
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
- Reads `assets.txt` (the file you wrote in Step 5)
- Classifies each URL: platform video (YouTube, Twitter, Vimeo, TikTok, etc.) → `yt-dlp`, everything else → `curl`
- Downloads all assets concurrently (async curl + thread pool for yt-dlp)
- Saves to `asset-downloads/images/`, `asset-downloads/videos/`, `asset-downloads/audio/`
- Tweet screenshots are already in `asset-downloads/tweets/` from Step 2b (not re-downloaded)
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

## Coverage Check

If you built a coverage plan in Phase 0, revisit it now. Go through each concept on the
checklist and mark it covered or not based on what you actually downloaded. Update
`coverage_plan.md` with the results:

```
- [x] Product hero shot — 4 images downloaded
- [x] Dr. Smith — headshot from conference article
- [ ] Traditional surgery vs AR-assisted — nothing found
- [x] Usage statistics — 2 infographics
- [x] Community reaction — 3 tweet screenshots
```

Flag the gaps to the user. For uncovered concepts, mention what you tried and that
nothing usable turned up — the user can decide whether to find those manually or skip them.

## What to tell the user

After everything completes, summarize:
- How many sources were found and crawled
- How many tweets found and screenshotted
- How many unique images and videos were extracted
- Download results (succeeded / failed / skipped)
- Deduplication results (groups found, files removed, space saved)
- Coverage gaps (if a plan was made) — what concepts still need visuals
- Note any pages that couldn't be crawled (403s, etc.)

## Dependencies

- `curl` — almost always available
- `yt-dlp` — needed only if there are YouTube/Twitter/etc. platform videos. If not
  installed, those downloads are skipped with a clear message. Install: `pip install yt-dlp`
- `screenshots` skill — used for capturing tweet screenshots via Playwright/agent-browser

## Known limitations with stock sites

**Pexels and Pixabay** are behind Cloudflare anti-bot protection. `curl`, `yt-dlp`,
and `WebFetch` all get 403 errors on their pages and download URLs. Do not waste time
trying workarounds (impersonation flags, API keys, etc.) — it won't work from a CLI
environment. If you need assets from Pexels/Pixabay, list the URLs in a
`manual_downloads.txt` file and tell the user to grab them in a browser.

**Mixkit** (mixkit.co) serves direct MP4 files with no bot protection — always prefer
it for stock video B-roll. Their free library covers most common concepts (people,
tech, nature, business, emotions).
