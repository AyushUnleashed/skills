#!/usr/bin/env python3
"""
Fetches YouTube transcript and converts to timestamped text format.

Usage:
    python3 fetch_transcript.py <youtube_url> <output_dir>

Creates:
    <output_dir>/raw_subtitle.json3     — Raw subtitle data from YouTube
    <output_dir>/full_transcript.txt    — Clean timestamped transcript
    <output_dir>/video_metadata.txt     — Title, duration, URL

Exits with code 1 on failure, 0 on success.
"""

import json
import subprocess
import sys
import os
import re


def get_video_slug(title):
    """Convert video title to a filesystem-safe slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:80]  # cap length


def fetch_metadata(url):
    """Get video title and duration."""
    result = subprocess.run(
        ['yt-dlp', '--print', 'title', '--print', 'duration_string', url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error fetching metadata: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    lines = result.stdout.strip().split('\n')
    return lines[0], lines[1] if len(lines) > 1 else "unknown"


def fetch_subtitles(url, output_path):
    """Download auto-generated subtitles in json3 format."""
    result = subprocess.run(
        ['yt-dlp', '--write-auto-sub', '--sub-lang', 'en',
         '--skip-download', '--sub-format', 'json3',
         '-o', output_path, url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error fetching subtitles: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # yt-dlp appends .en.json3 to the output path
    actual_path = output_path + '.en.json3'
    if not os.path.exists(actual_path):
        # Try finding it
        base_dir = os.path.dirname(output_path)
        base_name = os.path.basename(output_path)
        for f in os.listdir(base_dir):
            if f.startswith(base_name) and f.endswith('.json3'):
                actual_path = os.path.join(base_dir, f)
                break
    return actual_path


def ms_to_mmss(ms):
    total_sec = ms // 1000
    mins = total_sec // 60
    secs = total_sec % 60
    return f'{mins:02d}:{secs:02d}'


def convert_to_timestamped_text(json3_path, title, url, duration):
    """Convert json3 subtitle format to readable timestamped text.

    Each line uses [MM:SS-MM:SS] format where the end timestamp is the
    start of the next line. This lets ffmpeg cut precisely to the end
    of the last kept line without guessing duration.
    """
    with open(json3_path, 'r') as f:
        data = json.load(f)

    events = data.get('events', [])

    # First pass: collect all valid (start_ms, text) pairs
    pairs = []
    for event in events:
        segs = event.get('segs')
        if not segs:
            continue
        text = ''.join(s.get('utf8', '') for s in segs).strip()
        if not text or text == '\n':
            continue
        start_ms = event.get('tStartMs', 0)
        pairs.append((start_ms, text))

    # Second pass: build lines with start-end timestamps
    # end of line N = start of line N+1 (exact boundary for cutting)
    lines = []
    for i, (start_ms, text) in enumerate(pairs):
        if i + 1 < len(pairs):
            end_ms = pairs[i + 1][0]
        else:
            # Last line: use dDurationMs if available, else +3s
            event_dur = events[-1].get('dDurationMs', 3000)
            end_ms = start_ms + event_dur
        lines.append(f'[{ms_to_mmss(start_ms)}-{ms_to_mmss(end_ms)}] {text}')

    header = f"# Transcript: {title}\n# Video: {url}\n# Duration: {duration}\n\n"
    return header + '\n'.join(lines), len(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 fetch_transcript.py <youtube_url> <output_dir>")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2]

    os.makedirs(output_dir, exist_ok=True)

    print(f"Fetching metadata for: {url}")
    title, duration = fetch_metadata(url)
    print(f"Video: {title} ({duration})")

    # Save metadata
    with open(os.path.join(output_dir, 'video_metadata.txt'), 'w') as f:
        f.write(f"title={title}\n")
        f.write(f"duration={duration}\n")
        f.write(f"url={url}\n")
        f.write(f"slug={get_video_slug(title)}\n")

    print("Fetching subtitles...")
    raw_path = os.path.join(output_dir, 'raw_subtitle')
    json3_path = fetch_subtitles(url, raw_path)
    print(f"Raw subtitles saved to: {json3_path}")

    print("Converting to timestamped text...")
    transcript, line_count = convert_to_timestamped_text(json3_path, title, url, duration)

    transcript_path = os.path.join(output_dir, 'full_transcript.txt')
    with open(transcript_path, 'w') as f:
        f.write(transcript)

    print(f"Transcript saved: {transcript_path} ({line_count} lines)")
    print("Done.")


if __name__ == '__main__':
    main()
