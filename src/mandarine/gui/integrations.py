"""Right-click menu entries in the file manager.

* macOS: a Finder Quick Action, "Mandarine", in ~/Library/Services.
* Linux: a Nautilus script, a Dolphin service menu, a Nemo action, a Caja
  script, a Thunar custom action and a PCManFM (file-manager-actions) entry,
  so it shows up on GNOME, KDE, Cinnamon, MATE, XFCE and LXQt alike.

Each entry runs ``mandarine wheel <files>``, which opens the wheel with
the selected files in the running app (or starts it).
"""
from __future__ import annotations

import os
import plistlib
import re
import shlex
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from .. import ops
from . import autostart

MENU_TITLE = "Mandarine"


def wheel_command() -> list[str]:
    """Command that opens the wheel; file paths are appended."""
    cmd = autostart._launch_command()
    if cmd[:2] == ["/usr/bin/open", "-a"]:  # inside an .app: call the binary itself
        cmd = [str(Path(sys.executable))]
    return cmd + ["wheel"]


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def thunar_file() -> Path:
    return _config_home() / "Thunar" / "uca.xml"


THUNAR_ID = "mandarine-wheel"

# Every file kind the wheel takes, for the menus that filter by type.
EXTENSIONS = sorted(e.lstrip(".") for exts in ops.files.KINDS.values() for e in exts)
MIME_TYPES = [
    "application/pdf", "image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff", "image/gif",
    "image/heic", "image/heif", "image/avif", "image/vnd.microsoft.icon",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text", "application/rtf", "text/plain", "text/markdown", "text/html",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.oasis.opendocument.spreadsheet", "text/csv",
    "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.presentation",
    "video/mp4", "video/quicktime", "video/x-matroska", "video/webm", "video/x-msvideo", "video/x-m4v",
    "video/x-ms-wmv", "video/x-flv", "video/3gpp",
    "audio/mpeg", "audio/x-wav", "audio/wav", "audio/ogg", "audio/flac", "audio/mp4", "audio/x-m4a", "audio/aac",
    "audio/opus", "audio/x-ms-wma",
]


def entry_paths() -> list[Path]:
    if sys.platform == "darwin":
        return [Path.home() / "Library" / "Services" / f"{MENU_TITLE}.workflow"]
    data = _data_home()
    return [
        data / "nautilus" / "scripts" / MENU_TITLE,
        data / "kio" / "servicemenus" / "mandarine.desktop",
        data / "nemo" / "actions" / "mandarine.nemo_action",
        _config_home() / "caja" / "scripts" / MENU_TITLE,
        data / "file-manager" / "actions" / "mandarine.desktop",
    ]


def is_installed() -> bool:
    return any(p.exists() for p in entry_paths()) or (sys.platform != "darwin" and _thunar_has_action())


# --- macOS Quick Action ------------------------------------------------------------

def _arg(name: str, default, uuid: int) -> dict:
    return {"default value": default, "name": name, "required": "0", "type": "0", "uuid": str(uuid)}


def quick_action_plists(command: str) -> tuple[dict, dict]:
    """(Info.plist, document.wflow) for a Finder Quick Action running ``command "$@"``."""
    info = {
        "NSServices": [{
            "NSBackgroundColorName": "background",
            "NSIconName": "NSActionTemplate",
            "NSMenuItem": {"default": MENU_TITLE},
            "NSMessage": "runWorkflowAsService",
            "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
            "NSSendFileTypes": ["com.adobe.pdf", "public.image"],
        }],
    }
    action = {
        "AMAccepts": {"Container": "List", "Optional": True, "Types": ["com.apple.cocoa.string"]},
        "AMActionVersion": "2.0.3",
        "AMApplication": ["Automator"],
        "AMParameterProperties": {k: {} for k in ("COMMAND_STRING", "CheckedForUserDefaultShell", "inputMethod", "shell", "source")},
        "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
        "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
        "ActionName": "Run Shell Script",
        "ActionParameters": {
            # Detach so Automator's gear does not spin while the app runs.
            "COMMAND_STRING": f'{command} "$@" >/dev/null 2>&1 &',
            "CheckedForUserDefaultShell": True,
            "inputMethod": 1,  # selected files as arguments
            "shell": "/bin/zsh",
            "source": "",
        },
        "BundleIdentifier": "com.apple.RunShellScript",
        "CFBundleVersion": "2.0.3",
        "CanShowSelectedItemsWhenRun": False,
        "CanShowWhenRun": True,
        "Category": ["AMCategoryUtilities"],
        "Class Name": "RunShellScriptAction",
        "InputUUID": "6E1B7C52-6E0B-4C1E-9A6B-0F2F3B9D1A01",
        "OutputUUID": "6E1B7C52-6E0B-4C1E-9A6B-0F2F3B9D1A02",
        "UUID": "6E1B7C52-6E0B-4C1E-9A6B-0F2F3B9D1A03",
        "UnlocalizedApplications": ["Automator"],
        "arguments": {
            "0": _arg("inputMethod", 0, 0),
            "1": _arg("CheckedForUserDefaultShell", False, 1),
            "2": _arg("source", "", 2),
            "3": _arg("COMMAND_STRING", "", 3),
            "4": _arg("shell", "/bin/sh", 4),
        },
        "conversionLabel": 0,
        "isViewVisible": 1,
        "location": "309.000000:305.000000",
        "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib",
    }
    doc = {
        "AMApplicationBuild": "534",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [{"action": action, "isViewVisible": 1}],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleIDsByPath": {},
            "applicationPaths": [],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 15,
            "processesInput": False,
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": False,
            "systemImageName": "NSActionTemplate",
            "useAutomaticInputType": False,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }
    return info, doc


