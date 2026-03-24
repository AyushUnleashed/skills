#!/bin/bash
# Downloads specific time ranges from a YouTube video as MP4.
# Uses native mp4 streams to avoid quality loss from re-encoding.
#
# Usage:
#   bash cut_clips.sh <youtube_url> <output_dir> <clip_name> <start_time> <end_time>
#
# Example:
#   bash cut_clips.sh "https://youtube.com/watch?v=abc" ./clips "stealth_mode" "00:01:57" "00:04:05"
#
# Output: <output_dir>/<clip_name>.mp4

set -e

URL="$1"
OUTPUT_DIR="$2"
CLIP_NAME="$3"
START="$4"
END="$5"

if [ -z "$URL" ] || [ -z "$OUTPUT_DIR" ] || [ -z "$CLIP_NAME" ] || [ -z "$START" ] || [ -z "$END" ]; then
    echo "Usage: bash cut_clips.sh <youtube_url> <output_dir> <clip_name> <start_time> <end_time>"
    echo "  Times in format HH:MM:SS or MM:SS"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

MP4_PATH="$OUTPUT_DIR/${CLIP_NAME}.mp4"

echo "Downloading: $CLIP_NAME ($START → $END)..."
yt-dlp --download-sections "*${START}-${END}" \
    --force-keyframes-at-cuts \
    -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" \
    --merge-output-format mp4 \
    -o "$OUTPUT_DIR/${CLIP_NAME}.%(ext)s" \
    "$URL" 2>&1 | tail -5

if [ -f "$MP4_PATH" ]; then
    echo "Done: $MP4_PATH"
else
    echo "Error: No output file found for $CLIP_NAME"
    exit 1
fi
