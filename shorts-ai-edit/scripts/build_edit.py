#!/usr/bin/env python3
"""
build_edit.py — Assemble a final edited video from an EDL markdown file using FFMPEG.

Usage:
    python build_edit.py --video <aroll.mp4> --edl <edl.md> --output <out.mp4> [--assets-dir <dir>]

Image handling in FULL layout:
    Images are scaled to *fit* (contain, no crop), centered on a dark background,
    with rounded corners. Requires Pillow for rounded corners; falls back to
    FFMPEG-only contain+pad if Pillow is not installed.

Video handling in FULL layout:
    Videos are scaled to fill and cropped to 1080×1920 (standard crop-to-fill).
"""

import re
import os
import sys
import subprocess
import tempfile
import argparse
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

ENCODE_FLAGS = ["-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-ar", "44100", "-r", "30"]

FILL_FILTER      = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
FILL_HALF_FILTER = "scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960"
# Contain-fit within padded area (20px padding each side → 1040×1880 effective)
CONTAIN_FILTER   = "scale=1040:1880:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=#111111"


# ─── EDL Parsing ──────────────────────────────────────────────────────────────

def parse_time(t: str) -> float:
    parts = t.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return 0.0


def parse_edl(edl_path: str) -> list[dict]:
    content = Path(edl_path).read_text()
    sections = []
    for raw in re.split(r"^## Section \d+", content, flags=re.MULTILINE)[1:]:
        section = {}
        m = re.search(r"\*\*Time\*\*:\s*([\d:]+)\s*[–\-]+\s*([\d:]+)", raw)
        if m:
            section["start"] = parse_time(m.group(1))
            section["end"] = parse_time(m.group(2))
        m = re.search(r"\*\*Edit Type\*\*:\s*(\S+)", raw)
        if m:
            section["edit_type"] = m.group(1).upper().rstrip(".,")
        m = re.search(r"\*\*Asset File\*\*:\s*`([^`]+)`", raw)
        if m:
            section["asset_file"] = m.group(1).strip()
        m = re.search(r"\*\*Layout\*\*:\s*(\S+)", raw)
        if m:
            section["layout"] = m.group(1).upper().rstrip(".,")
        m = re.search(r'\*\*Script\*\*:\s*"([^"]+)"', raw)
        if m:
            section["script"] = m.group(1)[:60]
        if "start" in section and "edit_type" in section:
            sections.append(section)
    return sections


# ─── Image Pre-processing ─────────────────────────────────────────────────────

