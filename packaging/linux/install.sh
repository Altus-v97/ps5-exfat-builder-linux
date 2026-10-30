#!/usr/bin/env bash
# Installs exFAT Image Builder for the current user (no root needed):
#   ~/.local/opt/exfat-image-builder/    the app
#   ~/.local/bin/exfat-image-builder     launcher
#   app menu entry + icon
# Run ./install.sh --uninstall to remove it again.
set -euo pipefail
cd "$(dirname "$0")"

APP=exfat-image-builder
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
OPT="$HOME/.local/opt/$APP"
BIN="$HOME/.local/bin/$APP"
DESKTOP="$DATA/applications/$APP.desktop"
ICON="$DATA/icons/hicolor/128x128/apps/$APP.png"

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$OPT"
    rm -f "$BIN" "$DESKTOP" "$ICON"
    echo "Uninstalled. Your settings (~/.exfat_builder_settings.json) were left in place."
    exit 0
fi

mkdir -p "$OPT" "$(dirname "$BIN")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
rm -rf "$OPT"/*
cp -r "$APP" assets "$OPT"/
if [ -f CHANGELOG.md ]; then cp CHANGELOG.md "$OPT"/; fi
printf '#!/bin/sh\nexec "%s/%s" "$@"\n' "$OPT" "$APP" > "$BIN"
chmod 755 "$BIN" "$OPT/$APP"
sed "s|^Exec=.*|Exec=$BIN|" "$APP.desktop" > "$DESKTOP"
cp "$APP.png" "$ICON"
command -v update-desktop-database >/dev/null && update-desktop-database "$DATA/applications" 2>/dev/null || true

echo "Installed. Start it from your app menu (\"exFAT Image Builder\") or run: $BIN"
missing=""
command -v mkfs.exfat >/dev/null || missing="$missing exfatprogs"
command -v udisksctl >/dev/null || command -v mount.exfat-fuse >/dev/null || missing="$missing udisks2-or-exfat-fuse"
if [ -n "$missing" ]; then
    echo "Still needed to build images:$missing  (see README_LINUX.md)"
fi
