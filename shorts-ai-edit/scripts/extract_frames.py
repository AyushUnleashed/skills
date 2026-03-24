#!/usr/bin/env python3
"""
extract_frames.py — Extract frames from a video for visual analysis.

Automatically picks a cost-optimal sampling rate based on video length:
  - Target: ~30 frames total (enough to understand the content)
  - Max rate: 1 frame/second (never more than this)
  - For longer videos, the interval grows so total frames stay around 30

Examples:
  30s  video → 1s  interval → 30 frames  (1fps)
  60s  video → 2s  interval → 30 frames  (0.5fps)
  5min video → 10s interval → 30 frames  (0.1fps)
  1hr  video → 2min interval → 30 frames (0.008fps)

Usage:
    python extract_frames.py <video_path> [output_dir] [--interval N]

Output frames are saved to /tmp/frames/<video_stem>/ by default.
Prints the list of frame paths on completion.
"""

import subprocess
import sys
import math
import argparse
from pathlib import Path

TARGET_FRAMES = 30  # aim for this many frames regardless of video length


def get_duration(video_path: str) -> float:
    """Return video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"Warning: could not detect duration, defaulting to 1fps", file=sys.stderr)
        return 0.0
    return float(result.stdout.strip())


def pick_interval(duration_seconds: float) -> int:
    """
    Choose the sampling interval (seconds between frames).
    Never sample faster than 1fps; for long videos space frames out
    so we stay near TARGET_FRAMES total.
    """
    if duration_seconds <= 0:
        return 1
    interval = math.ceil(duration_seconds / TARGET_FRAMES)
    return max(1, interval)  # floor at 1s — never go faster than 1fps


def extract_frames(video_path: str, output_dir=None, interval: int = None):
    video = Path(video_path)
    if not video.exists():
        print(f"Error: Video not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    if output_dir is None:
        output_dir = Path("/tmp/frames") / video.stem
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auto-detect interval if not overridden
    if interval is None:
        duration = get_duration(str(video))
        interval = pick_interval(duration)
        estimated = math.ceil(duration / interval) if duration > 0 else "?"
        print(f"Video duration : {duration:.0f}s")
        print(f"Sampling every : {interval}s  (~{estimated} frames)")
    else:
        print(f"Sampling every : {interval}s  (manual override)")

    fps = 1.0 / interval  # e.g. interval=10 → fps=0.1

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vf", f"fps={fps}",
        str(output_dir / "frame_%04d.jpg"),
    ]

    print(f"Output         : {output_dir}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    frames = sorted(output_dir.glob("frame_*.jpg"))
    print(f"\nExtracted {len(frames)} frame(s) at 1/{interval}fps.")
    for f in frames:
        print(str(f))

    return frames, interval


def main():
    parser = argparse.ArgumentParser(description="Extract frames from video for visual analysis")
    parser.add_argument("video", help="Path to the video file")
    parser.add_argument("output_dir", nargs="?", default=None,
                        help="Where to save frames (default: /tmp/frames/<name>/)")
    parser.add_argument("--interval", type=int, default=None,
                        help="Seconds between frames. Auto-calculated if omitted.")
    args = parser.parse_args()

    extract_frames(args.video, args.output_dir, args.interval)


if __name__ == "__main__":
    main()
