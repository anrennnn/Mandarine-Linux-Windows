"""Tray app: watches for Shift+drag, the shortcut and the bubble, shows the
wheel and runs the action off the UI thread."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QPoint, QRectF, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMenu, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from .. import APP_ID, APP_NAME, ops
from ..i18n import tr
from . import autostart, icons, integrations, selection
from .bubble import Bubble
from .dialogs import DIALOGS, MergeDialog
from .glass import blur_behind, paint_panel, rounded, shape_to
from .hotkey import DEFAULT as DEFAULT_HOTKEY, Hotkey
from .settings import GITHUB, SettingsDialog, open_url
from .single import Server, send_to_running
from .style import QSS
from .watcher import DragWatcher
from .wheel import Wheel, human_size

# Toast titles while working. Keys are wheel actions; "to:" conversions say their format.
TITLES = {
    "compress": "Compressing…", "rotate": "Rotating…", "mute": "Removing audio…", "resize": "Resizing to 720p…",
    "normalize": "Normalizing loudness…", "metadata": "Cleaning metadata…", "crop": "Cropping…",
    "background": "Adding background…", "redact": "Redacting…", "annotate": "Saving annotations…",
    "edit": "Saving edits…", "merge": "Merging…",
}
MEDIA = ("video", "audio")
GATHER_MS = 350


def reveal(path: Path) -> None:
    """Open the folder with ``path`` selected (FileManager1 D-Bus), else just the folder."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{path}"])
        return
    gdbus = shutil.which("gdbus")
    if gdbus:
        proc = subprocess.run(
            [gdbus, "call", "--session", "--dest", "org.freedesktop.FileManager1",
             "--object-path", "/org/freedesktop/FileManager1", "--method",
             "org.freedesktop.FileManager1.ShowItems", f"['{path.resolve().as_uri()}']", ""],
            capture_output=True, timeout=5)
        if proc.returncode == 0:
            return
    subprocess.Popen(["xdg-open", str(path.parent)])


def is_wayland() -> bool:
    return sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland"


# --- background work -----------------------------------------------------------------

class _Signals(QObject):
    progress = Signal(int, int)
    percent = Signal(int)
    done = Signal(list)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, fn: Callable[[Callable[[int, int], None]], list[Path]]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            self.signals.done.emit(self.fn(self.signals.progress.emit))
        except Exception as e:
            traceback.print_exc()
            self.signals.failed.emit(str(e) or e.__class__.__name__)


# --- toast ------------------------------------------------------------------------------