# --- Linux ----------------------------------------------------------------------------

def nautilus_script(command: str) -> str:
    # Nautilus passes the selection as arguments.
    return f'#!/bin/sh\nexec {command} "$@"\n'


def dolphin_menu(command: str) -> str:
    return (
        "[Desktop Entry]\nType=Service\nX-KDE-ServiceTypes=KonqPopupMenu/Plugin\n"
        f"MimeType={';'.join(MIME_TYPES)};\n"
        "Actions=mandarine;\nX-KDE-Priority=TopLevel\n\n"
        f"[Desktop Action mandarine]\nName={MENU_TITLE}\nIcon=mandarine\nExec={command} %F\n"
    )


def nemo_action(command: str) -> str:
    return (
        "[Nemo Action]\n"
        f"Name={MENU_TITLE}\nComment=Open the Mandarine wheel\nExec={command} %F\n"
        f"Icon-Name=mandarine\nSelection=notnone\nExtensions={';'.join(EXTENSIONS)};\n"
    )


def fma_action(command: str) -> str:
    """FileManager-Actions entry, read by PCManFM and PCManFM-Qt."""
    return (
        "[Desktop Entry]\nType=Action\n"
        f"Name={MENU_TITLE}\nIcon=mandarine\nProfiles=files;\n\n"
        f"[X-Action-Profile files]\nMimeTypes={';'.join(MIME_TYPES)};\nExec={command} %F\n"
    )


def thunar_action(command: str) -> str:
    patterns = ";".join(f"*.{e}" for e in EXTENSIONS)
    return (
        f"<action>\n\t<icon>mandarine</icon>\n\t<name>{MENU_TITLE}</name>\n"
        f"\t<unique-id>{THUNAR_ID}</unique-id>\n\t<command>{escape(command)} %F</command>\n"
        f"\t<description>Open the Mandarine wheel</description>\n\t<patterns>{patterns}</patterns>\n"
        "\t<audio-files/>\n\t<image-files/>\n\t<other-files/>\n\t<text-files/>\n\t<video-files/>\n</action>\n"
    )


def _thunar_text() -> str:
    path = thunar_file()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _thunar_has_action() -> bool:
    return f"<unique-id>{THUNAR_ID}</unique-id>" in _thunar_text()


def _thunar_without_action(text: str) -> str:
    return re.sub(rf"<action>(?:(?!</action>).)*<unique-id>{THUNAR_ID}</unique-id>.*?</action>\n?", "", text,
                  flags=re.S)


def thunar_install(command: str) -> Path:
    path = thunar_file()
    text = _thunar_without_action(_thunar_text())
    if "</actions>" not in text:
        text = '<?xml version="1.0" encoding="UTF-8"?>\n<actions>\n</actions>\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("</actions>", thunar_action(command) + "</actions>", 1), encoding="utf-8")
    return path


def thunar_uninstall() -> None:
    if _thunar_has_action():
        thunar_file().write_text(_thunar_without_action(_thunar_text()), encoding="utf-8")


# --- install / remove -----------------------------------------------------------------------

def install() -> list[Path]:
    command = shlex.join(wheel_command())
    paths = entry_paths()
    if sys.platform == "darwin":
        bundle = paths[0] / "Contents"
        bundle.mkdir(parents=True, exist_ok=True)
        info, doc = quick_action_plists(command)
        (bundle / "Info.plist").write_bytes(plistlib.dumps(info))
        (bundle / "document.wflow").write_bytes(plistlib.dumps(doc))
        refresh_services()
        return paths
    writers = [nautilus_script, dolphin_menu, nemo_action, nautilus_script, fma_action]
    for path, write in zip(paths, writers):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(write(command))
        path.chmod(0o755)  # Nautilus, Caja and Dolphin only run executable entries
    return paths + [thunar_install(command)]


def uninstall() -> None:
    import shutil
    for p in entry_paths():
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    if sys.platform == "darwin":
        refresh_services()
    else:
        thunar_uninstall()


def refresh_services() -> None:
    """Ask macOS to re-read the Services menu now rather than at next login."""
    try:
        subprocess.run(["/System/Library/CoreServices/pbs", "-update"], timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def set_installed(on: bool) -> None:
    install() if on else uninstall()
