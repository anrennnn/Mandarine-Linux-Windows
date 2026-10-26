#!/usr/bin/env python3
"""Render packaging/icon.svg into icon.png and the Linux hicolor sizes (and icon.icns on macOS)."""
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PK = Path(__file__).resolve().parent.parent / "packaging"
app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
renderer = QSvgRenderer(QByteArray((PK / "icon.svg").read_bytes()))


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return img


render(512).save(str(PK / "icon.png"))
for s in (16, 24, 32, 48, 64, 128, 256, 512):
    d = PK / "hicolor" / f"{s}x{s}" / "apps"
    d.mkdir(parents=True, exist_ok=True)
    render(s).save(str(d / "mandarine.png"))
scalable = PK / "hicolor" / "scalable" / "apps"
scalable.mkdir(parents=True, exist_ok=True)
(scalable / "mandarine.svg").write_bytes((PK / "icon.svg").read_bytes())
print("ok")
