"""Optional helper programs: ffmpeg, LibreOffice and Tesseract.

They are found at call time (``PATH``, then the usual install folders on
Windows), so installing one later works without restarting the app. A missing
program raises ``MissingTool`` with the command that installs it (apt on
Linux, winget on Windows), which the GUI shows as-is.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path

from .files import MissingTool

PACKAGES = {
    "ffmpeg": "ffmpeg",
    "ffprobe": "ffmpeg",
    "soffice": "libreoffice-writer",
    "tesseract": "tesseract-ocr tesseract-ocr-spa",
}
WINGET = {
    "ffmpeg": "Gyan.FFmpeg",
    "ffprobe": "Gyan.FFmpeg",
    "soffice": "TheDocumentFoundation.LibreOffice",
    "tesseract": "UB-Mannheim.TesseractOCR",
}

# Conversions can be slow (a long video), but never hang forever.
TIMEOUT = 60 * 60
OFFICE_TIMEOUT = 5 * 60  # a document converts in seconds; a stuck LibreOffice should not hang the app


def is_windows() -> bool:
    return sys.platform == "win32"


def quiet() -> dict:
    """``subprocess`` options: UTF-8 text, and no console window flashing up on Windows."""
    opts: dict = {"encoding": "utf-8", "errors": "replace"}
    if is_windows():
        opts["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return opts


def windows_candidates(program: str) -> list[str]:
    """Where the Windows installers (and winget) put each helper."""
    env = os.environ.get
    local = env("LOCALAPPDATA", "")
    roots = [p for p in (env("ProgramFiles"), env("ProgramFiles(x86)"), env("ProgramW6432")) if p]
    exe = f"{program}.exe"
    out = [str(Path(sys.executable).parent / "tools" / exe)]  # bundled next to Mandarine.exe
    if program in ("ffmpeg", "ffprobe"):
        out += [str(Path(local) / "Microsoft" / "WinGet" / "Links" / exe)]
        out += sorted(glob(str(Path(local) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg*" / "*" / "bin" / exe)))
        out += [str(Path(r) / "ffmpeg" / "bin" / exe) for r in roots] + [rf"C:\ffmpeg\bin\{exe}"]
    elif program == "soffice":
        out += [str(Path(r) / "LibreOffice" / "program" / "soffice.exe") for r in roots]
    elif program == "tesseract":
        out += [str(Path(r) / "Tesseract-OCR" / exe) for r in roots]
        out += [str(Path(local) / "Programs" / "Tesseract-OCR" / exe)]
    return out


def find(program: str) -> str | None:
    names = ["soffice", "libreoffice"] if program == "soffice" else [program]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    if is_windows():
        for candidate in windows_candidates(program):
            if Path(candidate).is_file():
                return candidate
    return None


def available(program: str) -> bool:
    return find(program) is not None


def install_hint(program: str) -> str:
    if is_windows():
        return f"winget install -e --id {WINGET.get(program, program)}"
    return f"sudo apt install {PACKAGES.get(program, program)}"


def require(program: str) -> str:
    found = find(program)
    if not found:
        raise MissingTool(program, install_hint(program))
    return found


def run(args: list[str], timeout: int = TIMEOUT, **kw) -> subprocess.CompletedProcess:
    """Run a helper, raising a readable error with the tail of its output."""
    exe = require(args[0])
    proc = subprocess.run([exe, *args[1:]], capture_output=True, timeout=timeout, **quiet(), **kw)
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
    env = dict(os.environ)
    if not is_windows():
        env["SAL_USE_VCLPLUGIN"] = "svp"  # no display needed
    try:
        run(args, timeout=OFFICE_TIMEOUT, env=env)
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
