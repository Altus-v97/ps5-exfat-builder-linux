# 🎮 exFAT Image Builder for Linux

**Build, Convert & Backport PS5 Game Images — on Linux**

Build • Convert • Backport • Deploy

![Platform](https://img.shields.io/badge/Platform-Linux%20x86--64-blue)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![Release](https://img.shields.io/github/v/release/Altus-v97/ps5-exfat-builder-linux)
![Downloads](https://img.shields.io/github/downloads/Altus-v97/ps5-exfat-builder-linux/total)

A Linux port of [**exFAT Image Builder**](https://github.com/kerrdec97/ps5-exfat-builder)
by kerrdec97 — the same app and interface, with the Windows-only tools
(OSFMount, format.com, robocopy) replaced by standard Linux ones.

------------------------------------------------------------------------

## 🚀 Overview

**exFAT Image Builder** is an all-in-one application for creating,
converting and managing mountable PS5 game images from your own game
dumps.

Whether you're building an **exFAT image**, generating a **compressed
FFPFSC**, creating an **FFPKG**, applying **backports**, managing
**DLC**, or transferring directly to your PS5, everything is available
from one interface.

> ⚠️ **Homebrew & Personal Backup Tool**
>
> This software is intended only for games and content **you legally own
> and have dumped yourself**.
>
> It **does not** download games, decrypt retail packages, bypass DRM or
> provide copyrighted content.

------------------------------------------------------------------------

# 📥 Download

Grab the latest build from the
[**Releases page**](https://github.com/Altus-v97/ps5-exfat-builder-linux/releases/latest).
Runs on x86-64 Linux with glibc 2.31+ (Ubuntu 20.04+, Mint 20+, Debian 11+,
Fedora 32+ and similar).

| File | Use it when |
|---|---|
| `exfat-image-builder_*_amd64.deb` | Debian / Ubuntu / Mint — `sudo apt install ./exfat-image-builder_*_amd64.deb`, then start **exFAT Image Builder** from the app menu |
| `exfat-image-builder-*-linux-x86_64.tar.gz` | Any distro — unpack, run `./install.sh` (no root; `./install.sh --uninstall` removes it) |
| `exfat-image-builder-linux-x86_64` | Just run it: `chmod +x exfat-image-builder-linux-x86_64 && ./exfat-image-builder-linux-x86_64` |

## Requirements

Building images needs **exfatprogs** plus **udisks2** or **exfat-fuse**
to mount the image (the `.deb` installs exfatprogs for you):

```bash
sudo apt install exfatprogs udisks2 exfat-fuse      # Debian / Ubuntu / Mint
sudo dnf install exfatprogs udisks2 fuse-exfat      # Fedora
sudo pacman -S exfatprogs udisks2 fuse-exfat        # Arch
```

- **FFPKG** builds also need the **.NET 8 runtime** (`dotnet-runtime-8.0`).
- For the emoji icons in the sidebar, install an emoji font
  (e.g. `fonts-noto-color-emoji`).
- Run the app as your normal user — **not** with `sudo`. It only asks for
  privileges at the moment it mounts an image.

------------------------------------------------------------------------

# ⚡ Quick Start

1.  Install the requirements above.
2.  Start **exFAT Image Builder** and open the **Build** tab.
3.  Select your PS5 game dump (the folder containing `eboot.bin`).
4.  Choose **exFAT**, **FFPKG** or **FFPFSC**.
5.  Click **Add to Queue** then **Build All**.
6.  Wait for Scan → Format → Copy → Verify to complete.

------------------------------------------------------------------------

# ✨ Features

## 📦 Image Builder

-   ✅ Build exFAT Images
-   ✅ Build FFPKG (UFS2)
-   ✅ Build Compressed FFPFSC Images
-   ✅ Automatic Image Verification (`fsck.exfat`)
-   ✅ Queue Multiple Builds
-   ✅ Automatic Game Detection
-   ✅ Extract exFAT Images

## 🔥 Backport Toolkit

-   Auto Backport
-   SDK Detection
-   Fakelib Support
-   DLC Support
-   Language Stripper
-   Automatic AMPR Generation
-   Restore Original Files

## 🎮 PS5 Integration

-   FTP Browser
-   Remote Content Manager
-   Payload Sender
-   Live Kernel Log Viewer
-   Console Diagnostics
-   Direct PS5 Deployment

## 📚 Library

-   Automatic Cover Art
-   Metadata Detection
-   Bulk Rename
-   Batch Queue
-   Format Conversion
-   Game Browser

## 🌍 Languages

Supports **17 interface languages**, maintained by the community.

## 🚧 Not yet on Linux

-   The exFAT **Image Editor** (replace / add / delete files inside an
    existing image) and mounting an FFPKG as a drive still depend on
    Windows-only tools (OSFMount / Dokan). Use the Windows version for
    these for now.

------------------------------------------------------------------------

# 📦 Supported Formats

  Format     Description
  ---------- --------------------------
  📀 exFAT   Standard mountable image
  📦 FFPKG   UFS2 Image
  🗜 FFPFSC   Compressed PFS Image

------------------------------------------------------------------------

# 🛠 Building from source

```bash
git clone https://github.com/Altus-v97/ps5-exfat-builder-linux.git
cd ps5-exfat-builder-linux
./build_linux.sh            # binary in dist/
./build_linux.sh --package  # also .deb and .tar.gz
```

Or run straight from source with `python3 exfat_builder.py` after
installing `pillow tkinterdnd2 psutil mkpfs==0.0.8`. See
[README_LINUX.md](README_LINUX.md) for mount methods, troubleshooting and
how the release packages are built.

The original Windows build files (`build.bat`) are kept so the code base
stays in sync with upstream.

------------------------------------------------------------------------

# ❤️ Credits

The original **exFAT Image Builder** is developed by
[kerrdec97](https://github.com/kerrdec97/ps5-exfat-builder) — this
repository only adds Linux support.

Thanks to everyone in the PS5 Homebrew community, especially:

-   Nazky
-   BestPig
-   SvenGDK
-   drakmor
-   PSBrew
-   john-tornblom
-   ps5-payload-dev
-   idlesauce
-   NookieAI
-   stonemodder

See **THIRD_PARTY_NOTICES.md** for full licensing information.

------------------------------------------------------------------------

# ⚠ Disclaimer

This software is intended only for content you legally own.

It is **not affiliated with or endorsed by Sony Interactive
Entertainment**.

Use at your own risk.

------------------------------------------------------------------------

# ⭐ Support the Project

-   ⭐ Star the repository
-   🐞 Report Linux bugs in this repo's
    [Issues](https://github.com/Altus-v97/ps5-exfat-builder-linux/issues)
-   ❤️ Support the original developer and the PS5 Homebrew community

Made with Claude Code and a passion for PSX homebrew.
