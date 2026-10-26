"""Convert any supported file to another format.

PDFs and images are handled in-process (PyMuPDF, Pillow). Documents go
through LibreOffice, video and audio through ffmpeg, text extraction through
the PDF text layer or Tesseract.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image, features

from . import media, office, text
from .files import PIL_FORMAT, ext_of, kind, output_path

try:  # HEIC/HEIF read and write (iPhone photos)
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF = True
except ImportError:  # pragma: no cover - the .deb always ships it
    HEIF = False

AVIF = bool(features.check("avif"))

# Clockwise from the top of the wheel, so the order matters.
PDF_TARGETS = ["docx", "jpg", "png", "txt", "webp", "odt"]
IMAGE_TARGETS = ["pdf", "jpg", "png", "webp", "avif", "heic", "ico", "txt"]

# What a plain ``convert`` with no target does.
DEFAULTS = {"pdf": "jpg", "image": "pdf", "document": "pdf", "sheet": "pdf", "slides": "pdf",
            "video": "mp4", "audio": "mp3"}


def targets_for(path: Path) -> list[str]:
    """Formats a file can be converted to, in wheel order."""
    k = kind(path)
    if k == "pdf":
        return list(PDF_TARGETS)
    if k == "image":
        own = ext_of(path)
        return [t for t in IMAGE_TARGETS if t != own
                and (t != "avif" or AVIF) and (t != "heic" or HEIF)]
    if k in ("video", "audio"):
        return media.targets(path)
    return office.targets(path)


def default_target(path: Path) -> str:
    choices = targets_for(path)
    preferred = DEFAULTS[kind(path)]
    return preferred if preferred in choices else choices[0]


def common_targets(paths: list[Path]) -> list[str]:
    """Targets every file in ``paths`` supports, in the first file's order."""
    if not paths:
        return []
    out = targets_for(paths[0])
    for p in paths[1:]:
        allowed = set(targets_for(p))
        out = [t for t in out if t in allowed]
    return out


def render_page(doc: pymupdf.Document, index: int, dpi: int = 200) -> Image.Image:
    """Render one PDF page to an RGB Pillow image."""
    pix = doc[index].get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def first_page_image(path: Path, dpi: int = 200) -> Image.Image:
    """The file as one image: an image as-is, a PDF as its first page."""
    if kind(path) == "pdf":
        with pymupdf.open(path) as doc:
            return render_page(doc, 0, dpi)
    with Image.open(path) as im:
        im.load()
        return im.copy()


def save_image(im: Image.Image, dest: Path, quality: int = 92) -> Path:
    fmt = PIL_FORMAT[dest.suffix.lower().lstrip(".")]
    if fmt == "JPEG" and im.mode not in ("RGB", "L"):
        im = flatten(im)
    if fmt in ("AVIF", "HEIF") and im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    params: dict = {"quality": quality} if fmt in ("JPEG", "WEBP", "AVIF", "HEIF") else {}
    if fmt == "PNG":
        params["optimize"] = True
    if fmt == "ICO":
        side = min(256, max(im.size))
        im = im.copy()
        im.thumbnail((side, side))
        params["sizes"] = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= side]
    im.save(dest, fmt, **params)
    return dest


def flatten(im: Image.Image, color=(255, 255, 255)) -> Image.Image:
    """Drop transparency onto a solid background."""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, color)
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def convert(path: Path, target: str | None = None, dpi: int = 200, progress=None) -> list[Path]:
    """Convert ``path`` to ``target`` and return the files written.

    A multi-page PDF to an image format gives one image per page (``Name p1.jpg``, ...).
    """
    path = Path(path)
    target = (target or default_target(path)).lower().lstrip(".")
    target = {"jpeg": "jpg", "heif": "heic", "tif": "tiff"}.get(target, target)
    if target not in targets_for(path):
        raise ValueError(f"Cannot convert {path.name} to {target.upper()}")
    k = kind(path)

    if k in ("video", "audio"):
        return media.convert(path, target, progress)
    if k in ("document", "sheet", "slides"):
        return office.convert(path, target)
    if target == "txt":
        return [text.to_text(path, progress)]

    if k == "pdf":
        if target in ("docx", "odt"):
            return [office.pdf_to_word(path, target)]
        out: list[Path] = []
        with pymupdf.open(path) as doc:
            total = doc.page_count
            for i in range(total):
                suffix = f"p{i + 1}" if total > 1 else ""
                dest = output_path(path, suffix, target)
                save_image(render_page(doc, i, dpi), dest)
                out.append(dest)
                if progress:
                    progress(i + 1, total)
        return out

    with Image.open(path) as im:
        im.load()
        if target == "pdf":
            dest = output_path(path, "", "pdf")
            flatten(im).save(dest, "PDF", resolution=float(im.info.get("dpi", (72, 72))[0] or 72))
        else:
            dest = save_image(im.copy(), output_path(path, "", target))
    if progress:
        progress(1, 1)
    return [dest]
