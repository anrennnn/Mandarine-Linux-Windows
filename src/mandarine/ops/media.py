"""Video and audio with ffmpeg: convert, compress, mute, rotate, resize,
normalise loudness and strip metadata."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from . import external
from .files import ext_of, kind, output_path

VIDEO_TARGETS = ["mp4", "webm", "gif", "mp3", "mov", "mkv"]
AUDIO_TARGETS = ["mp3", "m4a", "wav", "ogg", "flac", "opus"]

H264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"]
AAC = ["-c:a", "aac", "-b:a", "160k"]

ENCODE = {
    "mp4": H264 + AAC + ["-movflags", "+faststart"],
    "mov": H264 + AAC,
    "mkv": H264 + AAC,
    "webm": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1", "-deadline", "good",
             "-cpu-used", "4", "-c:a", "libopus", "-b:a", "128k"],
    "gif": ["-vf", "fps=12,scale='min(640,iw)':-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse",
            "-loop", "0", "-an"],
    "mp3": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    "wav": ["-vn", "-c:a", "pcm_s16le"],
    "ogg": ["-vn", "-c:a", "libvorbis", "-q:a", "5"],
    "flac": ["-vn", "-c:a", "flac"],
    "opus": ["-vn", "-c:a", "libopus", "-b:a", "128k"],
}

Progress = Callable[[int, int], None] | None


def targets(path: Path) -> list[str]:
    own = ext_of(path)
    pool = VIDEO_TARGETS if kind(path) == "video" else AUDIO_TARGETS
    return [t for t in pool if t != own]


def duration(path: Path) -> float:
    """Seconds, or 0 when ffprobe cannot tell."""
    try:
        proc = external.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(path)], timeout=60)
        return float(proc.stdout.strip() or 0)
    except (ValueError, RuntimeError):
        return 0.0


def ffmpeg(src: Path, dest: Path, args: list[str], progress: Progress = None) -> Path:
    """Run ffmpeg ``src -> dest`` reporting progress in per-mille of the duration."""
    exe = external.require("ffmpeg")
    total = duration(src) if progress else 0.0
    # -loglevel error keeps stderr small: it is read only after stdout, so a chatty
    # ffmpeg could otherwise fill the pipe and stall both processes.
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(src), *args,
           "-progress", "pipe:1", "-nostats", str(dest)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **external.quiet())
    assert proc.stdout is not None
    for line in proc.stdout:
        m = re.match(r"out_time_us=(\d+)", line)
        if m and total and progress:
            progress(min(999, int(int(m.group(1)) / 1e3 / total)), 1000)
    err = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        dest.unlink(missing_ok=True)
        tail = " ".join(err.strip().splitlines()[-2:])
        raise RuntimeError(f"ffmpeg failed: {tail}")
    if progress:
        progress(1000, 1000)
    return dest


def convert(path: Path, target: str, progress: Progress = None) -> list[Path]:
    path = Path(path)
    if target not in targets(path):
        raise ValueError(f"Cannot convert {path.name} to {target.upper()}")
    return [ffmpeg(path, output_path(path, "", target), ENCODE[target], progress)]


def compress(path: Path, level: str = "medium", progress: Progress = None) -> Path:
    path = Path(path)
    ext = ext_of(path)
    if kind(path) == "video":
        crf = {"low": "24", "medium": "28", "high": "32"}[level]
        height = {"low": 1440, "medium": 1080, "high": 720}[level]
        dest = output_path(path, "Compressed", "mp4")
        args = ["-vf", f"scale=-2:'min({height},ih)'", "-c:v", "libx264", "-preset", "slow", "-crf", crf,
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
        ffmpeg(path, dest, args, progress)
        if ext == "mp4" and dest.stat().st_size >= path.stat().st_size:
            dest.write_bytes(path.read_bytes())  # never hand back a "compressed" file that grew
        return dest
    rate = {"low": "160k", "medium": "128k", "high": "96k"}[level]
    if ext == "mp3":
        args, out_ext = ["-vn", "-c:a", "libmp3lame", "-b:a", rate], "mp3"
    elif ext in ("m4a", "aac"):
        args, out_ext = ["-vn", "-c:a", "aac", "-b:a", rate], "m4a"
    elif ext == "opus":
        args, out_ext = ["-vn", "-c:a", "libopus", "-b:a", {"low": "96k", "medium": "64k", "high": "48k"}[level]], "opus"
    elif ext == "ogg":
        args, out_ext = ["-vn", "-c:a", "libvorbis", "-q:a", {"low": "4", "medium": "3", "high": "1"}[level]], "ogg"
    else:  # wav, flac, wma: a lossy copy is the only way to make them much smaller
        args, out_ext = ["-vn", "-c:a", "libmp3lame", "-b:a", rate], "mp3"
    dest = ffmpeg(path, output_path(path, "Compressed", out_ext), args, progress)
    if out_ext == ext and dest.stat().st_size >= path.stat().st_size:
        dest.write_bytes(path.read_bytes())  # never hand back a "compressed" file that grew
    return dest


def mute(path: Path, progress: Progress = None) -> Path:
    path = Path(path)
    return ffmpeg(path, output_path(path, "Muted"), ["-an", "-c:v", "copy"], progress)


def rotate(path: Path, degrees: int = 90, progress: Progress = None) -> Path:
    path = Path(path)
    vf = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}[degrees % 360]
    return ffmpeg(path, output_path(path, "Rotated"), ["-vf", vf, *H264, "-c:a", "copy"], progress)


def resize(path: Path, height: int = 720, progress: Progress = None) -> Path:
    path = Path(path)
    args = ["-vf", f"scale=-2:'min({height},ih)'", *H264, "-c:a", "copy"]
    return ffmpeg(path, output_path(path, f"{height}p", ext_of(path) if ext_of(path) != "gif" else "mp4"), args, progress)


def normalize(path: Path, progress: Progress = None) -> Path:
    """EBU R128 loudness normalisation (-16 LUFS, good for podcasts and social video)."""
    path = Path(path)
    ext = ext_of(path)
    codec = ENCODE.get(ext, ENCODE["mp3"])
    out_ext = ext if ext in ENCODE else "mp3"
    if kind(path) == "video":
        args = ["-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k"]
        return ffmpeg(path, output_path(path, "Normalized"), args, progress)
    args = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", *codec]
    return ffmpeg(path, output_path(path, "Normalized", out_ext), args, progress)


def strip_metadata(path: Path, progress: Progress = None) -> Path:
    path = Path(path)
    args = ["-map", "0", "-map_metadata", "-1", "-map_chapters", "-1", "-c", "copy"]
    return ffmpeg(path, output_path(path, "Clean"), args, progress)
