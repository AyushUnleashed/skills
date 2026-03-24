#!/bin/bash
# Validates all prerequisites needed for pod-clips skill
# Run this FIRST before anything else

set -e

ERRORS=0

echo "=== Pod Clips: Prerequisite Check ==="
echo ""

# Check yt-dlp
if command -v yt-dlp &> /dev/null; then
    echo "[OK] yt-dlp found: $(which yt-dlp)"
else
    echo "[FAIL] yt-dlp not found. Install with: pip install yt-dlp"
    ERRORS=$((ERRORS + 1))
fi

# Check ffmpeg
if command -v ffmpeg &> /dev/null; then
    echo "[OK] ffmpeg found: $(which ffmpeg)"
else
    echo "[FAIL] ffmpeg not found. Install with: sudo apt install ffmpeg"
    ERRORS=$((ERRORS + 1))
fi

# Check python3
if command -v python3 &> /dev/null; then
    echo "[OK] python3 found: $(python3 --version)"
else
    echo "[FAIL] python3 not found."
    ERRORS=$((ERRORS + 1))
fi

# Check python json module (should always be there, but sanity check)
if python3 -c "import json" 2>/dev/null; then
    echo "[OK] python3 json module available"
else
    echo "[FAIL] python3 json module missing"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# Validate YouTube URL if provided as argument
if [ -n "$1" ]; then
    URL="$1"
    echo "--- Validating URL: $URL ---"

    # Basic URL format check
    if [[ "$URL" =~ ^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]{11} ]]; then
        echo "[OK] URL format looks valid"
    else
        echo "[FAIL] URL doesn't look like a valid YouTube video URL"
        echo "  Expected format: https://www.youtube.com/watch?v=XXXXXXXXXXX"
        echo "  Or: https://youtu.be/XXXXXXXXXXX"
        ERRORS=$((ERRORS + 1))
    fi

    # Try to fetch video metadata (title + duration) as a connectivity/availability check
    echo "Checking video availability..."
    METADATA=$(yt-dlp --print title --print duration_string "$URL" 2>/dev/null) || true
    if [ -n "$METADATA" ]; then
        TITLE=$(echo "$METADATA" | head -1)
        DURATION=$(echo "$METADATA" | tail -1)
        echo "[OK] Video found: \"$TITLE\" ($DURATION)"
        echo ""
        echo "VIDEO_TITLE=$TITLE"
        echo "VIDEO_DURATION=$DURATION"
    else
        echo "[FAIL] Could not fetch video metadata. Video may be private, deleted, or URL is wrong."
        ERRORS=$((ERRORS + 1))
    fi
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=== All checks passed ==="
    exit 0
else
    echo "=== $ERRORS check(s) failed ==="
    exit 1
fi
