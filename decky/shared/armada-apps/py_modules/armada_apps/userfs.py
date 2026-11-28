import ctypes
import errno
import os
import re
import shutil
import stat

from .paths import user_home, user_ids

# Root writing into user-owned directories: every operation is fd-anchored so
# a user-planted symlink cannot redirect it.


class UnsafePathError(RuntimeError):
    pass


RENAME_EXCHANGE = 2

try:
    _libc = ctypes.CDLL(None, use_errno=True)
    _renameat2 = _libc.renameat2
    _renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    _renameat2.restype = ctypes.c_int
except (OSError, AttributeError):
    _renameat2 = None


def grant_user_fd(fd):
    # Through the held fd, so the name cannot be swapped underneath.
    try:
        os.fchmod(fd, 0o755)
    except OSError:
        pass
    ids = user_ids()
    if not ids:
        return
    try:
        os.fchown(fd, ids[0], ids[1])
    except OSError:
        pass


def exchange(src_fd, src, dst_fd, dst):
    # NotImplementedError where libc or the filesystem lacks renameat2.
    if _renameat2 is None:
        raise NotImplementedError("renameat2 unavailable")
    if _renameat2(src_fd, os.fsencode(src), dst_fd, os.fsencode(dst), RENAME_EXCHANGE) != 0:
        error = ctypes.get_errno()
        if error in (errno.EINVAL, errno.ENOSYS, errno.ENOTSUP):
            raise NotImplementedError("renameat2 unsupported here")
        raise OSError(error, os.strerror(error))


def _open_component(dir_fd, name):
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise UnsafePathError("Refusing to follow a symlink at " + name)
        raise


def _chown_at(name, dir_fd):
    ids = user_ids()
    if not ids:
        return
    try:
        os.chown(name, ids[0], ids[1], dir_fd=dir_fd, follow_symlinks=False)
    except OSError:
        pass


def open_home():
    return os.open(os.path.realpath(user_home()), os.O_RDONLY | os.O_DIRECTORY)


def open_user_path(parts, create=False):
    fd = open_home()
    try:
        for name in parts:
            try:
                next_fd = _open_component(fd, name)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(name, 0o755, dir_fd=fd)
                _chown_at(name, fd)
                next_fd = _open_component(fd, name)
            os.close(fd)
            fd = next_fd
        return fd
    except Exception:
        os.close(fd)
        raise


def make_staging(prefix):
    # Root-owned 0700 staging inside the user's home: closed to tampering, yet
    # on the same filesystem as the publish targets so rename stays atomic.
    home_fd = open_home()
    try:
        from .profile import profile
        name = ".{}-{}.{}".format(profile.name, prefix, os.getpid())
        try:
            shutil.rmtree(name, ignore_errors=True, dir_fd=home_fd)
        except OSError:
            pass
        try:
            os.unlink(name, dir_fd=home_fd)
        except OSError:
            pass
        os.mkdir(name, 0o700, dir_fd=home_fd)
        fd = _open_component(home_fd, name)
        return home_fd, name, fd
    except Exception:
        os.close(home_fd)
        raise


def sweep_staging():
    """Remove staging folders a killed install left behind. Only at load,
    when no job of this plugin can be running."""
    from .profile import profile
    pattern = re.compile(r"\.{}-[a-z]+\.[0-9]+".format(re.escape(profile.name)))
    home_fd = open_home()
    try:
        for name in os.listdir(home_fd):
            if not pattern.fullmatch(name):
                continue
            try:
                info = os.stat(name, dir_fd=home_fd, follow_symlinks=False)
            except OSError:
                continue
            # Only staging this plugin's own user made (root); anything the
            # user made stays.
            if stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid():
                shutil.rmtree(name, ignore_errors=True, dir_fd=home_fd)
    finally:
        os.close(home_fd)


def cleanup_staging(home_fd, name, fd):
    for close_fd in (fd,):
        try:
            os.close(close_fd)
        except OSError:
            pass
    try:
        shutil.rmtree(name, ignore_errors=True, dir_fd=home_fd)
    except OSError:
        pass
    try:
        os.close(home_fd)
    except OSError:
        pass


def proc_path(fd, name=None):
    base = "/proc/self/fd/{}".format(fd)
    return base + "/" + name if name else base


def create_file(dir_fd, name, mode=0o644):
    try:
        os.unlink(name, dir_fd=dir_fd)
    except FileNotFoundError:
        pass
    # O_EXCL refuses anything recreated at the name between unlink and open.
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=dir_fd)
    try:
        ids = user_ids()
        if ids:
            try:
                os.fchown(fd, ids[0], ids[1])
            except OSError:
                pass
        os.fchmod(fd, mode)
    except Exception:
        os.close(fd)
        raise
    return os.fdopen(fd, "wb")


def rename(src_fd, src, dst_fd, dst):
    os.rename(src, dst, src_dir_fd=src_fd, dst_dir_fd=dst_fd)


def unlink(dir_fd, name):
    try:
        os.unlink(name, dir_fd=dir_fd)
    except FileNotFoundError:
        pass


def rmtree(dir_fd, name):
    try:
        shutil.rmtree(name, dir_fd=dir_fd)
    except FileNotFoundError:
        pass


def remove_entry(dir_fd, name):
    try:
        os.unlink(name, dir_fd=dir_fd)
        return
    except FileNotFoundError:
        return
    except IsADirectoryError:
        pass
    except OSError as error:
        if error.errno != errno.EISDIR:
            raise
    rmtree(dir_fd, name)


def lchown_tree(root):
    ids = user_ids()
    if not ids:
        return
    uid, gid = ids
    for dirpath, dirnames, filenames in os.walk(root):
        for entry in dirnames + filenames:
            try:
                os.lchown(os.path.join(dirpath, entry), uid, gid)
            except OSError:
                pass
    try:
        os.lchown(root, uid, gid)
    except OSError:
        pass
