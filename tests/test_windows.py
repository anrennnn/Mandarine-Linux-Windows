"""The Windows code paths, run anywhere with fake user32 and winreg."""
import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray, Qt

from mandarine import cli, i18n, ops
from mandarine.gui import app as A
from mandarine.gui import autostart, hotkey as H, integrations as I, selection, settings as S, watcher as W, win32


class FakeUser32:
    def __init__(self):
        self.down = set()
        self.swapped = 0
        self.cursor_ok = 1
        self.hwnd = 100
        self.cls = "CabinetWClass"
        self.foreground = 555
        self.hotkeys = {}
        self.accept = True

    def GetAsyncKeyState(self, vk):
        return -32768 if vk in self.down else 0

    def GetSystemMetrics(self, index):
        assert index == win32.SM_SWAPBUTTON
        return self.swapped

    def GetCursorPos(self, ptr):
        return self.cursor_ok

    def WindowFromPoint(self, pt):
        assert isinstance(pt, wintypes.POINT)
        return self.hwnd

    def GetAncestor(self, hwnd, flag):
        assert flag == win32.GA_ROOT
        return hwnd + 1

    def GetClassNameW(self, hwnd, buf, size):
        buf.value = self.cls
        return len(self.cls)

    def GetForegroundWindow(self):
        return self.foreground

    def RegisterHotKey(self, hwnd, ident, mods, vk):
        if self.accept:
            self.hotkeys[ident] = (mods, vk)
        return self.accept

    def UnregisterHotKey(self, hwnd, ident):
        self.hotkeys.pop(ident, None)
        return 1


class FakeKey:
    def __init__(self, reg, path):
        self.reg, self.path = reg, path

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def Close(self):
        pass


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    REG_SZ = 1

    def __init__(self):
        self.keys = {}

    def CreateKey(self, root, path):
        self.keys.setdefault(path, {})
        return FakeKey(self, path)

    def OpenKey(self, root, path):
        if path not in self.keys:
            raise FileNotFoundError(path)
        return FakeKey(self, path)

    def SetValueEx(self, key, name, reserved, kind, value):
        self.keys[key.path][name] = value

    def QueryValueEx(self, key, name):
        if name not in self.keys[key.path]:
            raise FileNotFoundError(name)
        return self.keys[key.path][name], self.REG_SZ

    def DeleteValue(self, key, name):
        if name not in self.keys[key.path]:
            raise FileNotFoundError(name)
        del self.keys[key.path][name]

    def DeleteKey(self, root, path):
        if any(k.startswith(path + "\\") for k in self.keys):
            raise PermissionError("has subkeys")  # like the real API
        if path not in self.keys:
            raise FileNotFoundError(path)
        del self.keys[path]


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    u, reg = FakeUser32(), FakeWinreg()
    monkeypatch.setattr(win32, "user32", lambda: u)
    monkeypatch.setattr(autostart, "_winreg", lambda: reg)
    monkeypatch.setattr(I, "_winreg", lambda: reg)
    return u, reg


# --- win32 helpers ---------------------------------------------------------------------

def test_win32_helpers():
    u = FakeUser32()
    assert win32.primary_button(u) == win32.VK_LBUTTON
    u.swapped = 1
    assert win32.primary_button(u) == win32.VK_RBUTTON
    u.down.add(win32.VK_SHIFT)
    assert win32.pressed(u, win32.VK_SHIFT) and not win32.pressed(u, win32.VK_CONTROL)
    assert win32.class_at_cursor(u) == "CabinetWClass"
    u.hwnd = 0
    assert win32.class_at_cursor(u) == ""
    u.cursor_ok = 0
    assert win32.class_at_cursor(u) == ""
    assert win32.foreground_window(u) == 555
    u.foreground = None
    assert win32.foreground_window(u) == 0


# --- Shift+drag -------------------------------------------------------------------------

def test_windows_drag_backend(windows):
    u, _ = windows
    b = W.WinBackend()
    assert b.loose and not b.drag_has_files()
    u.down = {win32.VK_LBUTTON, win32.VK_SHIFT, win32.VK_CONTROL}
    assert b.state() == W.State(True, True, 0, True)
    assert b.drag_has_files()  # pressed on Explorer
    u.cls = "Chrome_WidgetWin_1"
    assert b.state().button and b.drag_has_files()  # still the same press
    u.down = set()
    b.state()
    u.down = {win32.VK_LBUTTON}
    assert b.state() == W.State(True, False, 0, False)
    assert not b.drag_has_files()  # this press began in a browser


