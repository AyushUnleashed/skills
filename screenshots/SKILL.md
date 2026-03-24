---
name: screenshots
description: |
  Capture marketing-quality, retina-resolution screenshots of websites and web apps — section by section, not as full-page dumps. Use this skill whenever the user wants to screenshot their app or website for Product Hunt, social media, landing pages, or documentation. Key behaviors: explores the site first to understand its structure, then captures only the exact section requested (features section, pricing table, hero, etc.) without over-capturing unrelated areas or under-capturing by cutting elements in half. Every screenshot goes through a vision-based quality check — if it's off, the viewport adjusts and it retakes automatically. Always trigger this skill for: "take screenshots of my app", "screenshot my website", "generate marketing screenshots", "capture my UI for Product Hunt", "screenshot the features section", or any request for polished app/site images.
---

# Screenshots Skill

Capture precise, retina-quality (2x HiDPI) screenshots of web pages — targeting specific sections, not whole pages. Every capture is verified by vision analysis and adjusted until it shows exactly the right content.

## Two tools at your disposal

**1. `agent-browser`** — for exploring the site, navigating pages, reading DOM structure, and understanding what sections exist.

**2. `scripts/capture.js`** — for the actual HiDPI screenshots. This bundled Playwright Node.js script captures at `deviceScaleFactor: 2` (true retina). **Always use it for final captures.** It self-bootstraps playwright if not already installed.

```bash
# Find the script path first:
CAPTURE=$(find ~/.claude/skills -name "capture.js" | grep screenshots | head -1)

# Basic viewport capture
node $CAPTURE --url "https://example.com" --out "screenshots/01-hero.png" --width 1440 --height 800

# Capture a specific CSS selector (preferred — cleanest result)
node $CAPTURE --url "https://example.com" --out "screenshots/02-features.png" \
  --selector "#features" --padding 40

# Capture with scroll offset (fallback when no good selector)
node $CAPTURE --url "https://example.com" --out "screenshots/03-pricing.png" \
  --scroll-y 1800 --width 1440 --height 700

# Hide sticky nav/header before capturing (critical for section shots)
node $CAPTURE --url "https://example.com" --out "screenshots/02-features.png" \
  --selector ".features" --hide "nav,header,.navbar,.sticky" --padding 0
```

---

## Step 1: Gather requirements

Ask the user two questions upfront using `AskUserQuestion`:

**Q1 — Count** ("How many screenshots do you need?"):
- "3-5" → Quick set of key features
- "5-10" → Comprehensive feature coverage
- "10+" → Full marketing suite

**Q2 — Purpose** ("What will these screenshots be used for?"):
- "Product Hunt" → Hero shots and feature highlights
- "Social media" → Eye-catching feature demos
- "Landing page" → Marketing sections and benefits
- "Documentation" → UI reference and tutorials

Also ask whether the app requires login (and if so, get credentials).

---

## Step 2: Explore the site

Before planning any screenshots, understand what's actually there.

```bash
agent-browser open https://example.com && agent-browser wait --load networkidle
agent-browser snapshot -i
```

For each major page or section:
- Note section headings, IDs, and classes (these become your selectors)
- Note approximate scroll positions for sections without clean IDs
- Note interactive states that need to be set (logged-in views, expanded accordions, selected tabs)

Look specifically for:
- Navigation links → discover all pages
- Section IDs/classes on `<section>`, `<div>`, `<article>` elements
- Hero, features, pricing, testimonials, CTA, footer sections
- Any login-gated content worth capturing

---

## Step 3: Plan the screenshots

Based on your exploration, draft a list. Present it to the user with `AskUserQuestion`:

**"I found these sections in your site. Which would you like to screenshot?"**
- List the 3-4 most marketing-relevant sections you found
- Include "Let me specify exactly what I want" as an option

For each planned screenshot, note:
- The target URL
- The target section (selector preferred, scroll position as fallback)
- Any UI state needed (tab selected, login required, demo data visible)
- Intended filename

