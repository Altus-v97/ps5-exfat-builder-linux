# PyInstaller spec for the Linux single-file build (used by build_linux.sh).
# Same options as build.bat, plus one Linux-specific rule: the X11 / font
# stack is NOT bundled. Mixing a bundled libX11/libXft/fontconfig from the
# build machine with the target desktop's own libxcb/X server crashes Tk
# (seen as a segfault in _XReply on Ubuntu 22.04 with a Debian 11 build).
# Every desktop has these libs; the .deb lists them as dependencies.
# Tcl/Tk itself stays bundled — many desktops don't ship libtk8.6.
import os
import re

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

datas, binaries, hiddenimports = [], [], []
for pkg in ('mkpfs', 'cryptography', 'tkinterdnd2'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules('ui') + collect_submodules('ui.shared')
hiddenimports += [
    'linux_image_builder', 'PIL._tkinter_finder', 'psutil',
    'mkpfs', 'mkpfs.__main__', 'mkpfs.cli', 'mkpfs.pfs', 'mkpfs.utils',
    'mkpfs.consts', 'mkpfs.logging', 'mkpfs.pbar',
]

a = Analysis(
    [os.path.join(ROOT, 'exfat_builder.py')],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)

SYSTEM_LIBS = re.compile(
    r'^lib(X11|X11-xcb|xcb|Xau|Xdmcp|Xext|Xrender|Xft|Xss|Xcursor|Xfixes'
    r'|fontconfig|freetype|expat|bsd|md)\.so')
a.binaries = [b for b in a.binaries
              if not SYSTEM_LIBS.match(os.path.basename(b[0]))]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='exfat-image-builder',
    console=False,
    upx=False,
)