class Toast(QWidget):
    """Small glass status card: "Converting to JPG… / 1 of 1 saved"."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(2)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 600;")
        self.detail = QLabel()
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.detail, 1)
        self.show_btn = QPushButton(tr("Show"))
        self.show_btn.setObjectName("Chip")
        self.show_btn.clicked.connect(self._reveal)
        row.addWidget(self.show_btn)
        lay.addWidget(self.title)
        lay.addLayout(row)
        self.setFixedWidth(340)
        self.blurred = False
        self._path: Path | None = None
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.hide)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_panel(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, self.blurred)
        p.end()

    def _reveal(self) -> None:
        if self._path:
            reveal(self._path)
        self.hide()

    def show_message(self, title: str, detail: str = "", path: Path | None = None, sticky: bool = False) -> None:
        self.title.setText(title)
        self.detail.setText(detail)
        self._path = path
        self.show_btn.setVisible(path is not None)
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 18, screen.top() + 18)
        self.show()
        self.raise_()
        if not self.blurred:
            self.blurred = blur_behind(self, 14)
        shape_to(self, rounded(QRectF(self.rect()), 14))
        if sticky:
            self._hide.stop()
        else:
            self._hide.start(6000)


# --- app ----------------------------------------------------------------------------------

def tray_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if sys.platform == "darwin":
        p.drawImage(pm.rect(), icons.image("logo", 64, "#000000", 2.2))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f0702e"))
        p.drawEllipse(2, 2, 60, 60)
        p.drawImage(pm.rect().adjusted(10, 10, -10, -10), icons.image("logo", 44, "#ffffff", 2.2))
    p.end()
    ic = QIcon(pm)
    if sys.platform == "darwin":
        ic.setIsMask(True)  # template image: follows the light/dark menu bar
    return ic


class Mandarine(QObject):
    def __init__(self, app: QApplication, settings: QSettings | None = None, backend="auto", hotkey_backend="auto") -> None:
        super().__init__()
        self.app = app
        self.settings = settings if settings is not None else QSettings("Mandarine", "Mandarine")
        self.pool = QThreadPool.globalInstance()
        self.wheel = Wheel()
        self.wheel.dropped.connect(self.run_action)
        self.toast = Toast()
        self.watcher = DragWatcher(self, backend=backend)
        self.watcher.shift_drag.connect(self._on_shift_drag)
        self.watcher.released.connect(self.wheel.drag_released)
        self.hotkey = Hotkey(self, backend=hotkey_backend)
        self.hotkey.activated.connect(self.on_hotkey)
        self.bubble = Bubble(self.settings)
        self.bubble.entered.connect(self._on_bubble_drag)
        self.bubble.clicked.connect(lambda pos: self.wheel.popup(pos, sticky=True))
        self._open_dialogs: list = []
        # "Open with" / right-click on several files can start one process per
        # file (always on Windows): gather what arrives close together.
        self._incoming: list[Path] = []
        self._gather = QTimer(self)
        self._gather.setSingleShot(True)
        self._gather.setInterval(GATHER_MS)
        self._gather.timeout.connect(self._show_incoming)
        self._tasks: list[Task] = []
        self.settings_dialog: SettingsDialog | None = None
        self._load_settings()
        self.hotkey.set(str(self.settings.value("hotkey", DEFAULT_HOTKEY)))
        self._build_tray()
        self.watcher.start()

    # --- settings ---------------------------------------------------------------

    def _load_settings(self) -> None:
        self.wheel.first_mode = str(self.settings.value("wheel/first", "formats"))
        self.compress_level = str(self.settings.value("compress/level", "medium"))
        self.watcher.enabled = self.settings.value("enabled", True, type=bool)
        # The bubble is the only global trigger on Wayland, so it is on there by default.
        want_bubble = self.settings.value("bubble", not self.watcher.available, type=bool)
        if want_bubble and not self.bubble.isVisible():
            self.bubble.place()
            self.bubble.show()
        elif not want_bubble and self.bubble.isVisible():
            self.bubble.hide()

    def hotkey_status(self) -> str:
        if not self.hotkey.available:
            return tr("A global shortcut is not available in this session.")
        if not self.hotkey.text:
            return tr("No shortcut set.")
        if not self.hotkey.ok:
            return tr("That shortcut is taken by another app or not supported. Try another one.")
        return tr("Opens the wheel for the files you then drop on it.")

    def apply_setting(self, key: str, value) -> None:
        """Called by the settings window after it stored ``value``."""
        if key == "hotkey":
            self.hotkey.set(str(value))
            if self.settings_dialog:
                self.settings_dialog.set_shortcut_status(self.hotkey_status())
        elif key == "context_menu":
            integrations.set_installed(bool(value))
        elif key == "login":
            autostart.set_enabled(bool(value))
        self._load_settings()

    def open_settings(self) -> None:
        # The OS is the source of truth for these two.
        self.settings.setValue("login", autostart.is_enabled())
        self.settings.setValue("context_menu", integrations.is_installed())
        self.settings.setValue("bubble", self.bubble.isVisible())
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self.settings, self.hotkey_status(), is_wayland())
            self.settings_dialog.changed.connect(self.apply_setting)
            self.settings_dialog.finished.connect(self._settings_closed)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def _settings_closed(self, _result: int) -> None:
        self.settings_dialog.deleteLater()
        self.settings_dialog = None

    def first_run(self) -> None:
        """The first launch sets up the right-click menu and shows the settings once."""
        if self.settings.value("welcomed", False, type=bool):
            return
        self.settings.setValue("welcomed", True)
        # On Windows the installer asks about the right-click entry; the .deb has no such page.
        if sys.platform.startswith("linux") and not integrations.is_installed():
            integrations.install()
        self.open_settings()

    # --- tray -------------------------------------------------------------------

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        status = menu.addAction(
            tr("Hold Shift while dragging a file") if self.watcher.available
            else tr("Shift+drag is unavailable here: use the bubble or Show Wheel"))
        status.setEnabled(False)
        menu.addAction(icons.icon("logo"), tr("Show Wheel")).triggered.connect(lambda: self.show_wheel(sticky=True))
        menu.addAction(icons.icon("settings"), tr("Settings…")).triggered.connect(self.open_settings)
        menu.addSeparator()
        menu.addAction(icons.icon("globe"), tr("Mandarine on GitHub")).triggered.connect(lambda: open_url(GITHUB))
        menu.addSeparator()
        menu.addAction(tr("Quit")).triggered.connect(lambda: self.app.quit())
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self._menu = menu
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != "darwin":
            self.show_wheel(sticky=True)

    # --- wheel ---------------------------------------------------------------------

    def _on_shift_drag(self, pos: QPoint, ctrl: bool = False) -> None:
        self.wheel.popup(pos, tools=ctrl)

    def _on_bubble_drag(self, pos: QPoint, files: list[Path]) -> None:
        self.wheel.popup(pos, dragging=files)

    def wheel_pos(self) -> QPoint:
        # Under XWayland the cursor position is stale outside our windows: use the screen centre.
        if is_wayland():
            return QGuiApplication.primaryScreen().availableGeometry().center()
        return QCursor.pos()

    def show_wheel(self, sticky: bool = False, files: list[Path] | None = None) -> None:
        self.wheel.popup(self.wheel_pos(), sticky=sticky, files=files)

    def on_hotkey(self) -> None:
        self.show_wheel(sticky=True, files=selection.finder_selection() or None)

    def on_message(self, msg: str) -> None:
        parts = msg.split("\t")
        if parts[0] == "wheel":
            files = [Path(p) for p in parts[1:] if p and ops.is_supported(Path(p))]
            if not files:
                self.show_wheel(sticky=True)
                return
            self._incoming += [f for f in files if f not in self._incoming]
            self._gather.start()  # restarts while more files keep arriving
        elif parts[0] == "settings":
            self.open_settings()

    def _show_incoming(self) -> None:
        files, self._incoming = self._incoming, []
        if files:
            self.show_wheel(sticky=True, files=files)

    # --- actions ------------------------------------------------------------------

    def run_action(self, key: str, files: list[Path]) -> None:
        # Let the drop finish in the source app before any window appears.
        QTimer.singleShot(0, lambda: self._run(key, files))

    def _run(self, key: str, files: list[Path]) -> None:
        media = all(ops.kind(f) in MEDIA for f in files)
        if key == "merge":
            self._open_merge(files)
            return
        if key in DIALOGS and not media:
            for f in files:
                self._open_dialog(key, f)
            return
        if key.startswith("to:"):
            target = key[3:]
            title = tr("Converting to {}…", target.upper())

            def job(progress, f):
                return ops.convert(f, target, progress=progress)
        elif key == "compress":
            level = self.compress_level

            def job(progress, f):
                return [ops.compress(f, level, progress)]
        elif key == "rotate":
            def job(progress, f):
                return [ops.media.rotate(f, 90, progress) if ops.kind(f) == "video" else ops.rotate(f, 90)]
        elif key == "mute":
            def job(progress, f):
                return [ops.media.mute(f, progress)]
        elif key == "resize":
            def job(progress, f):
                return [ops.media.resize(f, 720, progress)]
        elif key == "normalize":
            def job(progress, f):
                return [ops.media.normalize(f, progress)]
        elif key == "metadata":
            def job(progress, f):
                return [ops.media.strip_metadata(f, progress)]
        else:
            return
        self._start(key, title if key.startswith("to:") else tr(TITLES[key]), files, job)

    def _show_dialog(self, key: str, dlg, files: list[Path]) -> None:
        self._open_dialogs.append(dlg)

        def finished(result: int) -> None:
            self._open_dialogs.remove(dlg)
            if result and dlg.job:
                job = dlg.job
                self._start(key, tr(TITLES[key]), files[:1], lambda progress, _f: job())
            dlg.deleteLater()

        dlg.finished.connect(finished)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _open_dialog(self, key: str, f: Path) -> None:
        try:
            dlg = DIALOGS[key](f)
        except Exception as e:
            self.toast.show_message(tr("Could not open {}", f.name), str(e))
            return
        self._show_dialog(key, dlg, [f])

    def _open_merge(self, files: list[Path]) -> None:
        self._show_dialog("merge", MergeDialog(files), files)

    def _start(self, key: str, title: str, files: list[Path], job) -> None:
        total = len(files)
        self.toast.show_message(title, tr("{} of {} saved", 0, total), sticky=True)
        outputs: list[Path] = []
        errors: list[str] = []
        task: Task

        def run_all(progress):
            for i, f in enumerate(files):
                def part(done: int, of: int, i=i) -> None:
                    if of:
                        task.signals.percent.emit(int((i + done / of) * 100 / total))
                try:
                    outputs.extend(job(part, f))
                except Exception as e:
                    errors.append(f"{f.name}: {e}")
                progress(i + 1, total)
            return outputs

        task = Task(run_all)
        task.signals.progress.connect(
            lambda i, n: self.toast.show_message(title, tr("{} of {} saved", i, n), sticky=True))
        task.signals.percent.connect(
            lambda pct: self.toast.show_message(title, tr("Working… {}%", min(pct, 99)), sticky=True))
        task.signals.done.connect(lambda outs: self._finish(key, title, files, outs, errors))
        task.signals.failed.connect(lambda msg: self.toast.show_message(tr("Something went wrong"), msg))
        self._tasks.append(task)  # keep the signals objects alive until done
        task.signals.done.connect(lambda _o: self._tasks.remove(task))
        task.signals.failed.connect(lambda _m: self._tasks.remove(task))
        self.pool.start(task)

    def _finish(self, key: str, title: str, files: list[Path], outs: list[Path], errors: list[str]) -> None:
        if errors and not outs:
            self.toast.show_message(tr("Nothing saved"), errors[0])
            return
        detail = tr("{} file saved" if len(outs) == 1 else "{} files saved", len(outs))
        if key == "compress" and len(files) == 1 and outs:
            before, after = files[0].stat().st_size, outs[0].stat().st_size
            saved = 100 - round(after * 100 / before) if before else 0
            detail = f"{human_size(before)} → {human_size(after)}" + (
                f" (-{saved}%)" if saved > 0 else f" ({tr('already optimal')})")
        if errors:
            detail += tr(", {} failed", len(errors))
        self.toast.show_message(tr("{} done", title.rstrip("…")), detail, path=outs[0] if outs else None)


def prefer_xwayland() -> None:
    """On Wayland, run through XWayland when it is there: only X11 lets a
    window (the wheel, the bubble) pick its own position on screen."""
    if is_wayland() and os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def run_app(files: list[Path] | None = None) -> int:
    message = "\t".join(["wheel", *map(str, files)]) if files else "settings"
    if send_to_running(message):
        return 0  # already running: the second launch opens the wheel (or the settings)
    prefer_xwayland()
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName("Mandarine")
    QApplication.setDesktopFileName(APP_ID)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)
    app.setWindowIcon(tray_icon())
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("mandarine: no system tray found; use the bubble or `mandarine wheel`", file=sys.stderr)
    core = Mandarine(app)
    server = Server(app)
    server.message.connect(core.on_message)
    server.listen()
    if files:
        QTimer.singleShot(300, lambda: core.on_message(message))
    elif os.environ.get("MANDARINE_SHOW_WHEEL"):
        QTimer.singleShot(300, lambda: core.show_wheel(sticky=True))
    else:
        QTimer.singleShot(600, core.first_run)
    return app.exec()
