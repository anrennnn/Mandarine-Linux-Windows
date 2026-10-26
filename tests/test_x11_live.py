"""Real X server checks, run in CI under Xvfb with xdotool (MANDARINE_LIVE_X11=1).

Elsewhere they skip: the mocked tests already cover every line, these prove
the X11 calls behave as assumed against a real server.
"""
import os
import shutil
import subprocess

import pytest
from PySide6.QtCore import Qt

pytestmark = pytest.mark.skipif(
    not (os.environ.get("MANDARINE_LIVE_X11") and os.environ.get("DISPLAY") and shutil.which("xdotool")),
    reason="needs MANDARINE_LIVE_X11=1, an X display and xdotool",
)


def xdotool(*args):
    subprocess.run(["xdotool", *args], check=True)


def test_pointer_and_shift_state():
    from mandarine.gui.watcher import X11Backend
    b = X11Backend()
    xdotool("keydown", "shift", "mousedown", "1")
    try:
        s = b.state()
        assert s.button and s.shift
    finally:
        xdotool("mouseup", "1", "keyup", "shift")
    s = b.state()
    assert not s.button and not s.shift


def test_global_hotkey_fires(qtbot):
    from mandarine.gui.hotkey import X11Hotkey
    fired = []
    hk = X11Hotkey(lambda: fired.append(1))
    assert hk.register(Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    xdotool("key", "ctrl+alt+space")
    qtbot.waitUntil(lambda: bool(fired), timeout=3000)
    hk.unregister()
