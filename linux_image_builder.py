"""linux_image_builder.py — Linux backend for the exFAT image build.

Linux counterpart of the embedded make_image.bat + New-OsfExfatImage.ps1
pair. It performs the same steps and prints the same progress markers
the GUI's _handle_line/_parse_line already understand, so the Build tab
works unchanged on both platforms:

    [INFO] Enumerating files ... / Enumeration progress / Enumeration done
    [1/4] Creating & mounting the image ... as a logical volume on <mnt>
    [2/4] Formatting ...            (mkfs.exfat, done BEFORE mounting)
    [3/4] Copying ...               ([ROBO-MODE] perfile|summary, per-file
                                     "\t\t\t<size>\t<path>" lines and a
                                     robocopy-style "Files : N N" summary)
    [Info] Post-copy check ...
    [Info] Flushing volume write cache ... / Volume cache flushed in Ns.
    [4/4] Done. Dismounting ...
    OK: Image created at: <path>

Pipeline: sparse file -> mkfs.exfat -> mount -> copy -> syncfs -> unmount
-> fsck.exfat -n. Mounting is the only privileged step; the first method
that works is used (override with EXFAT_MOUNT_METHOD):

    root    already root: mount -o loop (kernel exfat driver)
    udisks  udisksctl loop-setup + mount (desktop sessions, no password)
    fuse    mount.exfat-fuse (exfat-fuse package, unprivileged)
    sudo    passwordless sudo mount -o loop
    pkexec  graphical password prompt, then mount -o loop

Run via the app (`exfat_builder.py --__exfat_image_worker__ ...`) or
directly: python3 linux_image_builder.py IMAGE SOURCE_DIR [options].
"""

import argparse
import concurrent.futures
import ctypes
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

GB = 1024 ** 3
MB = 1024 ** 2

MOUNT_METHODS = ('root', 'udisks', 'fuse', 'sudo', 'pkexec')


def log(text=''):
    print(text, flush=True)


def format_bytes(n):
    for unit, size in (('TB', 1024 ** 4), ('GB', GB), ('MB', MB), ('KB', 1024)):
        if n >= size:
            return '%.2f %s' % (n / size, unit)
    return '%d B' % n


def parse_size_to_bytes(s):
    m = re.match(r'^\s*(\d+)\s*([bBkKmMgGtT]?)\s*$', s or '')
    if not m:
        raise ValueError("Failed to parse size string: '%s'" % s)
    num, unit = int(m.group(1)), m.group(2)
    mult = {'': 1, 'b': 512, 'B': 512,
            'K': 1024, 'M': MB, 'G': GB, 'T': 1024 ** 4,
            'k': 1000, 'm': 1000 ** 2, 'g': 1000 ** 3, 't': 1000 ** 4}[unit]
    return num * mult


def is_hidden(name):
    return name.startswith('.')


def is_excluded_file(name):
    return name.lower().endswith(('.exfat', '.ffpkg'))


# ── Source scan (mirrors Get-SourceStats) ────────────────────────────────────

class SourceStats:
    def __init__(self):
        self.file_count = 0
        self.dir_count = 0
        self.raw_bytes = 0
        self.data_bytes = 0
        self.has_large_file = False
        self.longest_path = 0


def get_source_stats(src, cluster, exclude_hidden=False):
    st = SourceStats()
    log('[INFO] Enumerating files ...')
    t0 = time.time()
    for root, dirs, files in os.walk(src):
        if exclude_hidden:
            dirs[:] = [d for d in dirs if not is_hidden(d)]
        for d in dirs:
            st.dir_count += 1
            st.longest_path = max(st.longest_path,
                                  len(os.path.join(root, d)))
        for f in files:
            if is_excluded_file(f) or (exclude_hidden and is_hidden(f)):
                continue
            path = os.path.join(root, f)
            st.file_count += 1
            st.longest_path = max(st.longest_path, len(path))
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            st.raw_bytes += size
            st.data_bytes += int(math.ceil(size / cluster)) * cluster
            if size >= GB:
                st.has_large_file = True
            if st.file_count % 10000 == 0:
                log('[INFO] Enumeration progress: {:,} files / {}'.format(
                    st.file_count, format_bytes(st.raw_bytes)))
    log('[INFO] Enumeration done: {:,} files, {:,} dirs, {} ({:.1f}s)'.format(
        st.file_count, st.dir_count, format_bytes(st.raw_bytes),
        time.time() - t0))
    return st


