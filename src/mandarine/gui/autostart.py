"""Open at login: a LaunchAgent on macOS, an XDG autostart entry on Linux,
the ``Run`` registry key on Windows."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from .. import APP_ID


def _launch_command() -> list[str]:
    launcher = os.environ.get("MANDARINE_LAUNCHER")  # set by /usr/bin/mandarine in the .deb
    if launcher:
        return [launcher]
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        # Inside an .app bundle, open the bundle so macOS treats it as the app.
        for parent in exe.parents:
            if parent.suffix == ".app":
                return ["/usr/bin/open", "-a", str(parent)]
        if exe.stem.lower() == "mandarine-cli":  # Windows console twin: launch the windowed app
            exe = exe.with_name("Mandarine.exe")
        appimage = os.environ.get("APPIMAGE")
        return [appimage] if appimage else [str(exe)]
    return [sys.executable, "-m", "mandarine"]


def entry_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config / "autostart" / "mandarine.desktop"


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _winreg():  # pragma: no cover - tests swap in a fake
    import winreg

    return winreg


def is_enabled() -> bool:
    if sys.platform == "win32":
        reg = _winreg()
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
                reg.QueryValueEx(key, "Mandarine")
            return True
        except OSError:
            return False
    return entry_path().exists()


def render() -> str:
    cmd = _launch_command()
    if sys.platform == "darwin":
        args = "".join(f"\n        <string>{a}</string>" for a in cmd)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{APP_ID}</string>
    <key>ProgramArguments</key>
    <array>{args}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    return (
        "[Desktop Entry]\nType=Application\nName=Mandarine\n"
        f"Exec={shlex.join(cmd)}\nIcon=mandarine\nX-GNOME-Autostart-enabled=true\nNoDisplay=true\n"
    )


def set_enabled(on: bool) -> None:
    if sys.platform == "win32":
        reg = _winreg()
        with reg.CreateKey(reg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if on:
                reg.SetValueEx(key, "Mandarine", 0, reg.REG_SZ, subprocess.list2cmdline(_launch_command()))
            else:
                try:
                    reg.DeleteValue(key, "Mandarine")
                except OSError:
                    pass
        return
    path = entry_path()
    if on:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render())
    elif path.exists():
        path.unlink()