def test_windows_drag_fires_the_wheel(qapp, windows):
    from PySide6.QtCore import QPoint
    u, _ = windows
    w = W.DragWatcher(backend=W.WinBackend())
    fired = []
    w.shift_drag.connect(lambda pos, ctrl: fired.append(ctrl))
    u.down = {win32.VK_LBUTTON}
    w.poll(QPoint(0, 0))
    u.down = {win32.VK_LBUTTON, win32.VK_SHIFT}
    w.poll(QPoint(40, 0))
    assert fired == [False]


# --- hotkey -------------------------------------------------------------------------------

def test_win_key_codes():
    assert H.win_vk(Qt.Key.Key_A) == 0x41 and H.win_vk(Qt.Key.Key_7) == 0x37
    assert H.win_vk(Qt.Key.Key_F12) == 0x7B and H.win_vk(Qt.Key.Key_Space) == 0x20
    assert H.win_vk(Qt.Key.Key_Home) is None
    all_mods = (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.MetaModifier)
    assert H.win_modifiers(all_mods) == 0x4000 | 0xF
    assert H.win_modifiers(Qt.KeyboardModifier.NoModifier) == win32.MOD_NOREPEAT


def test_win_hotkey_registers_and_fires(qapp, windows):
    u, _ = windows
    fired = []
    hk = H.WinHotkey(lambda: fired.append(1))
    try:
        assert hk.register(*H.parse("Ctrl+Alt+Space"))
        assert u.hotkeys[H.WinHotkey.ID] == (win32.MOD_NOREPEAT | win32.MOD_CONTROL | win32.MOD_ALT, 0x20)
        assert not hk.register(*H.parse("Ctrl+Home"))  # no VK for it: nothing registered
        assert u.hotkeys == {}
        hk.register(*H.parse("Ctrl+Alt+Space"))
        msg = wintypes.MSG()
        msg.message, msg.wParam = win32.WM_HOTKEY, H.WinHotkey.ID
        assert hk.filter.nativeEventFilter(QByteArray(b"windows_generic_MSG"), ctypes.addressof(msg)) == (True, 0)
        assert fired == [1]
        msg.wParam = 7  # someone else's hotkey
        assert hk.filter.nativeEventFilter(QByteArray(b"windows_dispatcher_MSG"), ctypes.addressof(msg)) == (False, 0)
        assert hk.filter.nativeEventFilter(QByteArray(b"xcb_generic_event_t"), 0) == (False, 0)
        hk.unregister()
        hk.unregister()
        assert u.hotkeys == {}
        u.accept = False
        assert not hk.register(*H.parse("Ctrl+K"))
    finally:
        qapp.removeNativeEventFilter(hk.filter)


def test_make_hotkey_backend_on_windows(qapp, windows, monkeypatch):
    monkeypatch.setattr(H, "WinHotkey", lambda cb: "win")
    assert H.make_backend(lambda: None) == "win"

    def no_user32(cb):
        raise OSError
    monkeypatch.setattr(H, "WinHotkey", no_user32)
    assert H.make_backend(lambda: None) is None


# --- Explorer selection --------------------------------------------------------------------

def test_explorer_selection(windows, monkeypatch, jpg, tmp_path):
    u, _ = windows
    calls = []

    def run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, f"{jpg}\n{tmp_path / 'notes.xyz'}\n", "")
    monkeypatch.setattr(selection.subprocess, "run", run)
    assert selection.finder_selection() == [jpg]
    cmd, kw = calls[0]
    assert cmd[0] == "powershell" and "-eq 555" in cmd[-1] and kw["creationflags"] == 0x08000000
    u.foreground = 0
    assert selection.finder_selection() == []
    assert len(calls) == 1


# --- registry: autostart and right-click ---------------------------------------------------------

def test_windows_autostart(windows, monkeypatch):
    _, reg = windows
    monkeypatch.setattr(autostart, "_launch_command", lambda: [r"C:\Program Files\Mandarine\Mandarine.exe"])
    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    assert reg.keys[autostart.RUN_KEY]["Mandarine"] == r'"C:\Program Files\Mandarine\Mandarine.exe"'
    assert autostart.is_enabled()
    autostart.set_enabled(False)
    autostart.set_enabled(False)  # already gone
    assert not autostart.is_enabled()


def test_launch_command_prefers_the_windowed_exe(monkeypatch):
    monkeypatch.delenv("MANDARINE_LAUNCHER", raising=False)
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/apps/Mandarine/mandarine-cli.exe")
    assert autostart._launch_command() == [str(Path("/apps/Mandarine/Mandarine.exe"))]