def optimal_cluster_size(stats):
    if stats.file_count == 0:
        return 32768
    return 65536 if stats.raw_bytes // stats.file_count >= MB else 32768


def optimal_image_size(stats, cluster):
    # Same formula as Get-OptimalImageSizeBytesFromStats.
    data_clusters = int(math.ceil(stats.data_bytes / cluster))
    fat_bytes = data_clusters * 4
    bitmap_bytes = int(math.ceil(data_clusters / 8.0))
    entry_bytes = (stats.file_count + stats.dir_count) * 512
    base_total = (stats.data_bytes + fat_bytes + bitmap_bytes + entry_bytes
                  + 64 * MB)
    spare = min(max(int(math.ceil(base_total / 100.0)), 1024 * MB), 8192 * MB)
    total = max(base_total + spare, stats.raw_bytes + 1024 * MB)
    return int(math.ceil(total / MB)) * MB


# ── Mounting ─────────────────────────────────────────────────────────────────

def _run(cmd, timeout=120):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=timeout)


def _owner_opts():
    return 'uid=%d,gid=%d' % (os.getuid(), os.getgid())


class Mount:
    """A mounted image. .path is the mount point; .unmount() undoes it."""

    def __init__(self, method, path, unmount_cmds, cleanup_dir=None):
        self.method = method
        self.path = path
        self._unmount_cmds = unmount_cmds
        self._cleanup_dir = cleanup_dir

    def unmount(self, attempts=6):
        ok = False
        for i in range(attempts):
            results = [_run(c) for c in self._unmount_cmds]
            if all(r.returncode == 0 for r in results):
                ok = True
                break
            msg = ' / '.join(r.stdout.strip() for r in results if r.stdout.strip())
            log('[WARN] Unmount attempt %d/%d failed: %s' % (i + 1, attempts, msg))
            time.sleep(1.0)
        if ok and self._cleanup_dir:
            try:
                os.rmdir(self._cleanup_dir)
            except OSError:
                pass
        return ok


def _loop_mount(image, prefix, method, readonly):
    mnt = tempfile.mkdtemp(prefix='exfat_mnt_')
    opts = ('ro,' if readonly else '') + 'loop,' + _owner_opts()
    r = _run(prefix + ['mount', '-o', opts,
                       '-t', 'exfat', image, mnt])
    if r.returncode != 0:
        os.rmdir(mnt)
        raise RuntimeError(r.stdout.strip() or 'mount exit %d' % r.returncode)
    return Mount(method, mnt, [prefix + ['umount', mnt]], cleanup_dir=mnt)


def _mount_root(image, readonly):
    if os.geteuid() != 0:
        raise RuntimeError('not running as root')
    return _loop_mount(image, [], 'root', readonly)


def _mount_sudo(image, readonly):
    if not shutil.which('sudo') or _run(['sudo', '-n', 'true']).returncode != 0:
        raise RuntimeError('passwordless sudo not available')
    return _loop_mount(image, ['sudo', '-n'], 'sudo', readonly)


def _mount_pkexec(image, readonly):
    if not shutil.which('pkexec'):
        raise RuntimeError('pkexec not installed')
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        raise RuntimeError('no graphical session for the password prompt')
    log('[Info] Asking for your password (pkexec) to mount the image ...')
    return _loop_mount(image, ['pkexec'], 'pkexec', readonly)


def _mount_fuse(image, readonly):
    exe = shutil.which('mount.exfat-fuse') or shutil.which('exfat-fuse')
    if not exe:
        raise RuntimeError('exfat-fuse not installed')
    if not os.path.exists('/dev/fuse'):
        raise RuntimeError('/dev/fuse not available')
    fusermount = shutil.which('fusermount3') or shutil.which('fusermount')
    if not fusermount:
        raise RuntimeError('fusermount not found')
    mnt = tempfile.mkdtemp(prefix='exfat_mnt_')
    r = _run([exe, '-o', ('ro,' if readonly else '') + _owner_opts(), image, mnt])
    if r.returncode != 0:
        os.rmdir(mnt)
        raise RuntimeError(r.stdout.strip() or 'exit %d' % r.returncode)
    return Mount('fuse', mnt, [[fusermount, '-u', mnt]], cleanup_dir=mnt)


