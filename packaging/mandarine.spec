# -*- mode: python ; coding: utf-8 -*-
# Windows build (also runs on Linux, which is how CI checks it):
#   pyinstaller --noconfirm --distpath dist --workpath build/pyi packaging/mandarine.spec
# Produces dist/Mandarine/ with two programs sharing one runtime:
#   Mandarine.exe       the tray app (no console window)
#   mandarine-cli.exe   the same program for the terminal (convert, compress…)
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

ROOT = Path(SPECPATH).resolve().parent
PKG = ROOT / "src" / "mandarine"
VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', (PKG / "__init__.py").read_text()).group(1)
IS_WIN = sys.platform == "win32"
ICON = str(ROOT / "packaging" / "icon.ico")

# Qt modules the app never imports (it uses Core, Gui, Widgets, Network, Svg only).
EXCLUDES = [
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtDBus", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtConcurrent",
    "PySide6.QtPrintSupport", "PySide6.QtXml", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtUiTools", "PySide6.QtNetworkAuth", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "tkinter", "unittest", "pytest", "PyInstaller",
]

hidden = ["PIL.ImageFont", "PIL.ImageDraw", "PIL.ImageFilter", "PIL.ExifTags", "pillow_heif"]
# Imported lazily, so the analysis cannot see them.
if not IS_WIN:
    hidden += ["Xlib", "Xlib.display", "Xlib.ext", "Xlib.ext.record", "Xlib.protocol", "Xlib.support"]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=collect_dynamic_libs("pillow_heif"),
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

version = None
if IS_WIN:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )

    nums = tuple(int(n) for n in (VERSION.split(".") + ["0"] * 4)[:4])
    version = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "anrennnn"),
                StringStruct("FileDescription", "Mandarine"),
                StringStruct("FileVersion", VERSION),
                StringStruct("ProductName", "Mandarine"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("LegalCopyright", "AGPL-3.0-or-later. Based on Astral Shift."),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )


def program(name: str, console: bool):
    return EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=console,
        icon=ICON,
        version=version,
    )


coll = COLLECT(
    program("Mandarine", console=False),
    program("mandarine-cli", console=True),
    a.binaries, a.datas,
    strip=False, upx=False, name="Mandarine",
)
