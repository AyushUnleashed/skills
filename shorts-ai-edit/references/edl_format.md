# EDL Format Reference

The Edit Decision List (EDL) is a markdown file that maps every second of the video to a visual treatment. The build script parses this file directly, so field names and formatting must be exact.

## Section Template

```markdown
## Section N
- **Time**: MM:SS – MM:SS
- **Script**: "The spoken words in this section."
- **Edit Type**: A-ROLL | ASSET | MOTION-GRAPHIC
- **Asset File**: `filename.ext` | [to be generated] | (omit for A-ROLL)
- **Layout**: FULL | SPLIT | (omit for A-ROLL)
- **Notes**: Optional notes about why this choice was made.
```

## Edit Types

| Type | When to use | Asset File required? | Layout required? |
|------|------------|---------------------|-----------------|
| `A-ROLL` | Just the speaker | No | No |
| `ASSET` | Cut to a provided image or video | Yes — real filename | Yes |
| `MOTION-GRAPHIC` | Generated Remotion animation | `[to be generated]` until Phase 4 | Yes |

## Layouts

| Layout | What it does |
|--------|-------------|
| `FULL` | Asset fills the entire 1080×1920 frame. Speaker audio continues. |
| `SPLIT` | Asset on top (1080×960), speaker on bottom (1080×960). Speaker audio continues. |

## Full Example EDL

```markdown
# Edit Decision List

## Section 1
- **Time**: 00:00 – 00:07
- **Script**: "Welcome to ReelsAI — the platform that makes video creation as easy as writing a text message."
- **Edit Type**: A-ROLL
- **Notes**: Opening hook. Keep it personal, face on camera.

## Section 2
- **Time**: 00:07 – 00:18
- **Script**: "Instead of hiring a whole production team, you get AI that scripts, films, and edits."
- **Edit Type**: ASSET
- **Asset File**: `team_vs_ai.jpg`
- **Layout**: SPLIT
- **Notes**: The graphic shows traditional team vs. solo founder — strong contrast with the script.

## Section 3
- **Time**: 00:18 – 00:30
- **Script**: "Here's how the workflow looks — script, film, edit, post."
- **Edit Type**: MOTION-GRAPHIC
- **Asset File**: [to be generated]
- **Layout**: FULL
- **Prompt**: "Animated step-by-step flow: Script → Film → Edit → Post. Each step pops onto screen with a satisfying bounce. Dark background, bright neon green accent color (#00FF88). Clean sans-serif labels. Duration: 12 seconds."
- **Duration**: 12s
- **Notes**: No asset covers this abstract workflow concept, so we animate it.

## Section 4
- **Time**: 00:30 – 00:38
- **Script**: "Your first video in minutes, not days."
- **Edit Type**: A-ROLL
- **Notes**: Closing CTA — end on the founder's face for authenticity.
```

## Common Mistakes to Avoid

- **Gaps or overlaps in timestamps**: Every second of the main video should be covered. If the transcript ends at 00:38, the last section should end at 00:38.
- **`[to be generated]` left in the final EDL**: Before running the build script, all motion graphic sections must have real file paths.
- **Missing layout for ASSET/MOTION-GRAPHIC**: The script defaults to FULL if Layout is missing, but it's better to be explicit.
- **Sections shorter than 2 seconds**: Too brief to be meaningful. Merge with adjacent section.
