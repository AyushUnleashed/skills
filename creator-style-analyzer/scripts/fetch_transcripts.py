#!/usr/bin/env python3
"""
Fetch auto-generated English subtitles for YouTube Shorts and compile into one file.

Usage:
    python fetch_transcripts.py <links_file> <output_file>

Args:
    links_file:   Path to .txt file with video entries in format:
                  #01. Title | Views
                  https://www.youtube.com/shorts/XXXXX
    output_file:  Path to write compiled transcriptions
"""

import subprocess
import re
import os
import sys
import tempfile

def parse_links_file(filepath):
    """Parse the links file and extract video entries."""
    videos = []
    with open(filepath) as f:
        lines = f.readlines()

    current_title = None
    current_views = None
    for line in lines:
        line = line.strip()
        m = re.match(r'^#(\d+)\.\s+(.+?)\s+\|\s+(.+views)', line)
        if m:
            current_title = m.group(2)
            current_views = m.group(3)
        elif line.startswith("https://www.youtube.com/shorts/"):
            if current_title:
                videos.append({
                    "num": len(videos) + 1,
                    "title": current_title,
                    "views": current_views,
                    "url": line
                })
                current_title = None
    return videos


def srt_to_text(srt_content):
    """Parse SRT content to clean plain text, deduplicating auto-sub repetitions."""
    text_lines = []
    seen = set()
    for line in srt_content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.match(r'^\d+$', line):
            continue
        if re.match(r'\d{2}:\d{2}:\d{2}', line):
            continue
        line = re.sub(r'<[^>]+>', '', line)
        if line not in seen:
            seen.add(line)
            text_lines.append(line)
    return " ".join(text_lines)


def fetch_transcript(url, temp_dir):
    """Download auto-generated English subtitles for a single video."""
    vid_id = url.split("/")[-1].split("?")[0]
    sub_path = os.path.join(temp_dir, vid_id)

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "srt",
        "--convert-subs", "srt",
        "-o", sub_path,
        url
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None

    # Find the downloaded subtitle file
    for f_name in os.listdir(temp_dir):
        if vid_id in f_name and f_name.endswith(".srt"):
            srt_file = os.path.join(temp_dir, f_name)
            with open(srt_file) as sf:
                return srt_to_text(sf.read())
    return None


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <links_file> <output_file>")
        sys.exit(1)

    links_file = sys.argv[1]
    output_file = sys.argv[2]

    videos = parse_links_file(links_file)
    print(f"Found {len(videos)} videos to process")

    temp_dir = tempfile.mkdtemp(prefix="yt_subs_")
    results = []

    for i, v in enumerate(videos):
        print(f"[{i+1}/{len(videos)}] {v['title'][:60]}...", end=" ", flush=True)
        transcript = fetch_transcript(v["url"], temp_dir)
        results.append((v, transcript))
        if transcript:
            print(f"OK ({len(transcript)} chars)")
        else:
            print("NO SUBS")

    # Write output
    success = 0
    failed = 0
    with open(output_file, "w") as out:
        creator_name = os.path.basename(links_file).replace("_links.txt", "").replace("_", " ").title()
        out.write(f"{creator_name.upper()} - SHORT-FORM VIDEO TRANSCRIPTIONS\n")
        out.write("=" * 55 + "\n\n")

        for v, transcript in results:
            out.write("─" * 55 + "\n")
            out.write(f"#{v['num']:02d}. {v['title']} ({v['views']})\n")
            out.write(f"URL: {v['url']}\n")
            out.write("─" * 55 + "\n")
            if transcript:
                out.write(transcript + "\n\n")
                success += 1
            else:
                out.write("[TRANSCRIPT NOT AVAILABLE]\n\n")
                failed += 1

    print(f"\nDone! {success} transcribed, {failed} failed. Saved to {output_file}")


if __name__ == "__main__":
    main()
