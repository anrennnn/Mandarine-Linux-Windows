"""Documents, spreadsheets and slides with LibreOffice, plus PDF -> Word."""
from __future__ import annotations

from pathlib import Path

from . import external
from .files import ext_of, kind, output_path

DOCUMENT_TARGETS = ["pdf", "docx", "odt", "txt", "html", "rtf"]
SHEET_TARGETS = ["pdf", "xlsx", "ods", "csv"]
SLIDES_TARGETS = ["pdf", "pptx", "odp", "png"]

# LibreOffice --convert-to filters, per target.
FILTERS = {
    "pdf": "pdf",
    "docx": "docx:MS Word 2007 XML",
    "odt": "odt",
    "rtf": "rtf",
    "html": "html:XHTML Writer File:UTF8",
    "txt": "txt:Text (encoded):UTF8",
    "xlsx": "xlsx:Calc MS Excel 2007 XML",
    "ods": "ods",
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76",  # comma, quote, UTF-8
    "pptx": "pptx:Impress MS PowerPoint 2007 XML",
    "odp": "odp",
    "png": "png",
}


def targets(path: Path) -> list[str]:
    own = ext_of(path)
    pool = {"document": DOCUMENT_TARGETS, "sheet": SHEET_TARGETS, "slides": SLIDES_TARGETS}[kind(path)]
    if own == "md":
        own = "txt"
    return [t for t in pool if t != own]


def convert(path: Path, target: str) -> list[Path]:
    path = Path(path)
    if target not in targets(path):
        raise ValueError(f"Cannot convert {path.name} to {target.upper()}")
    produced = external.soffice_convert(path, FILTERS[target])
    return [external.move_result(produced, output_path(path, "", target))]


def pdf_to_word(path: Path, target: str = "docx") -> Path:
    """PDF -> DOCX/ODT through LibreOffice's PDF import (text stays editable)."""
    path = Path(path)
    produced = external.soffice_convert(path, FILTERS[target], infilter="writer_pdf_import")
    return external.move_result(produced, output_path(path, "", target))