---

## Step 4: Capture with verify-and-adjust

This is the core loop. For every single screenshot:

### 4a. Take the initial capture

**Prefer selector-based capture** when the section has a clean ID or class:
```bash
python3 .../capture.py --url URL --selector "#features" --out screenshots/02-features.png --padding 40
```

**Fall back to scroll+viewport** when selectors are unreliable:
```bash
python3 .../capture.py --url URL --scroll-y 1200 --width 1440 --height 800 --out screenshots/02-features.png
```

**Initial height guidelines:**
- Hero sections: 600-700px
- Feature grids (2-3 rows): 800-900px
- Pricing tables: 700-850px
- Testimonials: 600-800px
- Full-section with title + content: 900-1000px

### 4b. Verify with vision

Read the screenshot file immediately after capture:
```
Read tool: screenshots/02-features.png
```

Then assess:
- **OVER-CAPTURED**: Header/nav/footer from another section bleeds in, or there's large empty space that's not part of the target section
- **UNDER-CAPTURED**: Cards/items are visibly cut at the bottom or sides, text is truncated, a bottom CTA row is half-visible
- **GOOD**: The section fills the frame cleanly — starts where the section starts, ends where it ends, with modest padding

### 4c. Adjust and retry if needed

| Problem | Fix |
|---|---|
| Sticky nav/header bleeds in | Add `--hide "nav,header,.navbar"` to remove it entirely (best fix) |
| Top nav bleeds into shot | Alternatively: increase `--scroll-y` by nav height (~60-80px) |
| Bottom content cut off | Increase `--height` by 150-200px |
| Too much empty space below | Decrease `--height` by 100-150px |
| Unrelated section visible | Reduce `--height` or increase scroll |
| Card/item cut in half at bottom | Increase `--height` until the last full card row fits |

**Allow up to 3 retakes per screenshot.** If still not right after 3 tries, capture the full section with `--selector` (even if slightly over-padded) and move on — note it in the summary.

> **Why this matters**: A screenshot showing half a card or a random footer strip looks amateurish and undermines the marketing goal. The whole point is precision.

---

## Step 5: File naming

Use descriptive, ordered, kebab-case names:

```
screenshots/
├── 01-hero.png
├── 02-features-overview.png
├── 03-pricing-table.png
├── 04-testimonials.png
├── 05-dashboard.png
```

Name based on what's actually *in* the image (check after capture), not just what you planned to capture.

---

## Step 6: Summarize results

After all captures:

```bash
ls -lh screenshots/*.png
# Get dimensions if imagemagick available:
identify screenshots/*.png 2>/dev/null | awk '{print $1, $3}' || file screenshots/*.png
```

Present:
```
Generated N marketing screenshots:

screenshots/
├── 01-hero.png (1.4 MB, 2880x1400 @ 2x)
├── 02-features-overview.png (890 KB, 2880x1800 @ 2x)
...

All screenshots verified at retina quality. Ready for [purpose].
```

If any required a note (e.g., "couldn't isolate the features grid from the nav — captured with 30px overlap"), mention it briefly.

---

## Authentication

If the app requires login:
1. Use agent-browser to log in first and save session state:
```bash
agent-browser open https://app.example.com/login && agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser fill @e1 "email@example.com"
agent-browser fill @e2 "password"
agent-browser click @e3
agent-browser wait --url "**/dashboard"
agent-browser state save /tmp/auth-state.json
```
2. Pass the auth state to the capture script via `--auth-state /tmp/auth-state.json`

---

## Tips

- **Wait for animations**: Use `--wait 2000` flag if the page has loading animations
- **Dark mode**: Add `--dark-mode` flag to capture dark variant
- **Demo data**: If the app shows empty states, seed some demo data first via the UI
- **Sticky headers**: Increase `--scroll-y` by the header height to avoid the nav overlapping your section
