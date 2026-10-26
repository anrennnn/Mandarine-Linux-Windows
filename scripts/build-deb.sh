#!/usr/bin/env bash
# Build dist/mandarine_<version>_amd64.deb
#
# The package carries its own Python (python-build-standalone, built against an
# old glibc) and the wheels it needs under /opt/mandarine, so one .deb installs
# on Debian 12+ and Ubuntu 22.04+ alike (Qt needs glibc 2.34). ffmpeg, LibreOffice and Tesseract come
# from the distribution (Recommends), found on PATH at run time.
#
# Needs: curl, dpkg-deb. Run from anywhere.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/mandarine/__init__.py)"
ARCH=amd64
PY_RELEASE="${PY_RELEASE:-20250115}"
PY_VERSION="${PY_VERSION:-3.12.8}"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_RELEASE}/cpython-${PY_VERSION}+${PY_RELEASE}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"

BUILD="$ROOT/build/deb"
STAGE="$BUILD/mandarine_${VERSION}_${ARCH}"
OPT="$STAGE/opt/mandarine"
CACHE="$ROOT/build/cache"
mkdir -p "$CACHE" "$ROOT/dist"
rm -rf "$STAGE"
mkdir -p "$OPT" "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/metainfo" \
         "$STAGE/usr/share/doc/mandarine"

echo "== Python $PY_VERSION"
TARBALL="$CACHE/$(basename "$PY_URL")"
[ -f "$TARBALL" ] || curl -fsSL -o "$TARBALL" "$PY_URL"
tar -xzf "$TARBALL" -C "$OPT"
PY="$OPT/python/bin/python3"

echo "== Wheels"
"$PY" -m pip install --quiet --no-warn-script-location --no-compile --disable-pip-version-check \
    "PySide6-Essentials>=6.7,<7" "pymupdf>=1.24.2,<2" "pillow>=11.3" "pillow-heif>=0.18" "python-xlib>=0.33"
"$PY" -m pip install --quiet --no-warn-script-location --no-compile --disable-pip-version-check --no-deps "$ROOT"

echo "== Trim"
SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
LIB="$(dirname "$SITE")"
rm -rf "$LIB"/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3} "$LIB"/config-* \
       "$OPT/python/share" "$OPT/python/include" "$OPT"/python/bin/{2to3*,idle3*,pydoc3*,pip*} \
       "$OPT/python/lib/libtcl"* "$OPT/python/lib/libtk"* "$OPT/python/lib/tcl"* "$OPT/python/lib/tk"* "$OPT/python/lib/Tix"* "$OPT/python/lib/itcl"* "$OPT/python/lib/thread"* \
       "$LIB"/lib-dynload/_tkinter* "$SITE"/pip "$SITE"/pip-*.dist-info
# Qt modules Mandarine never imports (it uses Core, Gui, Widgets, Network and Svg).
QT="$SITE/PySide6"
for m in Qml Quick QuickControls2 QuickWidgets QuickTest Pdf PdfWidgets Designer Help UiTools Sql Test \
         Concurrent DBus OpenGLWidgets PrintSupport Xml StateMachine SpatialAudio Multimedia MultimediaWidgets \
         Charts DataVisualization WebChannel WebSockets NetworkAuth Positioning Location Bluetooth Nfc \
         Sensors SerialPort RemoteObjects Scxml TextToSpeech HttpServer Graphs 3DCore; do
    rm -f "$QT"/Qt"$m".*.so "$QT"/Qt"$m".pyi
done
rm -f "$QT"/QtOpenGL.*.so "$QT"/QtOpenGL.pyi
rm -rf "$QT"/{Qt/qml,Qt/translations,typesystems,include,glue,scripts,support} \
       "$QT"/{designer,assistant,linguist,lupdate,lrelease,qmlformat,qmllint,qmlls,balsam,balsamui,svgtoqml,uic,rcc}* \
       "$QT"/Qt/lib/libQt6{Quick,Qml,Pdf,Designer,Help,ShaderTools,Sql,Test,Charts,Multimedia,3D,Location,Positioning,Graphs,DataVisualization,WebChannel,WebSockets,RemoteObjects,Scxml,Sensors,SerialPort,TextToSpeech,HttpServer,SpatialAudio,Bluetooth,Nfc,LanguageServer,JsonRpc,StateMachine,Labs,WaylandCompositor,Lottie,UiTools}* \
       "$QT"/Qt/plugins/{qmltooling,sqldrivers,designer,assetimporters,sceneparsers,renderers,multimedia,position,geoservices,canbus,sensors,texttospeech,webview,qmllint,scxmldatamodel,renderplugins}
