import subprocess

import pytest
from PySide6.QtCore import QPoint, QSettings

from mandarine import i18n
from mandarine.gui import bubble as B
from mandarine.gui import desktop as D


def test_current_desktop(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    assert D.current() == {"ubuntu", "gnome"}
    monkeypatch.setattr(D.shutil, "which", lambda name: "/usr/bin/gsettings")
    assert D.can_add_gnome_shortcut()
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert not D.can_add_gnome_shortcut()


def test_gnome_accel(qapp):
    assert D.gnome_accel("Ctrl+Alt+Space") == "<Control><Alt>space"
    assert D.gnome_accel("Meta+Shift+M") == "<Shift><Super>m"
    assert D.gnome_accel("Ctrl+F5") == "<Control>F5"
    with pytest.raises(ValueError):
        D.gnome_accel("")


def test_add_gnome_shortcut(qapp, monkeypatch):
    calls = []
    store = {"custom-keybindings": "@as []"}

    def run(args, **kw):
        calls.append(args[1:])
        if args[1] == "get":
            return subprocess.CompletedProcess(args, 0, store["custom-keybindings"] + "\n", "")
        if args[1:3] == ["set", D.SCHEMA]:
            store["custom-keybindings"] = args[4]
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(D.subprocess, "run", run)
    D.add_gnome_shortcut("Ctrl+Alt+Space")
    assert store["custom-keybindings"] == str([D.PATH])
    assert ["set", f"{D.SCHEMA}.custom-keybinding:{D.PATH}", "binding", "<Control><Alt>space"] in calls
    D.add_gnome_shortcut("Ctrl+Alt+Space")  # already listed: not added twice
    assert store["custom-keybindings"] == str([D.PATH])

    monkeypatch.setattr(D.subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(args, 1, "", "No such schema"))
    with pytest.raises(RuntimeError, match="No such schema"):
        D.add_gnome_shortcut("Ctrl+Alt+Space")


def test_i18n(monkeypatch):
    monkeypatch.setenv("MANDARINE_LANG", "es")
    assert i18n.tr("COMPRESS") == "COMPRIMIR"
    assert i18n.tr("{} of {} saved", 1, 3) == "1 de 3 guardados"
    assert i18n.tr("not translated") == "not translated"
    monkeypatch.setenv("MANDARINE_LANG", "en")
    assert i18n.tr("COMPRESS") == "COMPRESS"
    for var in ("MANDARINE_LANG", "LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        monkeypatch.delenv(var, raising=False)
    assert i18n.lang() == "en"
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    assert i18n.lang() == "es"


def test_bubble_drag_click_and_move(qtbot, tmp_path, jpg):
    from test_wheel_canvas import drag_enter, drop, mime, mouse
    from PySide6.QtCore import QMimeData, QPointF
    s = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    b = B.Bubble(s)
    qtbot.addWidget(b)
    b.place()
    b.show()
    assert b.pos() == b.default_pos()
    entered, clicked = [], []
    b.entered.connect(lambda pos, files: entered.append(files))
    b.clicked.connect(clicked.append)
    assert not drag_enter(b, QMimeData()).isAccepted()
    drag_enter(b, mime(jpg))
    assert b.hot and entered == [[jpg]]
    b.grab()
    b.dragLeaveEvent(None)
    assert not b.hot
    drop(b, mime(jpg), QPointF(10, 10))
    assert entered == [[jpg], [jpg]]
    drop(b, QMimeData(), QPointF(10, 10))
    assert len(entered) == 2

    c = QPointF(B.SIZE / 2, B.SIZE / 2)
    b.mousePressEvent(mouse("press", c))
    b.mouseReleaseEvent(mouse("release", c))
    assert len(clicked) == 1
    b.mouseReleaseEvent(mouse("release", c))  # no press: ignored
    b.mouseMoveEvent(mouse("move", c))  # no press: ignored
    start = b.pos()
    b.mousePressEvent(mouse("press", c))
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QMouseEvent
    target = QPointF(b.mapToGlobal(c.toPoint())) + QPointF(-40, -30)
    b.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, c, c, target, Qt.MouseButton.NoButton,
                                 Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    b.mouseReleaseEvent(mouse("release", c))
    assert len(clicked) == 1 and s.value("bubble/pos") == b.pos() != start
    b.mousePressEvent(mouse("press", c, Qt.MouseButton.RightButton))  # left button only

    s.setValue("bubble/pos", QPoint(-99999, -99999))  # its monitor is gone
    b.place()
    assert b.pos() == b.default_pos()