def test_windows_context_menu(windows, monkeypatch):
    _, reg = windows
    monkeypatch.setattr(I, "wheel_command", lambda: [r"C:\Apps\Mandarine.exe", "wheel"])
    assert not I.is_installed()
    keys = I.install()
    assert len(keys) == len(I.EXTENSIONS)
    pdf = I.WIN_KEY.format(ext="pdf")
    assert reg.keys[pdf][""] == "Mandarine" and reg.keys[pdf]["MultiSelectModel"] == "Player"
    assert reg.keys[pdf + "\\command"][""] == r'C:\Apps\Mandarine.exe wheel "%1"'
    assert I.is_installed()
    I.set_installed(False)
    assert not I.is_installed() and reg.keys == {}
    I.uninstall()  # nothing left: no error


# --- helpers and the rest --------------------------------------------------------------------

def test_windows_helper_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ops.external.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("ProgramW6432", raising=False)
    assert ops.external.quiet()["creationflags"] == 0x08000000
    assert ops.external.install_hint("ffmpeg") == "winget install -e --id Gyan.FFmpeg"
    assert ops.external.find("ffmpeg") is None
    with pytest.raises(ops.MissingTool, match="winget install -e --id UB-Mannheim.TesseractOCR"):
        ops.external.require("tesseract")
    ff = tmp_path / "local/Microsoft/WinGet/Packages/Gyan.FFmpeg_x/ffmpeg-8.0-full_build/bin/ffmpeg.exe"
    ff.parent.mkdir(parents=True)
    ff.write_bytes(b"")
    assert ops.external.find("ffmpeg") == str(ff)
    lo = tmp_path / "pf/LibreOffice/program/soffice.exe"
    lo.parent.mkdir(parents=True)
    lo.write_bytes(b"")
    assert ops.external.find("soffice") == str(lo)
    assert any("Tesseract-OCR" in c for c in ops.external.windows_candidates("tesseract"))
    assert ops.external.windows_candidates("other")[0].endswith("other.exe")


def test_soffice_env_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    seen = {}

    def run(args, timeout, env):
        seen["env"] = env
        out = Path(args[args.index("--outdir") + 1])
        (out / "x.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(ops.external, "run", run)
    produced = ops.external.soffice_convert(tmp_path / "x.docx", "pdf")
    assert produced.name == "x.pdf" and "SAL_USE_VCLPLUGIN" not in seen["env"]


def test_reveal_in_explorer(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    calls = []
    monkeypatch.setattr(A.subprocess, "Popen", calls.append)
    A.reveal(tmp_path / "a.jpg")
    assert calls == [["explorer", f"/select,{tmp_path / 'a.jpg'}"]]


def test_settings_offer_winget_on_windows(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(S.ops.external, "find", lambda program: None)
    started = []
    monkeypatch.setattr(S.subprocess, "Popen", started.append)
    d = S.SettingsDialog(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat), "status", False)
    qtbot.addWidget(d)
    assert "winget install -e --id Gyan.FFmpeg" in d.helpers["ffmpeg"].text()
    [button] = [b for b in d.findChildren(S.QPushButton) if b.text() == "Install"][:1]
    button.click()
    assert started[0][:4] == ["cmd", "/c", "start", "winget"] and "Gyan.FFmpeg" in started[0]


def test_settings_show_installed_helpers(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    monkeypatch.setattr(S.ops.external, "find", lambda program: "/usr/bin/" + program)
    d = S.SettingsDialog(QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat), "status", False)
    qtbot.addWidget(d)
    assert d.helpers["tesseract"].text() == "Installed"


def test_cli_integrate(monkeypatch):
    from mandarine.gui import autostart as AS, integrations as IN
    calls = []
    monkeypatch.setattr(IN, "set_installed", lambda on: calls.append(("menu", on)))
    monkeypatch.setattr(AS, "set_enabled", lambda on: calls.append(("login", on)))
    assert cli.main(["integrate"]) == 0
    assert cli.main(["integrate", "--no-login"]) == 0
    assert cli.main(["integrate", "--remove", "--no-login"]) == 0
    assert calls == [("menu", True), ("login", True), ("menu", True), ("menu", False), ("login", False)]


def test_language_from_the_system_locale(monkeypatch):
    for var in ("MANDARINE_LANG", "LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: ("Spanish_Spain", "1252"))
    assert i18n.lang() == "es"
    monkeypatch.setattr(i18n.locale, "getlocale", lambda: (None, None))
    assert i18n.lang() == "en"
