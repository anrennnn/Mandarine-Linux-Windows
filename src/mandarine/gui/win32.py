"""Small Windows API layer (ctypes, no pywin32).

Everything that touches ``user32`` goes through the object ``user32()``
returns, so the tests can hand in a fake and run on any platform.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

VK_LBUTTON, VK_RBUTTON, VK_SHIFT, VK_CONTROL = 0x01, 0x02, 0x10, 0x11
SM_SWAPBUTTON = 23
GA_ROOT = 2
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

# Top-level window classes of File Explorer and of the desktop.
EXPLORER_CLASSES = {"CabinetWClass", "ExploreWClass", "Progman", "WorkerW"}


def user32():  # pragma: no cover - Windows only, exercised by the Windows CI job
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.GetAsyncKeyState.argtypes = [ctypes.c_int]
    u.GetAsyncKeyState.restype = ctypes.c_short
    u.GetSystemMetrics.argtypes = [ctypes.c_int]
    u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    u.WindowFromPoint.argtypes = [wintypes.POINT]
    u.WindowFromPoint.restype = wintypes.HWND
    u.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetAncestor.restype = wintypes.HWND
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetForegroundWindow.restype = wintypes.HWND
    u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    return u


def pressed(u, vk: int) -> bool:
    return bool(u.GetAsyncKeyState(vk) & 0x8000)


def primary_button(u) -> int:
    """VK of the primary mouse button (left, unless the buttons are swapped)."""
    return VK_RBUTTON if u.GetSystemMetrics(SM_SWAPBUTTON) else VK_LBUTTON


def class_at_cursor(u) -> str:
    """Window class of the top-level window under the mouse pointer."""
    pt = wintypes.POINT()
    if not u.GetCursorPos(ctypes.byref(pt)):
        return ""
    hwnd = u.WindowFromPoint(pt)
    if not hwnd:
        return ""
    root = u.GetAncestor(hwnd, GA_ROOT) or hwnd
    buf = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(root, buf, 256)
    return buf.value


def foreground_window(u) -> int:
    return int(u.GetForegroundWindow() or 0)
