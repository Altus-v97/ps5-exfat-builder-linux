#!/usr/bin/env bash
# Turns dist/exfat-image-builder (from ./build_linux.sh) into release packages:
#   dist/exfat-image-builder-<ver>-linux-x86_64.tar.gz   any distro (install.sh, no root)
#   dist/exfat-image-builder_<ver>_amd64.deb             Debian/Ubuntu/Mint (needs dpkg-deb)
# Usually run via ./build_linux.sh --package.
set -euo pipefail
cd "$(dirname "$0")/../.."

APP=exfat-image-builder
VER=$(sed -n "s/^APP_VERSION = '\(.*\)'$/\1/p" exfat_builder.py)
VPY="${VPY:-.venv/bin/python}"
BIN="dist/$APP"
HERE=packaging/linux
[ -x "$BIN" ] || { echo "ERROR: $BIN not found - run ./build_linux.sh first." >&2; exit 1; }

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# 128px menu icon from the 16px controller.ico (nearest-neighbour keeps it crisp).
"$VPY" -c "
from PIL import Image
Image.open('controller.ico').convert('RGBA').resize((128, 128), Image.NEAREST).save('$STAGE/$APP.png')
"

# The app reads assets/whatsnew/*.png and CHANGELOG.md from next to its executable.
payload() {
    mkdir -p "$1/assets/whatsnew"
    install -m 755 "$BIN" "$1/$APP"
    cp assets/whatsnew/*.png "$1/assets/whatsnew/"
    if [ -f "CHANGELOG_v$VER.md" ]; then cp "CHANGELOG_v$VER.md" "$1/CHANGELOG.md"; fi
}

# ── tar.gz ──
TDIR="$STAGE/$APP-$VER"
payload "$TDIR"
cp "$HERE/$APP.desktop" "$STAGE/$APP.png" README_LINUX.md "$TDIR/"
install -m 755 "$HERE/install.sh" "$TDIR/install.sh"
TAR="dist/$APP-$VER-linux-x86_64.tar.gz"
tar -C "$STAGE" -czf "$TAR" "$APP-$VER"
echo "Built $TAR"

# ── .deb ──
if command -v dpkg-deb >/dev/null; then
    ROOT="$STAGE/deb"
    payload "$ROOT/opt/$APP"
    mkdir -p "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
             "$ROOT/usr/share/icons/hicolor/128x128/apps" "$ROOT/DEBIAN"
    printf '#!/bin/sh\nexec /opt/%s/%s "$@"\n' "$APP" "$APP" > "$ROOT/usr/bin/$APP"
    chmod 755 "$ROOT/usr/bin/$APP"
    install -m 644 "$HERE/$APP.desktop" "$ROOT/usr/share/applications/"
    install -m 644 "$STAGE/$APP.png" "$ROOT/usr/share/icons/hicolor/128x128/apps/"
    GLIBC=$(ldd --version | head -1 | grep -oE '[0-9]+\.[0-9]+$')
    cat > "$ROOT/DEBIAN/control" <<EOF
Package: $APP
Version: $VER
Architecture: amd64
Maintainer: exFAT Image Builder Linux port <noreply@users.noreply.github.com>
Depends: libc6 (>= $GLIBC), libx11-6, libxext6, libxft2, libxss1, libfontconfig1, libfreetype6, exfatprogs
Recommends: udisks2 | exfat-fuse, libxcursor1, fonts-noto-color-emoji
Suggests: dotnet-runtime-8.0
Section: utils
Priority: optional
Installed-Size: $(du -sk "$ROOT" | cut -f1)
Homepage: https://github.com/Altus-v97/ps5-exfat-builder-linux
Description: Build, edit and convert PS5 game images
 Builds exFAT, FFPKG (UFS2) and compressed FFPFSC images from your own
 PS5 game dumps, with a queue, backport tools, FTP and payload sender.
 FFPKG builds need the .NET 8 runtime (dotnet-runtime-8.0).
EOF
    DEB="dist/${APP}_${VER}_amd64.deb"
    dpkg-deb --root-owner-group --build "$ROOT" "$DEB" >/dev/null
    echo "Built $DEB"
else
    echo "Skipping .deb - dpkg-deb not found."
fi
(cd dist && sha256sum "$APP-$VER-linux-x86_64.tar.gz" ${APP}_*_amd64.deb 2>/dev/null > SHA256SUMS || true)