find "$SITE" -depth -type d \( -name tests -o -name __pycache__ \) -prune -exec rm -rf {} +
# Console scripts point at the build path; the app starts through /usr/bin/mandarine.
find "$OPT/python/bin" -mindepth 1 ! -name python3 ! -name python3.12 -delete
find "$OPT" -name "*.dist-info" -type d -exec rm -rf {}/RECORD \; 2>/dev/null || true

echo "== Smoke test"
"$PY" -I -c "import mandarine.gui.app, mandarine.ops, PySide6.QtSvg, PySide6.QtNetwork, Xlib, pillow_heif; print('imports ok')"
QT_QPA_PLATFORM=offscreen "$PY" -I -c "
from PySide6.QtWidgets import QApplication; app = QApplication([])
from mandarine.gui.wheel import Wheel; w = Wheel(); w.grab(); print('qt ok')"
"$PY" -I -m compileall -q -j0 --invalidation-mode unchecked-hash "$OPT/python/lib" >/dev/null

echo "== Permissions"
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$OPT"/python/bin/python3*

echo "== Desktop files"
install -m 755 packaging/linux/mandarine "$STAGE/usr/bin/mandarine"
install -m 644 packaging/linux/io.github.anrennnn.Mandarine.desktop "$STAGE/usr/share/applications/"
install -m 644 packaging/linux/io.github.anrennnn.Mandarine.metainfo.xml "$STAGE/usr/share/metainfo/"
for d in packaging/hicolor/*/apps; do
    size="$(basename "$(dirname "$d")")"
    install -d "$STAGE/usr/share/icons/hicolor/$size/apps"
    install -m 644 "$d"/* "$STAGE/usr/share/icons/hicolor/$size/apps/"
done
install -m 644 LICENSE "$STAGE/usr/share/doc/mandarine/copyright"
cat > "$STAGE/usr/share/doc/mandarine/README" <<TXT
Mandarine $VERSION - https://github.com/anrennnn/Mandarine-Linux-Windows
Based on Astral Shift by Taoufik Jabbari (https://github.com/jtaoufik/astral-shift), AGPL-3.0-or-later.
Bundles CPython (PSF license), Qt for Python / PySide6 (LGPL-3.0), PyMuPDF (AGPL-3.0),
Pillow (MIT-CMU), pillow-heif (BSD-3-Clause, libheif LGPL-3.0) and python-xlib (LGPL-2.1).
TXT

printf 'mandarine (%s) stable; urgency=medium\n\n  * Release %s.\n\n -- anrennnn <anrennnn@users.noreply.github.com>  %s\n' \
    "$VERSION" "$VERSION" "$(date -R)" | gzip -9n > "$STAGE/usr/share/doc/mandarine/changelog.gz"

echo "== Control"
SIZE_KB="$(du -sk "$STAGE" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<CTRL
Package: mandarine
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: anrennnn <anrennnn@users.noreply.github.com>
Installed-Size: $SIZE_KB
Depends: libc6 (>= 2.34), libegl1, libgl1, libfontconfig1, libfreetype6, libdbus-1-3, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libx11-xcb1, xdg-utils
Recommends: ffmpeg, libreoffice-writer, tesseract-ocr, tesseract-ocr-spa, tesseract-ocr-eng, libglib2.0-bin
Suggests: libreoffice-calc, libreoffice-impress
Homepage: https://github.com/anrennnn/Mandarine-Linux-Windows
Description: radial wheel to convert and edit files while you drag them
 Hold Shift while dragging a file and a wheel opens around the cursor: drop it
 on a format to convert it (PDF to Word, images to PDF/WebP/AVIF/HEIC, video to
 MP4/GIF/MP3, documents through LibreOffice), or on a tool to compress, crop,
 redact, annotate, strip metadata or put it on a background. A floating bubble
 does the same on Wayland, and the file manager's right-click menu opens it too.
 Everything runs locally; no file is uploaded.
CTRL
cat > "$STAGE/DEBIAN/postrm" <<'SH'
#!/bin/sh
set -e
# Python byte-code written at run time, if any.
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    rm -rf /opt/mandarine
fi
SH
chmod 755 "$STAGE/DEBIAN/postrm"

echo "== dpkg-deb"
OUT="$ROOT/dist/mandarine_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$OUT" >/dev/null
ls -lh "$OUT"
