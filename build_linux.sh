#!/usr/bin/env bash
# Linux counterpart of build.bat: builds dist/exfat-image-builder, a
# single-file binary. Run from the repo root. Uses a local .venv so the
# system Python is left alone.
#
#   ./build_linux.sh            binary only
#   ./build_linux.sh --package  also a .tar.gz and .deb (packaging/linux/package.sh)
#
# The binary runs on distros whose glibc is at least as new as the build
# machine's, so build release packages on an old distro (see README_LINUX.md).
#
# Needs: python3 (3.11+) with tkinter + venv
#   Debian/Ubuntu: sudo apt install python3-tk python3-venv
#   Fedora:        sudo dnf install python3-tkinter
#   Arch:          sudo pacman -S tk
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

for f in exfat_builder.py linux_image_builder.py ui; do
    if [ ! -e "$f" ]; then
        echo "ERROR: $f not found. Run this script from the repo root." >&2
        exit 1
    fi
done

if ! "$PYTHON" -c 'import tkinter' 2>/dev/null; then
    echo "ERROR: $PYTHON has no tkinter. Install python3-tk (or your distro's equivalent)." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating .venv ..."
    "$PYTHON" -m venv .venv
fi
VPY=.venv/bin/python

echo "Installing dependencies..."
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet --upgrade pyinstaller pillow tkinterdnd2 psutil mkpfs==0.0.8
echo

echo "Building exfat-image-builder (Full version)..."
# Options live in the spec (it also keeps the X11/font libs out of the
# bundle so the desktop's own copies are used).
"$VPY" -m PyInstaller --clean --noconfirm packaging/linux/exfat-image-builder.spec
echo

if [ -f exfat_builder_lite.py ]; then
    echo "Building exfat-image-builder-lite..."
    "$VPY" -m PyInstaller --onefile --windowed --clean --noconfirm \
        --name "exfat-image-builder-lite" \
        --hidden-import PIL._tkinter_finder \
        --hidden-import psutil \
        exfat_builder_lite.py
else
    echo "Skipping Lite build - exfat_builder_lite.py not found."
fi

(cd dist && sha256sum exfat-image-builder > exfat-image-builder.sha256)
echo
echo "Done! Binary: dist/exfat-image-builder  (SHA256 in dist/exfat-image-builder.sha256)"
if [ "${1:-}" = "--package" ]; then
    VPY="$VPY" packaging/linux/package.sh
fi
echo "Runtime needs exfatprogs, plus udisks2 or exfat-fuse for mounting - see README_LINUX.md."
