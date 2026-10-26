"""The floating bubble: a small always-on-top circle to drop files on.

Wayland does not let an app notice a drag elsewhere on screen, so this is how
the wheel opens there (and on any desktop, for people who prefer it): drag a
file onto the bubble and the wheel opens around it, still mid-drag. Click the
bubble to open the wheel for files you drop next; drag it to move it.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .. import APP_NAME
from . import icons
from .glass import shape_to
from .wheel import local_files

SIZE = 64


class Bubble(QWidget):
    entered = Signal(QPoint, list)  # global centre, [Path]: a drag arrived
    clicked = Signal(QPoint)  # global centre

    def __init__(self, settings: QSettings | None = None) -> None:
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
        self.setWindowTitle(f"{APP_NAME} bubble")
        self.settings = settings
        self.hot = False
        self._press: QPoint | None = None
        self._moved = False

    # --- placement --------------------------------------------------------------

    def default_pos(self) -> QPoint:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        return QPoint(screen.right() - SIZE - 12, screen.top() + screen.height() // 2 - SIZE // 2)

    def place(self) -> None:
        pos = self.settings.value("bubble/pos") if self.settings is not None else None
        pos = pos if isinstance(pos, QPoint) else self.default_pos()
        if QGuiApplication.screenAt(pos + QPoint(SIZE // 2, SIZE // 2)) is None:
            pos = self.default_pos()  # the monitor it was on is gone
        self.move(pos)
        disc = QPainterPath()
        disc.addEllipse(QRectF(1, 1, SIZE - 2, SIZE - 2))
        shape_to(self, disc)

    def centre(self) -> QPoint:
        return self.frameGeometry().center()

    # --- drag and drop --------------------------------------------------------

    def dragEnterEvent(self, e) -> None:
        files = local_files(e)
        if not files:
            e.ignore()
            return
        e.acceptProposedAction()
        self.hot = True
        self.update()
        self.entered.emit(self.centre(), files)

    def dragLeaveEvent(self, _e) -> None:
        self.hot = False
        self.update()

    def dropEvent(self, e) -> None:
        # The wheel normally covers the bubble before the drop; if not, open it for a click.
        self.hot = False
        self.update()
        files = local_files(e)
        if files:
            e.acceptProposedAction()
            self.entered.emit(self.centre(), files)

    # --- moving and clicking ------------------------------------------------------

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False

    def mouseMoveEvent(self, e) -> None:
        if self._press is not None:
            self.move(e.globalPosition().toPoint() - self._press)
            self._moved = True

    def mouseReleaseEvent(self, e) -> None:
        if self._press is None:
            return
        self._press = None
        if self._moved:
            if self.settings is not None:
                self.settings.setValue("bubble/pos", self.pos())
        else:
            self.clicked.emit(self.centre())

    # --- painting -------------------------------------------------------------

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(SIZE / 2, SIZE / 2)
        r = SIZE / 2 - 4
        g = QRadialGradient(c - QPointF(6, 8), r * 1.4)
        g.setColorAt(0.0, QColor("#ffb15c"))
        g.setColorAt(1.0, QColor("#e8442a") if self.hot else QColor("#f0702e"))
        p.setPen(QPen(QColor(255, 255, 255, 220), 2))
        p.setBrush(g)
        p.drawEllipse(c, r, r)
        p.drawImage(QRectF(c.x() - 15, c.y() - 15, 30, 30), icons.image("logo", 60, "#ffffff", 2.0))
        p.end()

