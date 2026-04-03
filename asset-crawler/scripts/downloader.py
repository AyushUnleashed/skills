#!/usr/bin/env python3
"""
Concurrent asset downloader with link-type routing.

Reads a pipe-delimited asset file and downloads everything concurrently.
Two download methods: curl (direct URLs) vs yt-dlp (platform videos).

Input format (one per line, other lines ignored):
    IMAGE | https://example.com/photo.jpg | Description of the image
    VIDEO | https://youtu.be/abc123 | Description of the video

Usage:
    python downloader.py --input assets.txt --output ./asset-downloads
    python downloader.py --input assets.txt --output ./asset-downloads --dry-run
    python downloader.py --input assets.txt --output ./asset-downloads --type images
    python downloader.py --input assets.txt --output ./asset-downloads --workers 20
"""

import asyncio
import re
import sys
import json
import shutil
import hashlib
import argparse
import mimetypes
from pathlib import Path
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
import subprocess

DEFAULT_WORKERS = 10

# Domains where yt-dlp is needed (direct curl won't give you the file).
# Full list: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
YTDLP_DOMAINS = {
    "youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com",
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com",
    "dailymotion.com", "www.dailymotion.com",
    "twitch.tv", "www.twitch.tv", "clips.twitch.tv",
    "reddit.com", "www.reddit.com", "v.redd.it",
    "facebook.com", "www.facebook.com", "fb.watch",
    "bilibili.com", "www.bilibili.com",
    "streamable.com", "www.streamable.com",
    "rumble.com", "www.rumble.com",
}


