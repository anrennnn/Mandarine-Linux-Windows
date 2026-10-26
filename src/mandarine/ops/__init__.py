"""File operations. Pure functions, no Qt: the GUI and the CLI both call these."""
from . import external, media, office, text
from .background import Background, PRESETS, RATIOS, add_background
from .compress import LEVELS, compress
from .convert import common_targets, convert, default_target, first_page_image, targets_for
from .edit import Adjustments, crop, edit, rotate
from .files import MissingTool, UnsupportedFile, ext_of, is_supported, kind, output_path
from .markup import Mark, annotate, redact
from .metadata import read_metadata, strip_metadata
from .pages import merge, split

__all__ = [
    "Adjustments", "Background", "LEVELS", "Mark", "MissingTool", "PRESETS", "RATIOS", "UnsupportedFile",
    "add_background", "annotate", "common_targets", "compress", "convert", "crop", "default_target", "edit",
    "ext_of", "external", "first_page_image", "is_supported", "kind", "media", "merge", "office", "output_path",
    "read_metadata", "redact", "rotate", "split", "strip_metadata", "targets_for", "text",
]
