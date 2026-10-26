"""File kinds and output naming.

Every action writes a new file next to the original and never overwrites
anything: ``Page 001.pdf`` -> ``Page 001.jpg``, ``Page 001 Cropped.jpg``,
``Page 001 Cropped 2.jpg`` if that one exists already.
"""
from __future__ import annotations

from pathlib import Path

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".heic", ".heif", ".avif", ".ico"}
DOCUMENT_EXTS = {".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".html", ".htm"}
SHEET_EXTS = {".xls", ".xlsx", ".ods", ".csv"}
SLIDES_EXTS = {".ppt", ".pptx", ".odp"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".3gp"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac", ".opus", ".wma"}

KINDS = {
    "pdf": PDF_EXTS,
    "image": IMAGE_EXTS,
    "document": DOCUMENT_EXTS,
    "sheet": SHEET_EXTS,
    "slides": SLIDES_EXTS,
    "video": VIDEO_EXTS,
    "audio": AUDIO_EXTS,
}

# Formats Pillow writes, keyed by the extension we produce.
PIL_FORMAT = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
    "gif": "GIF",
    "ico": "ICO",
    "avif": "AVIF",
    "heic": "HEIF",
    "heif": "HEIF",
}


class UnsupportedFile(ValueError):
    pass


class MissingTool(RuntimeError):
    """An optional helper program (ffmpeg, LibreOffice, Tesseract) is not installed."""

    def __init__(self, program: str, package: str) -> None:
        super().__init__(f"{program} is not installed. Install it with: sudo apt install {package}")
        self.program = program
        self.package = package


def kind(path: Path) -> str:
    """Return the file kind (``"pdf"``, ``"image"``, ``"video"``…); raise for anything else."""
    ext = Path(path).suffix.lower()
    for name, exts in KINDS.items():
        if ext in exts:
            return name
    raise UnsupportedFile(f"Unsupported file type: {Path(path).name}")


def is_supported(path: Path) -> bool:
    try:
        kind(path)
        return True
    except UnsupportedFile:
        return False


def ext_of(path: Path) -> str:
    """Lower-case extension without the dot, ``jpeg`` folded into ``jpg``."""
    ext = Path(path).suffix.lower().lstrip(".")
    return {"jpeg": "jpg", "tif": "tiff", "htm": "html", "heif": "heic", "oga": "ogg"}.get(ext, ext)


def output_path(src: Path, suffix: str = "", ext: str | None = None) -> Path:
    """Next free path beside ``src``: ``<stem>[ <suffix>][ N].<ext>``."""
    src = Path(src)
    ext = (ext or src.suffix.lstrip(".")).lower()
    stem = f"{src.stem} {suffix}".rstrip() if suffix else src.stem
    candidate = src.with_name(f"{stem}.{ext}")
    n = 2
    while candidate.exists():
        candidate = src.with_name(f"{stem} {n}.{ext}")
        n += 1
    return candidate