def _findmnt(dev):
    r = _run(['findmnt', '-n', '-o', 'TARGET', '--source', dev])
    return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ''


def _mount_udisks(image, readonly):
    if not shutil.which('udisksctl'):
        raise RuntimeError('udisksctl not installed')
    r = _run(['udisksctl', 'loop-setup', '--no-user-interaction', '-f', image]
             + (['-r'] if readonly else []))
    m = re.search(r'(/dev/loop\d+)', r.stdout)
    if r.returncode != 0 or not m:
        raise RuntimeError(r.stdout.strip() or 'loop-setup exit %d' % r.returncode)
    dev = m.group(1)
    delete = ['udisksctl', 'loop-delete', '--no-user-interaction', '-b', dev]
    # Desktop auto-mounters may grab the fresh loop device on their own.
    path = ''
    for _ in range(10):
        path = _findmnt(dev)
        if path:
            break
        r = _run(['udisksctl', 'mount', '--no-user-interaction', '-b', dev])
        m = re.search(r' at (.+?)\.?\s*$', r.stdout.strip())
        if r.returncode == 0 and m:
            path = m.group(1)
            break
        if 'AlreadyMounted' not in r.stdout:
            time.sleep(0.5)
    if not path:
        _run(delete)
        raise RuntimeError(r.stdout.strip() or 'udisksctl mount failed')
    return Mount('udisks', path,
                 [['udisksctl', 'unmount', '--no-user-interaction', '-b', dev],
                  delete])


_MOUNTERS = {'root': _mount_root, 'udisks': _mount_udisks, 'fuse': _mount_fuse,
             'sudo': _mount_sudo, 'pkexec': _mount_pkexec}


def mount_image(image, method='auto', readonly=False):
    methods = MOUNT_METHODS if method in ('', 'auto') else (method,)
    errors = []
    for name in methods:
        try:
            m = _MOUNTERS[name](image, readonly)
            log('[Info] Mounted with method: %s' % name)
            return m
        except Exception as e:
            errors.append('%s: %s' % (name, e))
    raise RuntimeError(
        'Could not mount the image. Tried:\n  ' + '\n  '.join(errors) +
        '\nInstall udisks2 (desktop) or exfat-fuse, or run with passwordless '
        'sudo. See README_LINUX.md.')


def syncfs(path):
    """Flush one filesystem (falls back to a global sync)."""
    fd = os.open(path, os.O_RDONLY)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.syncfs(fd) != 0:
            raise OSError(ctypes.get_errno(), 'syncfs failed')
    except (AttributeError, OSError):
        os.sync()
    finally:
        os.close(fd)


# ── Copy (robocopy replacement) ──────────────────────────────────────────────

LARGE_FILE = 64 * MB


def copy_tree(src, dest, threads, retries, retry_wait, exclude_hidden, per_file):
    """Copy src into dest. Big files go one at a time (keeps them contiguous
    in the image); small files run on a thread pool. Returns
    (copied, failed, bytes)."""
    small, large = [], []
    dir_count = 0
    for root, dirs, files in os.walk(src):
        if exclude_hidden:
            dirs[:] = [d for d in dirs if not is_hidden(d)]
        rel = os.path.relpath(root, src)
        target_root = dest if rel == '.' else os.path.join(dest, rel)
        os.makedirs(target_root, exist_ok=True)
        dir_count += 1
        for f in files:
            if is_excluded_file(f) or (exclude_hidden and is_hidden(f)):
                continue
            s = os.path.join(root, f)
            try:
                size = os.path.getsize(s)
            except OSError:
                size = 0
            (large if size >= LARGE_FILE else small).append(
                (s, os.path.join(target_root, f), size))

    lock = threading.Lock()
    totals = {'copied': 0, 'failed': 0, 'bytes': 0}

    def copy_one(job):
        s, d, size = job
        last = None
        for attempt in range(retries + 1):
            try:
                shutil.copyfile(s, d)
                if size >= LARGE_FILE:
                    # Push big files to the image now so the free-space
                    # progress in the GUI tracks real writes (robocopy /J).
                    with open(d, 'rb+') as fh:
                        os.fsync(fh.fileno())
                st = os.stat(s)
                try:
                    os.utime(d, (st.st_atime, st.st_mtime))
                except OSError:
                    pass
                last = None
                break
            except OSError as e:
                last = e
                if attempt < retries:
                    time.sleep(retry_wait)
        with lock:
            if last is None:
                totals['copied'] += 1
                totals['bytes'] += size
                if per_file:
                    log('\t\t\t%d\t%s' % (size, s))
            else:
                totals['failed'] += 1
                log('[WARN] Failed to copy %s: %s' % (s, last))

    for job in large:
        copy_one(job)
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        list(pool.map(copy_one, small))

    total = len(small) + len(large)
    log('')
    log('               Total    Copied   Skipped  Mismatch    FAILED    Extras')
    log('    Dirs : %9d %9d %9d %9d %9d %9d' % (dir_count, dir_count, 0, 0, 0, 0))
    log('   Files : %9d %9d %9d %9d %9d %9d' % (
        total, totals['copied'], 0, 0, totals['failed'], 0))
    log('   Bytes : %s' % format_bytes(totals['bytes']))
    return totals['copied'], totals['failed'], totals['bytes']


