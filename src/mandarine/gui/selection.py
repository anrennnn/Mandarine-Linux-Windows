"""Files currently selected in the file manager, for the keyboard shortcut.

macOS asks once for permission to talk to Finder (Automation). On Windows,
the selection of the File Explorer window in front comes from the
Shell.Application COM object, through PowerShell. Linux file managers expose
no common API for this, so the shortcut opens an empty wheel that files can
be dropped on.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .. import ops

FINDER_SCRIPT = '''
set out to ""
tell application "Finder"
    repeat with f in (get selection)
        set out to out & POSIX path of (f as alias) & linefeed
    end repeat
end tell
return out
'''


EXPLORER_SCRIPT = (
    "$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "foreach ($w in (New-Object -ComObject Shell.Application).Windows()) "
    "{{ if ($w.HWND -eq {hwnd}) {{ foreach ($i in $w.Document.SelectedItems()) {{ $i.Path }} }} }}"
)


def _command() -> list[str] | None:
    if sys.platform == "darwin":
        return ["osascript", "-e", FINDER_SCRIPT]
    if sys.platform == "win32":
        from . import win32

        hwnd = win32.foreground_window(win32.user32())
        if not hwnd:
            return None
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", EXPLORER_SCRIPT.format(hwnd=hwnd)]
    return None


def finder_selection(timeout: float = 4.0) -> list[Path]:
    """Files selected in Finder / the File Explorer window in front."""
    cmd = _command()
    if cmd is None:
        return []
    try:
        done = subprocess.run(cmd, capture_output=True, timeout=timeout, **ops.external.quiet())
    except (OSError, subprocess.TimeoutExpired):
        return []
    if done.returncode != 0:
        return []
    paths = [Path(line) for line in done.stdout.splitlines() if line.strip()]
    return [p for p in paths if p.is_file() and ops.is_supported(p)]
