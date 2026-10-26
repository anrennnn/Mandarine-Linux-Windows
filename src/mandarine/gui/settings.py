"""Settings window."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QKeySequenceEdit, QLabel, QPushButton, QWidget,
)

import subprocess
import sys

from .. import __version__, ops
from ..i18n import tr
from . import desktop, hotkey
from .glass import GlassDialog

GITHUB = "https://github.com/anrennnn/Mandarine-Linux-Windows"


HELPERS = [
    ("ffmpeg", "Video and audio (ffmpeg)"),
    ("soffice", "Documents (LibreOffice)"),
    ("tesseract", "Text from images (Tesseract OCR)"),
]


def install_helper(program: str) -> None:
    """Windows: run winget in a console window the user can watch."""
    package = ops.external.WINGET[program]
    subprocess.Popen(["cmd", "/c", "start", "winget", "install", "-e", "--id", package,
                      "--accept-source-agreements", "--accept-package-agreements"])


def open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-weight: 600; margin-top: 6px;")
    return label


class SettingsDialog(GlassDialog):
    """Everything the tray menu used to hold, plus the shortcut."""

    changed = Signal(str, object)  # settings key, new value

    def __init__(self, settings: QSettings, hotkey_status: str, wayland_hint: bool, parent: QWidget | None = None) -> None:
        super().__init__(tr("Mandarine Settings"), parent)
        self.settings = settings
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        row = 0

        grid.addWidget(_section(tr("Shortcut")), row, 0, 1, 3)
        row += 1
        self.shortcut = QKeySequenceEdit(QKeySequence(str(settings.value("hotkey", hotkey.DEFAULT))))
        self.shortcut.setMaximumSequenceLength(1)
        self.shortcut.editingFinished.connect(self._shortcut_done)
        reset = QPushButton(tr("Default"))
        reset.clicked.connect(self._shortcut_default)
        grid.addWidget(QLabel(tr("Open the wheel")), row, 0)
        grid.addWidget(self.shortcut, row, 1)
        grid.addWidget(reset, row, 2)
        row += 1
        self.shortcut_status = QLabel(hotkey_status)
        self.shortcut_status.setObjectName("Muted")
        self.shortcut_status.setWordWrap(True)
        grid.addWidget(self.shortcut_status, row, 0, 1, 3)
        row += 1
        self.gnome_button: QPushButton | None = None
        if wayland_hint:
            hint = QLabel(tr("On Wayland, apps cannot watch global drags or keys. Use the floating bubble, or add a "
                             "shortcut in your desktop's keyboard settings that runs: mandarine wheel"))
            hint.setObjectName("Muted")
            hint.setWordWrap(True)
            hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(hint, row, 0, 1, 3)
            row += 1
            if desktop.can_add_gnome_shortcut():
                self.gnome_button = QPushButton(tr("Set up the shortcut in GNOME"))
                self.gnome_button.clicked.connect(self._gnome_shortcut)
                grid.addWidget(self.gnome_button, row, 0, 1, 3)
                row += 1

        grid.addWidget(_section(tr("Behaviour")), row, 0, 1, 3)
        row += 1
        self.checks: dict[str, QCheckBox] = {}
        for key, label, default in [
            ("enabled", "Show the wheel when I hold Shift while dragging a file", True),
            ("bubble", "Show the floating bubble (drop files on it; works on Wayland)", wayland_hint),
            ("context_menu", "Add Mandarine to the file manager's right-click menu", False),
            ("login", "Open at login", False),
        ]:
            box = QCheckBox(tr(label))
            box.setChecked(settings.value(key, default, type=bool))
            box.toggled.connect(lambda v, k=key: self._emit(k, v))
            grid.addWidget(box, row, 0, 1, 3)
            self.checks[key] = box
            row += 1
        tools_first = QCheckBox(tr("Open the tools ring first (Ctrl+Shift opens the other one)"))
        tools_first.setChecked(str(settings.value("wheel/first", "formats")) == "tools")
        tools_first.toggled.connect(lambda v: self._emit("wheel/first", "tools" if v else "formats"))
        grid.addWidget(tools_first, row, 0, 1, 3)
        self.checks["wheel/first"] = tools_first
        row += 1

        grid.addWidget(_section(tr("Defaults")), row, 0, 1, 3)
        row += 1
        self.combos: dict[str, QComboBox] = {}
        for key, label, options, default in [
            ("compress/level", "Compression", [("low", "Light (best quality)"), ("medium", "Balanced"),
                                               ("high", "Strong (smallest)")], "medium"),
        ]:
            combo = QComboBox()
            for value, text in options:
                combo.addItem(tr(text), value)
            combo.setCurrentIndex(max(0, combo.findData(str(settings.value(key, default)))))
            combo.currentIndexChanged.connect(lambda _i, k=key, c=combo: self._emit(k, c.currentData()))
            grid.addWidget(QLabel(tr(label)), row, 0)
            grid.addWidget(combo, row, 1, 1, 2)
            self.combos[key] = combo
            row += 1
        grid.addWidget(_section(tr("Helper programs")), row, 0, 1, 3)
        row += 1
        self.helpers: dict[str, QLabel] = {}
        for program, label in HELPERS:
            grid.addWidget(QLabel(tr(label)), row, 0)
            status = QLabel()
            status.setObjectName("Muted")
            status.setWordWrap(True)
            status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(status, row, 1)
            self.helpers[program] = status
            if sys.platform == "win32" and not ops.external.available(program):
                button = QPushButton(tr("Install"))
                button.clicked.connect(lambda _c=False, p=program: install_helper(p))
                grid.addWidget(button, row, 2)
            row += 1
        self.refresh_helpers()
        self.layout_.addLayout(grid)

        about = QLabel(tr("Mandarine {} · free and open source (AGPL-3.0) · based on Astral Shift", __version__))
        about.setObjectName("Muted")
        about.setWordWrap(True)
        github = QPushButton("GitHub")
        github.clicked.connect(lambda: open_url(GITHUB))
        done = QPushButton(tr("Done"))
        done.setObjectName("Primary")
        done.clicked.connect(self.accept)
        foot = QHBoxLayout()
        foot.addWidget(about, 1)
        foot.addWidget(github)
        foot.addWidget(done)
        self.layout_.addLayout(foot)
        self.resize(540, 0)

    def _emit(self, key: str, value) -> None:
        self.settings.setValue(key, value)
        self.changed.emit(key, value)

    def _shortcut_done(self) -> None:
        self._emit("hotkey", self.shortcut.keySequence().toString(QKeySequence.SequenceFormat.PortableText))

    def _shortcut_default(self) -> None:
        self.shortcut.setKeySequence(QKeySequence(hotkey.DEFAULT))
        self._shortcut_done()

    def _gnome_shortcut(self) -> None:
        text = self.shortcut.keySequence().toString(QKeySequence.SequenceFormat.PortableText) or hotkey.DEFAULT
        try:
            desktop.add_gnome_shortcut(text)
            self.set_shortcut_status(tr("Shortcut added to GNOME: {}", text))
        except Exception as e:  # gsettings refused: say why
            self.set_shortcut_status(str(e))

    def refresh_helpers(self) -> None:
        for program, status in self.helpers.items():
            found = ops.external.find(program)
            status.setText(tr("Installed") if found else tr("Missing · {}", ops.external.install_hint(program)))

    def set_shortcut_status(self, text: str) -> None:
        self.shortcut_status.setText(text)