# ── Main ─────────────────────────────────────────────────────────────────────

def build(args):
    image = os.path.abspath(args.image)
    src = os.path.abspath(args.source.rstrip('/') or '/')

    log('[INFO] Source folder: "%s"' % src)
    log('[INFO] Output image:  "%s"' % image)
    if not os.path.isdir(src):
        raise RuntimeError('Source directory not found: ' + src)
    if not os.path.isfile(os.path.join(src, 'eboot.bin')):
        raise RuntimeError('eboot.bin not found in source directory: ' + src)
    mkfs = shutil.which('mkfs.exfat')
    if not mkfs:
        raise RuntimeError('mkfs.exfat not found. Install exfatprogs '
                           '(e.g. sudo apt install exfatprogs).')

    out_dir = os.path.dirname(image)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(image):
        os.remove(image)

    if args.cluster_size > 0:
        cluster = args.cluster_size
        stats = get_source_stats(src, cluster, args.exclude_hidden)
        log('[Info] Using custom cluster size: %d bytes' % cluster)
    else:
        stats = get_source_stats(src, 32768, args.exclude_hidden)
        cluster = optimal_cluster_size(stats)
        if cluster != 32768:
            stats = get_source_stats(src, cluster, args.exclude_hidden)

    if args.size:
        size = parse_size_to_bytes(args.size)
    elif args.image_size_gb > 0:
        size = int(args.image_size_gb * GB)
        log('[INFO] Image size override: %s GB (%d bytes)' % (args.image_size_gb, size))
    else:
        log("[Info] Size not provided. Computing an optimal image size from '%s' ..." % src)
        size = optimal_image_size(stats, cluster)
    log('[Info] Computed image size: %s (%d bytes)' % (format_bytes(size), size))
    log('[Info] Selected filesystem: exFAT (cluster=%d) for image size %s.'
        % (cluster, format_bytes(size)))

    free = shutil.disk_usage(out_dir).free
    if free < size + 256 * MB:
        raise RuntimeError(
            'Not enough free space on the output drive for the image. The '
            'image needs %s (plus 256 MB headroom) but only %s is free at '
            "'%s'. Free up space or choose another output folder, then rebuild."
            % (format_bytes(size), format_bytes(free), out_dir))
    log('[Info] Free-space preflight OK: %s free on the output drive; the image '
        'needs %s.' % (format_bytes(free), format_bytes(size)))
    if args.sector_size not in (0, 512):
        log('[Info] Sector size %d requested; mkfs.exfat on an image file uses '
            '512-byte sectors, so this setting is ignored on Linux.' % args.sector_size)

    threads = args.threads if args.threads > 0 else 8
    threads = max(1, min(threads, 32))
    log('[Info] Source media: unknown, copy threads: %d' % threads)

    # Create + format first: mkfs.exfat works on a plain file, no mount needed.
    log('[1/4] Creating the image file (%s, sparse) ...' % format_bytes(size))
    with open(image, 'wb') as fh:
        fh.truncate(size)
    log('[2/4] Formatting image as exFAT (cluster=%d, label=\'%s\') via mkfs.exfat ...'
        % (cluster, args.label))
    r = _run([mkfs, '-c', str(cluster), '-L', args.label, image], timeout=600)
    for line in r.stdout.splitlines():
        log(line)
    if r.returncode != 0:
        raise RuntimeError('mkfs.exfat failed with exit code %d' % r.returncode)

    mnt = mount_image(image, os.environ.get('EXFAT_MOUNT_METHOD', 'auto'))
    # The GUI picks the mount point out of this exact phrase.
    log('[Info] Image mounted as a logical volume on %s' % mnt.path)
    try:
        per_file = 0 < stats.file_count <= 50000
        if per_file:
            log('[INFO] Per-file copy logging ON (%d files <= 50000)' % stats.file_count)
            log('[ROBO-MODE] perfile')
        else:
            log('[INFO] Per-file copy logging OFF (%d files > 50000) - using '
                'size/speed/ETA' % stats.file_count)
            log('[ROBO-MODE] summary')
        log("[3/4] Copying contents of '%s' -> '%s' (threads=%d) ..."
            % (src, mnt.path, threads))
        _, failed, _ = copy_tree(src, mnt.path, threads, args.retries,
                                 args.retry_wait, args.exclude_hidden, per_file)
        if failed:
            log('[WARN] %d file(s) could not be copied. The image has been '
                'created but is incomplete.' % failed)

        usage = shutil.disk_usage(mnt.path)
        used = usage.total - usage.free
        expect_min = int(stats.raw_bytes * 0.90)
        log('[Info] Post-copy check: volume holds %s, expected >= %s.'
            % (format_bytes(used), format_bytes(expect_min)))
        if used < expect_min:
            raise RuntimeError(
                'Copy verification FAILED: the mounted image holds only %s but '
                'the source is %s. Not shipping this image.'
                % (format_bytes(used), format_bytes(stats.raw_bytes)))
        log('[Info] Post-copy check passed.')

        log('[Info] Flushing volume write cache to image (syncfs %s)...' % mnt.path)
        t0 = time.time()
        flusher = threading.Thread(target=syncfs, args=(mnt.path,), daemon=True)
        flusher.start()
        while flusher.is_alive():
            flusher.join(10)
            if flusher.is_alive():
                log('[Info] Still flushing write cache (%ds elapsed)...'
                    % int(time.time() - t0))
        log('[Info] Volume cache flushed in %.1fs.' % (time.time() - t0))
        log('[4/4] Done. Dismounting volume...')
    finally:
        if not mnt.unmount():
            log('[WARN] Failed to unmount %s: volume busy.' % mnt.path)

    fsck = shutil.which('fsck.exfat')
    if fsck:
        r = _run([fsck, '-n', image], timeout=1800)
        if r.returncode != 0:
            for line in r.stdout.splitlines():
                log(line)
            raise RuntimeError('fsck.exfat found errors in the finished image '
                               '(exit %d).' % r.returncode)
        log('[Info] fsck.exfat: filesystem is clean.')
    log('OK: Image created at: %s' % image)


def parse_args(argv):
    p = argparse.ArgumentParser(description='Build a PS5 exFAT image on Linux.')
    p.add_argument('image')
    p.add_argument('source')
    p.add_argument('--size', default='')
    p.add_argument('--label', default='OSFIMG')
    p.add_argument('--cluster-size', type=int, default=0)
    p.add_argument('--sector-size', type=int, default=512)
    p.add_argument('--threads', type=int, default=0)
    p.add_argument('--retries', type=int, default=2)
    p.add_argument('--retry-wait', type=int, default=2)
    p.add_argument('--exclude-hidden', action='store_true')
    p.add_argument('--image-size-gb', type=float, default=0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        build(args)
    except Exception as e:
        log('[ERROR] %s' % e)
        log('[ERROR] The image is incomplete or empty and will NOT be used.')
        if os.path.exists(args.image):
            try:
                os.remove(args.image)
            except OSError:
                pass
        return 1
    log('[OK] Done: "%s"' % os.path.abspath(args.image))
    return 0


if __name__ == '__main__':
    sys.exit(main())