def preprocess_image(img_path: str, out_png: str,
                     width=1080, height=1920, padding=20, radius=30,
                     bg=(17, 17, 17)) -> bool:
    """
    Scale image to fit within the padded area, apply rounded corners,
    composite onto a dark background, save as PNG.
    Returns True on success, False if Pillow is unavailable.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    img = Image.open(img_path).convert("RGBA")
    max_w = width - padding * 2
    max_h = height - padding * 2
    img.thumbnail((max_w, max_h), Image.LANCZOS)

    # Rounded corner mask on the scaled image
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=255)
    img.putalpha(mask)

    # Composite onto dark background
    canvas = Image.new("RGBA", (width, height), (*bg, 255))
    x = (width - img.width) // 2
    y = (height - img.height) // 2
    canvas.paste(img, (x, y), img)

    canvas.convert("RGB").save(out_png, "PNG")
    return True


# ─── FFMPEG Helpers ───────────────────────────────────────────────────────────

def run(cmd: list, desc: str = ""):
    if desc:
        print(f"\n  → {desc}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nFFMPEG ERROR:\n{result.stderr[-800:]}", file=sys.stderr)
        raise RuntimeError("ffmpeg failed — see error above")
    return result


def build_aroll_clip(main_video: str, start: float, end: float, output: str, idx: int):
    """Trim + scale the main A-roll to 1080×1920."""
    run([
        "ffmpeg", "-y",
        "-ss", str(start), "-t", str(end - start),
        "-i", main_video,
        "-vf", FILL_FILTER,
        *ENCODE_FLAGS, output,
    ], f"Section {idx}: A-ROLL [{start:.0f}s–{end:.0f}s]")


def build_full_clip(main_video: str, asset_path: str, start: float, end: float,
                    output: str, idx: int, tmpdir: str):
    """
    FULL layout — asset fills 1080×1920, A-roll audio.
    Images: contain-fit + dark padding + rounded corners (Pillow) or FFMPEG fallback.
    Videos: crop-to-fill.
    """
    duration = end - start
    is_image = Path(asset_path).suffix.lower() in IMAGE_EXTS

    if is_image:
        # Try Pillow path first (rounded corners)
        preprocessed = os.path.join(tmpdir, f"img_full_{idx}.png")
        used_pillow = preprocess_image(asset_path, preprocessed)

        if used_pillow:
            # Preprocessed PNG already has correct size — just loop it
            run([
                "ffmpeg", "-y",
                "-loop", "1", "-t", str(duration), "-i", preprocessed,
                "-ss", str(start), "-t", str(duration), "-i", main_video,
                "-filter_complex", "[0:v]format=yuv420p[v]",
                "-map", "[v]", "-map", "1:a",
                *ENCODE_FLAGS, "-shortest", output,
            ], f"Section {idx}: FULL image (contain+rounded) [{start:.0f}s–{end:.0f}s]")
        else:
            # Pillow not available — FFMPEG contain+pad (no rounded corners)
            print("  ℹ Pillow not installed — using FFMPEG contain+pad (no rounded corners)")
            run([
                "ffmpeg", "-y",
                "-loop", "1", "-t", str(duration), "-i", asset_path,
                "-ss", str(start), "-t", str(duration), "-i", main_video,
                "-filter_complex", f"[0:v]{CONTAIN_FILTER}[v]",
                "-map", "[v]", "-map", "1:a",
                *ENCODE_FLAGS, "-shortest", output,
            ], f"Section {idx}: FULL image (contain) [{start:.0f}s–{end:.0f}s]")
    else:
        # Video asset → crop-to-fill
        run([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-t", str(duration), "-i", asset_path,
            "-ss", str(start), "-t", str(duration), "-i", main_video,
            "-filter_complex", f"[0:v]{FILL_FILTER}[v]",
            "-map", "[v]", "-map", "1:a",
            *ENCODE_FLAGS, "-shortest", output,
        ], f"Section {idx}: FULL video (fill) [{start:.0f}s–{end:.0f}s]")


def build_split_clip(main_video: str, asset_path: str, start: float, end: float,
                     output: str, idx: int):
    """
    SPLIT layout — asset (top 1080×960) + speaker (bottom 1080×960).
    Both images and videos use crop-to-fill for the top half.
    A-roll audio throughout.
    """
    duration = end - start
    is_image = Path(asset_path).suffix.lower() in IMAGE_EXTS
    loop_flags = ["-loop", "1"] if is_image else ["-stream_loop", "-1"]

    filter_graph = (
        f"[0:v]{FILL_HALF_FILTER}[asset];"
        f"[1:v]{FILL_HALF_FILTER}[speaker];"
        "[asset][speaker]vstack[v]"
    )

    run([
        "ffmpeg", "-y",
        *loop_flags, "-t", str(duration), "-i", asset_path,
        "-ss", str(start), "-t", str(duration), "-i", main_video,
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "1:a",
        *ENCODE_FLAGS, "-shortest", output,
    ], f"Section {idx}: SPLIT [{start:.0f}s–{end:.0f}s] ← {Path(asset_path).name}")


def concatenate_clips(clip_paths: list[str], output: str):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
        concat_list = f.name
    try:
        run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy", output,
        ], "Concatenating all clips → final output")
    finally:
        os.unlink(concat_list)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Assemble edited video from EDL")
    parser.add_argument("--video", required=True)
    parser.add_argument("--edl", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--assets-dir", default=None)
    args = parser.parse_args()

    edl_path = Path(args.edl)
    assets_dir = Path(args.assets_dir) if args.assets_dir else edl_path.parent

    sections = parse_edl(args.edl)
    if not sections:
        print("ERROR: No sections found in EDL.", file=sys.stderr)
        sys.exit(1)

    print(f"\nParsed {len(sections)} sections | output → {args.output}")

    # Check Pillow availability upfront
    try:
        import PIL
        print("  Pillow available — images will use contain+rounded corners")
    except ImportError:
        print("  ⚠ Pillow not found (pip install pillow) — images will use FFMPEG contain+pad")

    counts = {"A-ROLL": 0, "ASSET": 0, "MOTION-GRAPHIC": 0, "FALLBACK": 0}

    with tempfile.TemporaryDirectory() as tmpdir:
        clip_paths = []

        for i, section in enumerate(sections):
            clip_out = os.path.join(tmpdir, f"clip_{i:04d}.mp4")
            edit_type = section.get("edit_type", "A-ROLL")
            layout = section.get("layout", "FULL")
            start = section["start"]
            end = section["end"]

            if edit_type == "A-ROLL":
                build_aroll_clip(args.video, start, end, clip_out, i + 1)
                counts["A-ROLL"] += 1

            elif edit_type in ("ASSET", "MOTION-GRAPHIC"):
                asset_file = section.get("asset_file", "")
                fallback = False

                if not asset_file or "[to be generated]" in asset_file:
                    print(f"\n  ⚠ Section {i+1}: no asset file — falling back to A-ROLL")
                    fallback = True
                else:
                    asset_path = Path(asset_file)
                    if not asset_path.is_absolute():
                        asset_path = assets_dir / asset_file
                    if not asset_path.exists():
                        print(f"\n  ⚠ Section {i+1}: asset not found ({asset_path}) — falling back to A-ROLL")
                        fallback = True
                    elif layout == "SPLIT":
                        build_split_clip(args.video, str(asset_path), start, end, clip_out, i + 1)
                        counts[edit_type] += 1
                    else:
                        build_full_clip(args.video, str(asset_path), start, end, clip_out, i + 1, tmpdir)
                        counts[edit_type] += 1

                if fallback:
                    build_aroll_clip(args.video, start, end, clip_out, i + 1)
                    counts["FALLBACK"] += 1
            else:
                print(f"\n  ⚠ Section {i+1}: unknown type '{edit_type}' — using A-ROLL")
                build_aroll_clip(args.video, start, end, clip_out, i + 1)
                counts["FALLBACK"] += 1

            clip_paths.append(clip_out)

        print(f"\nAll clips built. Concatenating...")
        concatenate_clips(clip_paths, args.output)

    total = sum(s["end"] - s["start"] for s in sections)
    print(f"\n{'='*50}")
    print(f"  Done! → {args.output}")
    print(f"  Duration       : ~{total:.0f}s")
    print(f"  A-ROLL         : {counts['A-ROLL']}")
    print(f"  ASSET          : {counts['ASSET']}")
    print(f"  MOTION-GRAPHIC : {counts['MOTION-GRAPHIC']}")
    if counts["FALLBACK"]:
        print(f"  Fallbacks (⚠)  : {counts['FALLBACK']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
