# exFAT Image Builder on Linux

The Linux build is the same app, the same UI, and produces the same image
formats. The Windows-only pieces — OSFMount, `format.com` and `robocopy` —
are replaced by standard Linux tools.

## Install the runtime tools

| Needed for | Debian / Ubuntu | Fedora | Arch |
|---|---|---|---|
| exFAT images (required) | `exfatprogs` | `exfatprogs` | `exfatprogs` |
| Mounting the image (one of the methods below) | `udisks2` (most desktops already have it) or `exfat-fuse` | `udisks2` or `fuse-exfat` | `udisks2` or `fuse-exfat` |
| FFPKG (UFS2) images | `dotnet-runtime-8.0` | `dotnet-runtime-8.0` | `dotnet-runtime-8.0` |
| Running from source | `python3-tk` | `python3-tkinter` | `tk` |
| Emoji icons in the sidebar | `fonts-noto-color-emoji` | `google-noto-emoji-color-fonts` | `noto-fonts-emoji` |

Debian/Ubuntu in one line:

```bash
sudo apt install exfatprogs udisks2 exfat-fuse python3-tk fonts-noto-color-emoji
```

## Install a package

Release packages run on any x86-64 distro from roughly 2019 on (glibc 2.31+:
Ubuntu 20.04+, Mint 20+, Debian 11+, Fedora 32+).

**Debian / Ubuntu / Mint (`.deb`)** — pulls in exfatprogs and the X11 libs:

```bash
sudo apt install ./exfat-image-builder_3.6.4_amd64.deb
```

Remove with `sudo apt remove exfat-image-builder`.

**Any distro (`.tar.gz`)** — installs into your home folder, no root:

```bash
tar -xzf exfat-image-builder-3.6.4-linux-x86_64.tar.gz
cd exfat-image-builder-3.6.4
./install.sh            # ./install.sh --uninstall to remove
```

Either way, start **exFAT Image Builder** from your app menu or run
`exfat-image-builder`. No root needed: the app only asks for privileges at
the moment it mounts an image.

## Run it

**Built binary** — after building (below) run `dist/exfat-image-builder`.

**From source:**

```bash
python3 -m venv .venv
.venv/bin/pip install pillow tkinterdnd2 psutil mkpfs==0.0.8
.venv/bin/python exfat_builder.py
```

## Build the binary

```bash
./build_linux.sh
```

It creates a local `.venv`, installs the dependencies and runs
PyInstaller. Output: `dist/exfat-image-builder` (single file) plus its
`.sha256`. Add `--package` to also get the `.tar.gz` and `.deb`
(`packaging/linux/package.sh`).

### Release packages

A binary only runs on distros whose glibc is at least as new as the build
machine's, and Tcl/Tk is bundled from the Python used to build. Release
packages are therefore built on Debian 11 with a
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)
Python, which brings a current Tcl/Tk (Debian 11's Tk 8.6.11 crashes on the
emoji used throughout the UI):

```bash
docker run --rm -it -v "$PWD":/src -w /src python:3.11-bullseye bash -c '
  pip install uv && uv python install 3.11 &&
  PYTHON=$(uv python find 3.11) ./build_linux.sh --package'
```

The X11 / font libraries are deliberately not bundled (see
`packaging/linux/exfat-image-builder.spec`); the desktop's own copies are used.

## How an exFAT build works on Linux

Instead of OSFMount + `format.com` + `robocopy`, `linux_image_builder.py` does:

1. Scan the dump and compute the cluster size and image size (same formula
   as the Windows build).
2. Create a sparse image file and format it with `mkfs.exfat`.
3. Mount the image, copy the game in (large files one at a time, small
   files in parallel), flush with `syncfs`, unmount.
4. Run `fsck.exfat -n` on the finished image. A build only reports success
   if the filesystem check is clean.

### Mount methods

Mounting is the only step that needs privileges. The first method that works
is used:

| Method | When it works |
|---|---|
| `root` | the app itself runs as root |
| `udisks` | normal desktop session with udisks2 — no password |
| `fuse` | `exfat-fuse` installed and `/dev/fuse` available — no password |
| `sudo` | passwordless `sudo` configured |
| `pkexec` | graphical password prompt (polkit) |

To force one, set `EXFAT_MOUNT_METHOD`, e.g.
`EXFAT_MOUNT_METHOD=fuse ./dist/exfat-image-builder`. If none works, the
build log lists why each method failed.

The builder also runs headless:

```bash
python3 linux_image_builder.py "/out/My Game.exfat" /path/to/dump [--threads 8] [--cluster-size 65536]
```

## Feature status

| Feature | Linux |
|---|---|
| Build exFAT images (Build tab, queue) | ✅ |
| Build FFPKG (UFS2) images | ✅ needs the .NET 8 runtime |
| Build / convert compressed `.ffpfsc` (mkpfs) | ✅ |
| Extract an exFAT image | ✅ |
| FTP, payloads, klog, library, backports, metadata, covers | ✅ (pure Python) |
| Shutdown / restart / sleep after queue | ✅ via `systemctl` |
| Auto-update | Opens the releases page (releases are Windows `.exe`) |
| Image file manager / editor (mounts an image on a drive letter) | ❌ Windows-only (OSFMount) |
| Mount an FFPKG as a drive (Dokan) | ❌ Windows-only |
| Drag & drop | ✅ when tkdnd's native lib loads; falls back to Browse buttons |