def needs_ytdlp(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in YTDLP_DOMAINS


def guess_dest_subdir(kind: str, url: str) -> str:
    ext = Path(unquote(urlparse(url).path)).suffix.lower().split("?")[0]
    if kind == "VIDEO" or needs_ytdlp(url) or ext in (".mp4", ".webm", ".mov", ".mkv", ".avi"):
        return "videos"
    if ext in (".mp3", ".wav", ".ogg", ".flac", ".m4a") or "audio" in url.lower():
        return "audio"
    return "images"


def parse_assets(filepath: Path) -> list[dict]:
    assets = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            match = re.match(r"^(IMAGE|VIDEO)\s*\|\s*(.+?)\s*\|\s*(.+)$", line)
            if not match:
                continue
            kind, url, caption = match.groups()
            url = url.strip()
            if url.startswith("(") or "not directly provided" in url.lower():
                continue
            assets.append({"kind": kind, "url": url, "caption": caption.strip()})
    return assets


def safe_filename(url: str, caption: str, ext: str = None) -> str:
    parsed = urlparse(url)
    original = Path(unquote(parsed.path)).name
    if not original or original == "/":
        original = hashlib.md5(url.encode()).hexdigest()[:12]
    original = re.sub(r"[^\w.\-]", "_", original)
    if ext:
        original = f"{Path(original).stem}{ext}"
    slug = re.sub(r"[^\w]", "_", caption[:50]).strip("_").lower()
    return f"{slug}__{original}" if slug else original


def guess_extension(url: str) -> str:
    path = unquote(urlparse(url).path)
    ext = Path(path).suffix.lower().split("?")[0]
    if ext and len(ext) <= 5:
        return ext
    mt, _ = mimetypes.guess_type(path)
    if mt:
        guessed = mimetypes.guess_extension(mt)
        if guessed:
            return guessed
    return ""


async def download_direct(url: str, dest: Path) -> bool:
    cmd = [
        "curl", "-fsSL",
        "--max-time", "120",
        "--retry", "2",
        "-o", str(dest),
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        print(f"  FAIL curl: {stderr.decode().strip()[:120]}")
        return False
    return dest.exists() and dest.stat().st_size > 0


def _ytdlp_sync(url: str, dest_dir: Path, filename_prefix: str) -> bool:
    if not shutil.which("yt-dlp"):
        print("  SKIP: yt-dlp not installed -> pip install yt-dlp")
        return False
    if "/embed/" in url and "youtube" in url:
        vid_id = url.split("/embed/")[-1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={vid_id}"
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", str(dest_dir / f"{filename_prefix}__%(title)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAIL yt-dlp: {result.stderr.strip()[:200]}")
        return False
    return True


async def download_ytdlp(url: str, dest_dir: Path, filename_prefix: str,
                         executor: ThreadPoolExecutor) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, _ytdlp_sync, url, dest_dir, filename_prefix)


class Progress:
    def __init__(self, total: int):
        self.total = total
        self._done = 0
        self._lock = asyncio.Lock()

    async def tick(self, caption: str, status: str):
        async with self._lock:
            self._done += 1
            icon = "OK" if status == "ok" else "FAIL"
            print(f"  [{self._done:3d}/{self.total}] {icon:4s} | {caption[:70]}")


async def process_one(asset: dict, output_dir: Path, executor: ThreadPoolExecutor,
                      semaphore: asyncio.Semaphore, progress: Progress) -> dict:
    url = asset["url"]
    caption = asset["caption"]
    use_ytdlp = needs_ytdlp(url)
    method = "yt-dlp" if use_ytdlp else "curl"
    subdir = guess_dest_subdir(asset["kind"], url)
    dest_dir = output_dir / subdir

    result = {
        "url": url,
        "caption": caption,
        "method": method,
        "dest_dir": subdir,
        "status": "pending",
        "filename": None,
    }

    prefix = safe_filename(url, caption)
    dest_dir.mkdir(parents=True, exist_ok=True)

    async with semaphore:
        if use_ytdlp:
            success = await download_ytdlp(url, dest_dir, prefix, executor)
            result["filename"] = f"{prefix}__*.mp4"
        else:
            ext = guess_extension(url) or ".bin"
            fname = safe_filename(url, caption, ext=ext)
            dest = dest_dir / fname
            success = await download_direct(url, dest)
            result["filename"] = fname

    result["status"] = "ok" if success else "failed"
    await progress.tick(caption, result["status"])
    return result


async def run(assets: list[dict], output_dir: Path, max_workers: int):
    output_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("images", "videos", "audio"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(max_workers)
    executor = ThreadPoolExecutor(max_workers=min(max_workers, 4))
    progress = Progress(len(assets))

    print(f"Downloading {len(assets)} assets ({max_workers} concurrent)...\n")

    tasks = [process_one(a, output_dir, executor, semaphore, progress) for a in assets]
    results = await asyncio.gather(*tasks)

    executor.shutdown(wait=False)

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    ok = sum(1 for r in results if r["status"] == "ok")
    failed = sum(1 for r in results if r["status"] == "failed")
    print(f"\n{'='*50}")
    print(f"DONE: {ok} downloaded, {failed} failed, {len(assets) - ok - failed} skipped")
    print(f"Files in: {output_dir}")
    print(f"Manifest: {manifest_path}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Concurrent asset downloader")
    parser.add_argument("--input", type=str, required=True,
                        help="Path to pipe-delimited asset file")
    parser.add_argument("--output", type=str, required=True,
                        help="Output directory for downloaded files")
    parser.add_argument("--type", choices=["images", "videos", "all"], default="all",
                        help="Filter: images, videos, or all")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without downloading")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Max concurrent downloads (default: {DEFAULT_WORKERS})")
    args = parser.parse_args()

    assets_file = Path(args.input)
    output_dir = Path(args.output)

    if not assets_file.exists():
        print(f"ERROR: {assets_file} not found")
        sys.exit(1)

    assets = parse_assets(assets_file)
    print(f"Parsed {len(assets)} assets from {assets_file.name}\n")

    if args.type == "images":
        assets = [a for a in assets if a["kind"] == "IMAGE"]
    elif args.type == "videos":
        assets = [a for a in assets if a["kind"] == "VIDEO"]

    curl_count = sum(1 for a in assets if not needs_ytdlp(a["url"]))
    ytdlp_count = len(assets) - curl_count
    print(f"Routing: {curl_count} direct (curl)  |  {ytdlp_count} platform (yt-dlp)")
    print(f"Workers: {args.workers}\n")

    if args.dry_run:
        print("=== DRY RUN ===\n")
        for a in assets:
            method = "yt-dlp" if needs_ytdlp(a["url"]) else "curl"
            dest = guess_dest_subdir(a["kind"], a["url"])
            print(f"  {method:6s} -> {dest:10s} | {a['url'][:75]}")
            print(f"         caption: {a['caption'][:70]}\n")
        return

    asyncio.run(run(assets, output_dir, args.workers))


if __name__ == "__main__":
    main()
