#!/usr/bin/python3
import contextlib
import fcntl
import os
from pathlib import Path
import signal
import select
import subprocess
import time
import shutil

INSTALLER = "/usr/lib/steam/steam-install"


def exists(path):
    return os.path.lexists(path)


def stop_clients(root):
    handles = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            fd = None
            try:
                fd = os.pidfd_open(int(entry.name))
                executable = Path(os.readlink(entry / "exe").removesuffix(" (deleted)"))
                if entry.stat().st_uid == os.getuid() and executable.is_relative_to(root) and executable.name in {"steam", "steamwebhelper", "steamservice"}:
                    handles.append(fd)
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
                else:
                    os.close(fd)
            except (OSError, RuntimeError):
                if fd is not None and fd not in handles:
                    with contextlib.suppress(OSError):
                        os.close(fd)
        pending = set(handles)
        poller = select.poll()
        for fd in pending:
            poller.register(fd, select.POLLIN)
        for timeout, sig in ((15, signal.SIGKILL), (5, None)):
            deadline = time.monotonic() + timeout
            while pending and time.monotonic() < deadline:
                for fd, _ in poller.poll(100):
                    pending.discard(fd)
                    poller.unregister(fd)
            if sig:
                for fd in pending:
                    with contextlib.suppress(ProcessLookupError):
                        signal.pidfd_send_signal(fd, sig)
        if pending:
            raise RuntimeError("Steam processes did not stop; client files were not replaced")
    finally:
        for fd in handles:
            os.close(fd)


def progress(message):
    print(message, flush=True)


class SteamMaintenance:
    def __init__(self, home=None, runtime=None):
        self.home = Path(home or Path.home())
        self.root = self.home / ".local/share/Steam"
        self.runtime = Path(runtime or os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "armada-steam-health"
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)

    def check_root(self):
        if (self.home / ".steam").is_symlink():
            raise RuntimeError("Refusing to modify a symlinked ~/.steam directory")
        configured = Path(os.environ.get("STEAM_ROOT", self.root))
        if configured != self.root or self.root.is_symlink():
            raise RuntimeError("Repair is disabled for a custom or symlinked Steam installation")
        if (self.home / "devkit-game/devkit-steam").exists():
            raise RuntimeError("Repair is disabled for a sideloaded Steam installation")

    @contextlib.contextmanager
    def lock(self):
        with (self.runtime / "repair.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another Steam maintenance operation is already running") from None
            yield

    def restore(self, reset=False):
        self.check_root()
        with self.lock():
            progress("Stopping Steam")
            stop_clients(self.root.resolve())
            progress("Resetting the Steam client" if reset else "Repairing the Steam client")
            result = subprocess.run([INSTALLER, "--reset" if reset else "--repair"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    env={**os.environ, "HOME": str(self.home), "STEAM_ROOT": str(self.root)})
            if result.returncode != 0:
                raise RuntimeError(f"Cannot restore Steam: {result.stdout.strip()}")
            self.reset_caches()
            self.clear_runtime_files()
            progress("Steam client reset; you will need to sign in again" if reset
                     else "Steam client repaired; games and account data preserved")

    def clear_runtime_files(self):
        for name in ("steam.pid", "steam.token", "steam.pipe"):
            (self.home / ".steam" / name).unlink(missing_ok=True)

    def cache_paths(self):
        for relative in ("config/htmlcache", "config/widevine", "appcache/httpcache", "appcache/cefdata"):
            path = self.root / relative
            if exists(path) and path.parent.resolve().is_relative_to(self.root.resolve()):
                yield path

    def reset_caches(self):
        for path in self.cache_paths():
            if path.is_symlink() or not path.is_dir():
                path.unlink(missing_ok=True)
            else:
                shutil.rmtree(path)
