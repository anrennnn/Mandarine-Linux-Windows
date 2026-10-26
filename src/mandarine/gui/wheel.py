"""The radial wheel: a translucent, focus-less window that pops up around the
cursor and takes the dropped file(s).

It has two rings, like Tangerine:

* **formats**: one wedge per target format of the dragged file (PDF -> DOCX,
  JPG, PNG, TXT…). The centre shows the file size and switches to tools when
  you rest on it.
* **tools**: compress, crop, background, redact… for PDFs and images; compress,
  mute, rotate, 720p, loudness and clean for video; compress, loudness and
  clean for audio. The centre annotates one file or merges several.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QFont, QGuiApplication, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from .. import APP_NAME, ops
from ..i18n import tr
from . import icons
from .glass import blur_behind, rounded, shape_to


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    icon: str = ""

    @property
    def target(self) -> str | None:
        """``"docx"`` for a format wedge (key ``"to:docx"``), else None."""
        return self.key[3:] if self.key.startswith("to:") else None


def fmt(target: str) -> Action:
    return Action(f"to:{target}", target.upper(), "")


# Tools for PDFs and images, clockwise from the top.
RING = [
    Action("compress", "COMPRESS", "compress"),
    Action("metadata", "METADATA", "metadata"),
    Action("edit", "EDIT", "edit"),
    Action("rotate", "ROTATE", "rotate"),
    Action("background", "ADD BG", "background"),
    Action("crop", "CROP", "crop"),
    Action("redact", "REDACT", "redact"),
]
VIDEO_RING = [
    Action("compress", "COMPRESS", "compress"),
    Action("mute", "MUTE", "mute"),
    Action("rotate", "ROTATE", "rotate"),
    Action("resize", "720P", "resize"),
    Action("normalize", "LOUDNESS", "volume"),
    Action("metadata", "CLEAN", "metadata"),
]
AUDIO_RING = [
    Action("compress", "COMPRESS", "compress"),
    Action("normalize", "LOUDNESS", "volume"),
    Action("metadata", "CLEAN", "metadata"),
]
CENTER = Action("annotate", "ANNOTATE", "annotate")
MERGE = Action("merge", "MERGE", "merge")  # the centre when several files are dropped
TOOLS = Action("tools", "TOOLS", "tools")  # centre of the formats ring
FORMATS = Action("formats", "FORMATS", "formats")  # centre of a media tools ring

SIZE = 380
OUTER = 176
INNER = 60
GAP_DEG = 2.4
SWITCH_MS = 450  # resting on a mode-switch centre this long flips the ring


def accept_copy(event) -> bool:
    """Accept a drag or drop as a *copy*, never a move.

    Holding Shift makes Explorer, Nautilus and Dolphin propose a move, and a
    source that sees its move accepted may delete the original. Mandarine only
    reads the file, so it answers "copy" (or "link"), and refuses a move-only drag.
    """
    for action in (Qt.DropAction.CopyAction, Qt.DropAction.LinkAction):
        if event.possibleActions() & action:
            event.setDropAction(action)
            event.accept()
            return True
    event.ignore()
    return False


def local_files(event) -> list[Path]:
    md = event.mimeData()
    if not md.hasUrls():
        return []
    return [Path(u.toLocalFile()) for u in md.urls() if u.isLocalFile() and ops.is_supported(Path(u.toLocalFile()))]


def tool_ring(files: list[Path]) -> list[Action]:
    kinds = {ops.kind(f) for f in files}
    if kinds <= {"pdf", "image"}:
        return list(RING)
    if kinds == {"video"}:
        return list(VIDEO_RING)
    if kinds <= {"video", "audio"}:
        return list(AUDIO_RING)
    return []  # documents: formats only


def format_ring(files: list[Path]) -> list[Action]:
    return [fmt(t) for t in ops.common_targets(files)]


def center_for(mode: str, files: list[Path]) -> Action | None:
    if not files:
        return None
    if mode == "formats":
        return TOOLS if tool_ring(files) else None
    if {ops.kind(f) for f in files} <= {"pdf", "image"}:
        return MERGE if len(files) > 1 else CENTER
    return FORMATS


def ring_for(mode: str, files: list[Path]) -> list[Action]:
    if not files:
        return []
    return format_ring(files) if mode == "formats" else tool_ring(files)


def hit_test(p: QPointF, center: QPointF, ring: list[Action], centre: Action | None) -> Action | None:
    """Which action sits under ``p`` (widget coordinates)."""
    dx, dy = p.x() - center.x(), p.y() - center.y()
    r = math.hypot(dx, dy)
    if r <= INNER:
        return centre
    if r > OUTER + 6 or not ring:
        return None
    step = 360 / len(ring)
    # 0 deg = top, clockwise; wedge 0 is centred on the top.
    ang = (math.degrees(math.atan2(dx, -dy)) + 360 + step / 2) % 360
    return ring[int(ang // step) % len(ring)]


def human_size(n: float) -> str:
    unit = "B"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            break
        n /= 1024
    return f"{n:.0f} B" if unit == "B" else f"{n:.1f} {unit}"


class Wheel(QWidget):
    dropped = Signal(str, list)  # action key, [Path]
    dismissed = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setFixedSize(SIZE, SIZE)
        self.setWindowTitle(APP_NAME)
        self.hover: Action | None = None
        self.hint = ""  # e.g. "Page 001.jpg", shown under the wheel
        self.first_mode = "formats"
        self.mode = "formats"
        self._files: list[Path] = []
        self._preset = False
        self._opacity = 0.0
        self._fade = QTimer(self)
        self._fade.setInterval(12)
        self._fade.timeout.connect(self._step_fade)
        self._switch = QTimer(self)
        self._switch.setSingleShot(True)
        self._switch.setInterval(SWITCH_MS)
        self._switch.timeout.connect(self._switch_now)
        self._sticky = False  # opened from the tray: stay until Esc / click outside
        self._hide_on_leave = False  # opened by the bubble: no global release signal to close us
        self._drag_inside = False
        self.blurred = False
        self.setMouseTracking(True)

    # --- state ------------------------------------------------------------------

    @property
    def files(self) -> list[Path]:
        return list(self._files)

    @property
    def ring(self) -> list[Action]:
        return ring_for(self.mode, self._files)

    @property
    def centre(self) -> Action | None:
        return center_for(self.mode, self._files)

    def set_files(self, files: list[Path]) -> None:
        self._files = list(files)
        # Documents have no tools ring: always show their formats.
        if self.mode == "tools" and not tool_ring(self._files):
            self.mode = "formats"
        self.update()

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            self.hover = None
            self.hint = ""
            self.update()

    def _switch_now(self) -> None:
        if self.hover in (TOOLS, FORMATS):
            self.set_mode("tools" if self.hover == TOOLS else "formats")

    # --- showing --------------------------------------------------------------

    def popup(self, global_pos: QPoint, sticky: bool = False, files: list[Path] | None = None,
              tools: bool = False, dragging: list[Path] | None = None) -> None:
        """Show at ``global_pos``. With ``files``, a click on a wedge acts on them.

        ``tools`` flips the first ring (Ctrl held when the drag started).
        ``dragging`` are the files of a drag in progress (from the bubble): the
        wheel shows their ring at once and closes if the drag leaves it.
        """
        self._sticky = sticky or bool(files)
        self._preset = bool(files)
        self._hide_on_leave = dragging is not None
        self._drag_inside = False
        self.mode = self.first_mode
        if tools:
            self.mode = "formats" if self.first_mode == "tools" else "tools"
        self.set_files(files or dragging or [])
        self.hover = None
        self.hint = ""
        target = QGuiApplication.screenAt(global_pos)  # multi-monitor: the screen under the cursor
        screen = target.availableGeometry() if target else None
        x, y = global_pos.x() - SIZE // 2, global_pos.y() - SIZE // 2
        if screen is not None:
            x = max(screen.left(), min(x, screen.right() - SIZE))
            y = max(screen.top(), min(y, screen.bottom() - SIZE))
        self.move(x, y)
        self._opacity = 0.0
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade.start()
        if not self.blurred:
            ring = OUTER + 10
            self.blurred = blur_behind(self, ring, SIZE / 2 - ring)
        disc = QPainterPath()
        disc.addEllipse(QPointF(SIZE / 2, SIZE / 2), OUTER + 10, OUTER + 10)
        shape_to(self, disc.united(rounded(QRectF(10, SIZE - 28, SIZE - 20, 26), 6)))  # disc + name pill
        if self._sticky:
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
            self.show()
            self.activateWindow()

    def _step_fade(self) -> None:
        self._opacity = min(1.0, self._opacity + 0.12)
        self.setWindowOpacity(self._opacity)
        if self._opacity >= 1.0:
            self._fade.stop()

    def dismiss(self) -> None:
        self._switch.stop()
        if self.isVisible():
            self.hide()
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            self.dismissed.emit()

    def drag_released(self) -> None:
        """Mouse came up. If the drop landed on us, dropEvent already ran."""
        if not self._sticky:
            QTimer.singleShot(120, self.dismiss)

    # --- hints ------------------------------------------------------------------

    def _hint_for(self, action: Action | None) -> str:
        if not action or not self._files:
            return ""
        f = self._files[0]
        extra = f" +{len(self._files) - 1}" if len(self._files) > 1 else ""
        if action.key == "merge":
            return f"{f.stem} Merged.pdf"
        if action.target:
            return f"{f.stem}.{action.target}{extra}"
        return f.name + extra

    # --- drag and drop --------------------------------------------------------

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        files = local_files(e)
        if files:
            self._drag_inside = True
            self.set_files(files)
            accept_copy(e)
        else:
            e.ignore()

    def _hit(self, pos: QPointF) -> Action | None:
        return hit_test(pos, QPointF(SIZE / 2, SIZE / 2), self.ring, self.centre)

    def _set_hover(self, action: Action | None) -> None:
        if action != self.hover:
            self.hover = action
            self.hint = self._hint_for(action)
            if action in (TOOLS, FORMATS):
                self._switch.start()
            else:
                self._switch.stop()
            self.update()

    def dragMoveEvent(self, e: QDragMoveEvent) -> None:
        action = self._hit(e.position())
        self._set_hover(action)
        if action:
            accept_copy(e)
        else:
            e.ignore()

    def dragLeaveEvent(self, e) -> None:
        self._drag_inside = False
        self._set_hover(None)
        if self._hide_on_leave:
            QTimer.singleShot(400, self._leave_check)

    def _leave_check(self) -> None:
        if not self._drag_inside and not self._sticky:
            self.dismiss()

    def dropEvent(self, e: QDropEvent) -> None:
        files = local_files(e)
        self.set_files(files)
        action = self._hit(e.position())
        if action in (TOOLS, FORMATS):
            # Dropped on the switch before it flipped: keep the wheel for a click.
            self._switch_now()
            self._preset = self._sticky = True
            accept_copy(e)
            return
        if action and files:
            accept_copy(e)
            self.dropped.emit(action.key, files)
        self.dismiss()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.dismiss()
        elif e.key() == Qt.Key.Key_Tab and tool_ring(self._files):
            self.set_mode("tools" if self.mode == "formats" else "formats")

    def mouseMoveEvent(self, e) -> None:
        if self._preset:
            self._set_hover(self._hit(e.position()))

    def mousePressEvent(self, e) -> None:
        action = self._hit(e.position())
        if action is None:
            pos = e.position()
            if math.hypot(pos.x() - SIZE / 2, pos.y() - SIZE / 2) > OUTER + 6:
                self.dismiss()  # a click outside the disc closes; an empty spot on it does not
        elif action in (TOOLS, FORMATS):
            self.set_mode("tools" if action == TOOLS else "formats")
        elif self._preset:
            files = list(self._files)
            self.dismiss()
            self.dropped.emit(action.key, files)

    def focusOutEvent(self, e) -> None:
        if self._sticky:
            self.dismiss()

    # --- painting -------------------------------------------------------------

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(SIZE / 2, SIZE / 2)

        # Soft glass disc.
        glow = QRadialGradient(c, OUTER + 10)
        glow.setColorAt(0.0, QColor(255, 255, 255, 120))
        glow.setColorAt(0.85, QColor(255, 236, 225, 90 if self.blurred else 150))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, OUTER + 10, OUTER + 10)
        p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
        p.setBrush(QColor(255, 244, 236, 70))
        p.drawEllipse(c, OUTER + 4, OUTER + 4)

        label_font = QFont()
        label_font.setPixelSize(10)
        label_font.setBold(True)
        label_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        format_font = QFont()
        format_font.setPixelSize(17)
        format_font.setBold(True)
        format_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)

        ring = self.ring
        inner_r = INNER + 6
        if not ring:
            # Files not known yet (the drag has not entered): an empty ring.
            path = QPainterPath()
            path.addEllipse(c, OUTER, OUTER)
            path.addEllipse(c, inner_r, inner_r)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1))
            p.setBrush(QColor(255, 214, 190, 160))
            p.drawPath(path)
            p.setFont(label_font)
            p.setPen(QColor("#4a2c22"))
            p.drawText(QRectF(c.x() - 80, c.y() - OUTER + 40, 160, 20), Qt.AlignmentFlag.AlignCenter, tr("Drop here"))
        step = 360 / len(ring) if ring else 0
        for i, action in enumerate(ring):
            start = 90 - (i * step - step / 2) - GAP_DEG / 2  # Qt: 0 deg = 3 o'clock, counter-clockwise
            span = -(step - GAP_DEG)
            path = QPainterPath()
            outer = QRectF(c.x() - OUTER, c.y() - OUTER, 2 * OUTER, 2 * OUTER)
            inner = QRectF(c.x() - inner_r, c.y() - inner_r, 2 * inner_r, 2 * inner_r)
            path.arcMoveTo(outer, start)
            path.arcTo(outer, start, span)
            path.arcTo(inner, start + span, -span)
            path.closeSubpath()
            hovered = action == self.hover
            p.setPen(QPen(QColor(255, 255, 255, 200), 1))
            p.setBrush(QColor(232, 68, 40, 235) if hovered else QColor(255, 214, 190, 215))
            p.drawPath(path)

            mid = math.radians(i * step)
            r = (OUTER + inner_r) / 2
            pos = QPointF(c.x() + r * math.sin(mid), c.y() - r * math.cos(mid))
            color = "#ffffff" if hovered else "#4a2c22"
            p.setPen(QColor(color))
            if action.target:
                p.setFont(format_font)
                p.drawText(QRectF(pos.x() - 45, pos.y() - 12, 90, 24), Qt.AlignmentFlag.AlignCenter, action.label)
            else:
                p.drawImage(QRectF(pos.x() - 11, pos.y() - 20, 22, 22), icons.image(action.icon, 44, color, 1.9))
                p.setFont(label_font)
                p.drawText(QRectF(pos.x() - 50, pos.y() + 4, 100, 14), Qt.AlignmentFlag.AlignCenter, tr(action.label))

        # Centre: switch rings, annotate one file or merge several.
        centre = self.centre
        hovered = centre is not None and self.hover == centre
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.2))
        p.setBrush(QColor(232, 68, 40, 240) if hovered else QColor(255, 236, 224, 235))
        p.drawEllipse(c, INNER, INNER)
        color = "#ffffff" if hovered else "#4a2c22"
        if centre is not None:
            p.drawImage(QRectF(c.x() - 11, c.y() - 26, 22, 22), icons.image(centre.icon, 44, color, 1.9))
            small = QFont(label_font)
            small.setPixelSize(9 if len(tr(centre.label)) > 9 else 10)
            p.setFont(small)
            p.setPen(QColor(color))
            p.drawText(QRectF(c.x() - 56, c.y() - 2, 112, 14), Qt.AlignmentFlag.AlignCenter, tr(centre.label))
        if self._files:
            size = sum(f.stat().st_size for f in self._files if f.exists())
            f = QFont()
            f.setPixelSize(12 if centre is None else 10)
            f.setBold(centre is None)
            p.setFont(f)
            p.setPen(QColor(color))
            y = c.y() - 8 if centre is None else c.y() + 13
            p.drawText(QRectF(c.x() - 50, y, 100, 16), Qt.AlignmentFlag.AlignCenter, human_size(size))

        # File-name pill under the wheel, like the result's name.
        if self.hint:
            f = QFont()
            f.setPixelSize(12)
            f.setBold(True)
            p.setFont(f)
            w = min(SIZE - 20, p.fontMetrics().horizontalAdvance(self.hint) + 18)
            rect = QRectF(c.x() - w / 2, SIZE - 26, w, 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(38, 99, 235, 235))
            p.drawRoundedRect(rect, 6, 6)
            p.setPen(QColor("white"))
            text = p.fontMetrics().elidedText(self.hint, Qt.TextElideMode.ElideMiddle, int(w - 12))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.end()
