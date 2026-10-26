"""Optional helper programs: ffmpeg, LibreOffice and Tesseract.

They are found on ``PATH`` at call time, so installing one later works
without restarting the app. A missing program raises ``MissingTool`` with the
apt package to install, which the GUI shows as-is.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .files import MissingTool

PACKAGES = {
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffmpeg",
    "soffice": "libreoffice-writer",
    "tesseract": "tesseract-ocr tesseract-ocr-spa",
}

# Conversions can be slow (a long video), but never hang forever.
TIMEOUT = 60 * 60


def find(program: str) -> str | None:
    names = ["soffice", "libreoffice"] if program == "soffice" else [program]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def available(program: str) -> bool:
    return find(program) is not None


def require(program: str) -> str:
    found = find(program)
    if not found:
        raise MissingTool(program, PACKAGES.get(program, program))
    return found


def run(args: list[str], timeout: int = TIMEOUT, **kw) -> subprocess.CompletedProcess:
    """Run a helper, raising a readable error with the tail of its output."""
    exe = require(args[0])
    proc = subprocess.run([exe, *args[1:]], capture_output=True, text=True, timeout=timeout, **kw)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise RuntimeError(f"{args[0]} failed: " + (" ".join(tail) or f"exit code {proc.returncode}"))
    return proc


def soffice_convert(src: Path, filter_: str, infilter: str | None = None) -> Path:
    """Convert with LibreOffice into a temp dir and return the produced file.

    A private user profile lets this run while LibreOffice is open on the
    desktop (otherwise the call is handed to that instance and returns early).
    """
    out_dir = Path(tempfile.mkdtemp(prefix="mandarine-lo-"))
    profile = Path(tempfile.mkdtemp(prefix="mandarine-lo-profile-"))
    args = ["soffice", f"-env:UserInstallation={profile.as_uri()}", "--headless", "--norestore"]
    if infilter:
        args.append(f"--infilter={infilter}")
    args += ["--convert-to", filter_, "--outdir", str(out_dir), str(src)]
    try:
        run(args, env={**os.environ, "SAL_USE_VCLPLUGIN": "svp"})
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    produced = sorted(out_dir.iterdir())
    if not produced:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise RuntimeError(f"LibreOffice could not convert {src.name}")
    return produced[0]


def move_result(tmp: Path, dest: Path) -> Path:
    """Move a helper's temp output to ``dest`` and drop its temp folder."""
    shutil.move(str(tmp), dest)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    return dest


def tesseract_langs() -> str:
    """Spanish and English when installed, else whatever Tesseract has."""
    proc = run(["tesseract", "--list-langs"], timeout=30)
    have = {line.strip() for line in (proc.stdout + proc.stderr).splitlines()[1:] if line.strip()}
    wanted = [lang for lang in ("spa", "eng") if lang in have]
    return "+".join(wanted) if wanted else ""
