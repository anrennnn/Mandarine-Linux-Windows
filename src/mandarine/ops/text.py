"""Text out of PDFs and images: the PDF text layer, else OCR with Tesseract."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pymupdf

from . import external
from .files import kind, output_path


def ocr_image(image_path: Path) -> str:
    langs = external.tesseract_langs()
    args = ["tesseract", str(image_path), "stdout"] + (["-l", langs] if langs else [])
    return external.run(args).stdout


def pdf_text(path: Path, progress=None) -> str:
    """The text layer of every page; scanned pages (no text) go through OCR."""
    pages: list[str] = []
    with pymupdf.open(path) as doc:
        total = doc.page_count
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if not text and external.available("tesseract"):
                with tempfile.TemporaryDirectory(prefix="mandarine-ocr-") as tmp:
                    img = Path(tmp) / "page.png"
                    page.get_pixmap(dpi=300).save(img)
                    text = ocr_image(img).strip()
            pages.append(text)
            if progress:
                progress(i + 1, total)
    return "\n\n".join(pages).strip() + "\n"


def to_text(path: Path, progress=None) -> Path:
    """``Name.txt`` beside ``path``: PDF text, or OCR of an image."""
    path = Path(path)
    if kind(path) == "pdf":
        text = pdf_text(path, progress)
    elif kind(path) == "image":
        text = ocr_image(path)
    else:
        raise ValueError(f"Cannot extract text from {path.name}")
    if not text.strip():
        raise ValueError(f"No text found in {path.name}")
    dest = output_path(path, "", "txt")
    dest.write_text(text, encoding="utf-8")
    return dest
