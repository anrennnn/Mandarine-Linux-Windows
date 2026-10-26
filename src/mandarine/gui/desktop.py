"""Which Linux desktop we run on, and the GNOME keyboard shortcut.

On Wayland an app cannot grab a global key, but GNOME lets us register a
custom shortcut that runs ``mandarine wheel`` through ``gsettings``.
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/mandarine/"


def current() -> set[str]:
    """``{"gnome"}``, ``{"kde"}``, ``{"x-cinnamon"}``… from XDG_CURRENT_DESKTOP."""
    return {d.strip().lower() for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":") if d.strip()}


def can_add_gnome_shortcut() -> bool:
    return bool(current() & {"gnome", "ubuntu", "unity", "pop"}) and shutil.which("gsettings") is not None


def gnome_accel(text: str) -> str:
    """Qt ``"Ctrl+Alt+Space"`` -> GNOME ``"<Control><Alt>space"``."""
    seq = QKeySequence(text)
    if seq.isEmpty():
        raise ValueError("Empty shortcut")
    combo = seq[0]
    mods = combo.keyboardModifiers()
    out = ""
    for flag, name in ((Qt.KeyboardModifier.ControlModifier, "<Control>"), (Qt.KeyboardModifier.AltModifier, "<Alt>"),
                       (Qt.KeyboardModifier.ShiftModifier, "<Shift>"), (Qt.KeyboardModifier.MetaModifier, "<Super>")):
        if mods & flag:
            out += name
    key = QKeySequence(combo.key()).toString(QKeySequence.SequenceFormat.PortableText)
    return out + (key.lower() if len(key) == 1 or key == "Space" else key)


def _gsettings(*args: str) -> str:
    proc = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gsettings failed")
    return proc.stdout.strip()


def add_gnome_shortcut(text: str, command: str = "mandarine wheel") -> None:
    raw = _gsettings("get", SCHEMA, "custom-keybindings")
    paths = ast.literal_eval(raw.removeprefix("@as ")) if raw else []
    entry = f"{SCHEMA}.custom-keybinding:{PATH}"
    _gsettings("set", entry, "name", "Mandarine")
    _gsettings("set", entry, "command", command)
    _gsettings("set", entry, "binding", gnome_accel(text))
    if PATH not in paths:
        _gsettings("set", SCHEMA, "custom-keybindings", str([*paths, PATH]))
