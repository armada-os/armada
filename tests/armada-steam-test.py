#!/usr/bin/env python3
import argparse
import io
import tarfile
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
import armada_steam as health


def seed(root, payload=b"factory client"):
    (root / "steamrtarm64").mkdir(parents=True)
    steam = root / "steamrtarm64/steam"
    steam.write_bytes(payload)
    steam.chmod(0o755)
    (root / "package").mkdir()
    (root / "package/steam_client_test_linuxarm64.installed").write_text(
        f"steamrtarm64/,-1;123;0\nsteamrtarm64/steam,{len(payload)};123;{zlib.crc32(payload)}\n")


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.h = health.SteamMaintenance(self.home, self.base / "run")
        self.h.root.mkdir(parents=True)
        self.factory = self.base / "factory"
        seed(self.factory)
        seed(self.h.root, b"old client")
        self.addCleanup(patch.stopall)
        patch.object(health, "progress").start()
        patch.object(health.os, "sync").start()
        self.source = patch.object(health, "extract_source", side_effect=self.extract).start()
        patch.dict(os.environ, {}, clear=False).start()
        os.environ.pop("STEAM_ROOT", None)

    def extract(self, destination, log):
        shutil.copytree(self.factory, destination, dirs_exist_ok=True)
        log.write_text("fixture commit\n")

    def test_restore_preserves_user_data_and_removes_cache_and_workspace(self):
        preserved = ["steamapps/common/game/save", "userdata/123/save", "config/loginusers.vdf",
                     "compatibilitytools.d/custom/tool", "ssfn123", "logs/bootstrap_log.txt", "custom-file"]
        caches = ["config/htmlcache", "config/widevine", "appcache/httpcache", "appcache/cefdata"]
        for relative in preserved + [cache + "/cache" for cache in caches]:
            path = self.h.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative)
        dot = self.home / ".steam"
        dot.mkdir()
        (dot / "registry.vdf").write_text("account settings")
        (dot / "steam.pid").write_text("stale PID")
        (dot / "steam").mkdir()
        (dot / "steam/unexpected").write_text("keep me")
        self.h.restore()
        for relative in preserved:
            self.assertEqual((self.h.root / relative).read_text(), relative)
        self.assertEqual((dot / "registry.vdf").read_text(), "account settings")
        self.assertFalse((dot / "steam.pid").exists())
        self.assertFalse(list(dot.glob("steam.pid.before-repair-*")))
        self.assertEqual((self.h.root / "steamrtarm64/steam").read_bytes(), b"factory client")
        self.assertFalse(self.h.work.exists())
        for cache in caches:
            self.assertFalse((self.h.root / cache).exists())
        self.assertEqual(next(dot.glob("steam.before-repair-*/unexpected")).read_text(), "keep me")
        for name in ["steam", "root", "sdk32", "sdk64", "sdkarm64", "bin32", "bin64", "binarm64"]:
            self.assertTrue((dot / name).is_symlink())

    def test_same_size_corruption_leaves_client_untouched(self):
        (self.factory / "steamrtarm64/steam").write_bytes(b"Factory client")
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.h.restore()
        self.assertEqual((self.h.root / "steamrtarm64/steam").read_bytes(), b"old client")

    def test_source_failure_does_not_touch_client(self):
        self.source.side_effect = RuntimeError("missing OSTree object")
        with patch.object(health, "stop_clients") as stop:
            with self.assertRaisesRegex(RuntimeError, "missing OSTree object"):
                self.h.restore()
        stop.assert_not_called()
        self.assertEqual((self.h.root / "steamrtarm64/steam").read_bytes(), b"old client")

    def test_interrupted_restore_can_be_retried(self):
        save = self.h.root / "userdata/account/save"
        save.parent.mkdir(parents=True)
        save.write_text("keep")
        real_rename = Path.rename
        for name in ("package", "steamrtarm64"):
            for stage in ("live", "new"):
                with self.subTest(name=name, stage=stage):
                    failed_source = (self.h.root if stage == "live" else self.h.work / "new") / name
                    def fail(source, destination):
                        if source == failed_source:
                            raise OSError("simulated interruption")
                        return real_rename(source, destination)
                    with patch.object(Path, "rename", fail):
                        with self.assertRaisesRegex(OSError, "interruption"):
                            self.h.restore()
                    self.assertEqual(save.read_text(), "keep")
                    self.h.restore()
                    self.assertEqual(health.verify_client(self.h.root), 1)
                    self.assertEqual((self.h.root / "steamrtarm64/steam").read_bytes(), b"factory client")
                    self.assertEqual(save.read_text(), "keep")

    def test_custom_root_and_symlink_are_not_repaired(self):
        with patch.dict(os.environ, {"STEAM_ROOT": str(self.base / "custom")}):
            with self.assertRaisesRegex(RuntimeError, "custom"):
                self.h.restore()
        elsewhere = self.base / "elsewhere"
        self.h.root.rename(elsewhere)
        self.h.root.symlink_to(elsewhere)
        with self.assertRaisesRegex(RuntimeError, "symlinked"):
            self.h.restore()
        self.source.assert_not_called()

    def test_busy_repair_does_not_stop_clients(self):
        with self.h.lock(), patch.object(health, "stop_clients") as stop:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                self.h.restore()
        stop.assert_not_called()

    def test_running_client_stops_before_replacement(self):
        executable = self.h.root / "steamrtarm64/steam"
        shutil.copyfile(shutil.which("sleep"), executable)
        client = subprocess.Popen([str(executable), "60"])
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if Path(f"/proc/{client.pid}/exe").resolve() == executable:
                    break
                time.sleep(0.01)
            else:
                self.fail("Client did not launch")
            def extract_while_running(destination, log):
                self.assertIsNone(client.poll())
                self.extract(destination, log)
            self.source.side_effect = extract_while_running
            self.h.restore()
            client.wait(timeout=5)
            self.assertEqual(executable.read_bytes(), b"factory client")
        finally:
            health.stop_clients(self.h.root.resolve())
            if client.poll() is None:
                client.kill()
            client.wait()

    def test_manifest_rejects_path_escape(self):
        (self.factory / "package/steam_client_test_linuxarm64.installed").write_text("../../outside,1;1;1\n")
        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            health.verify_client(self.factory)

    def test_cache_symlink_is_removed_without_deleting_its_target(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep").write_text("keep")
        (self.h.root / "config").mkdir()
        (self.h.root / "config/htmlcache").symlink_to(outside)
        self.h.restore()
        self.assertFalse((self.h.root / "config/htmlcache").is_symlink())
        self.assertEqual((outside / "keep").read_text(), "keep")

    def test_restore_does_not_follow_cache_parent_outside_steam(self):
        outside = self.base / "outside"
        (outside / "htmlcache").mkdir(parents=True)
        (outside / "htmlcache/keep").write_text("keep")
        (self.h.root / "config").symlink_to(outside)
        self.h.restore()
        self.assertEqual((outside / "htmlcache/keep").read_text(), "keep")



class ArchiveTests(unittest.TestCase):
    def test_unsafe_archive_links_and_paths_are_rejected(self):
        for name, link in [("../outside", None), ("link", "/outside")]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                archive = work / "source.tar"
                with tarfile.open(archive, "w") as stream:
                    entry = tarfile.TarInfo(name)
                    if link:
                        entry.type = tarfile.SYMTYPE
                        entry.linkname = link
                        stream.addfile(entry)
                    else:
                        entry.size = 1
                        stream.addfile(entry, io.BytesIO(b"x"))
                destination = work / "stage"
                destination.mkdir()
                popen = subprocess.Popen
                def source(*args, **kwargs):
                    return popen(["cat", str(archive)], **kwargs)
                with patch.object(health.subprocess, "Popen", side_effect=source):
                    with self.assertRaises(tarfile.FilterError):
                        health.extract_source(destination, work / "log")
                self.assertFalse((work / "outside").exists())

    def test_failed_export_reports_source_error(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            destination = work / "stage"
            destination.mkdir()
            popen = subprocess.Popen
            def source(*args, **kwargs):
                return popen([sys.executable, "-c",
                              "import sys; print('No booted OSTree deployment', file=sys.stderr); sys.exit(1)"], **kwargs)
            with patch.object(health.subprocess, "Popen", side_effect=source):
                with self.assertRaisesRegex(RuntimeError, "No booted OSTree deployment"):
                    health.extract_source(destination, work / "log")
            self.assertEqual(list(destination.iterdir()), [])

    def test_low_space_stops_before_writing_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            archive = work / "source.tar"
            with tarfile.open(archive, "w") as stream:
                entry = tarfile.TarInfo("payload")
                entry.size = 1
                stream.addfile(entry, io.BytesIO(b"x"))
            destination = work / "stage"
            destination.mkdir()
            popen = subprocess.Popen
            def source(*args, **kwargs):
                return popen(["cat", str(archive)], **kwargs)
            usage = shutil.disk_usage(work)._replace(free=0)
            with patch.object(health.subprocess, "Popen", side_effect=source), patch.object(health.shutil, "disk_usage", return_value=usage):
                with self.assertRaisesRegex(RuntimeError, "free space"):
                    health.extract_source(destination, work / "log")
            self.assertFalse((destination / "payload").exists())


class IntegrationTests(unittest.TestCase):
    payload = None

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    @unittest.skipUnless(shutil.which("ostree"), "ostree is not installed")
    def test_native_ostree_restore(self):
        work = self.work
        tree = work / "tree"
        factory = tree / "var/home/armada/.local/share/Steam"
        seed(factory)
        expected = (factory / "steamrtarm64/steam").read_bytes()
        repo = work / "repo"
        subprocess.run(["ostree", "init", f"--repo={repo}", "--mode=bare-user"], check=True)
        subprocess.run(["ostree", "commit", f"--repo={repo}", "--branch=factory", f"--tree=dir={tree}"], check=True)
        exporter = work / "export"
        exporter.write_text(f'#!/bin/sh\nexec ostree export --repo={repo} --no-xattrs --subpath=/var/home/armada/.local/share/Steam factory\n')
        exporter.chmod(0o755)
        pkexec = work / "pkexec"
        pkexec.write_text('#!/bin/sh\nshift\nexec "$@"\n')
        pkexec.chmod(0o755)
        target = work / "result"
        target.mkdir()
        with patch.object(health, "SOURCE", str(exporter)), patch.dict(os.environ, {"PATH": f'{work}:{os.environ["PATH"]}'}):
            health.extract_source(target, work / "source.log")
        count = health.verify_client(target)
        assert count > 0
        assert (target / "steamrtarm64/steam").read_bytes() == expected
        assert not (target / "var").exists()
        client = health.SteamMaintenance(work / "home", work / "run")
        seed(client.root, b"broken client")
        with patch.object(health, "SOURCE", str(exporter)), patch.dict(os.environ, {"PATH": f'{work}:{os.environ["PATH"]}'}):
            client.restore()
        assert (client.root / "steamrtarm64/steam").read_bytes() == expected

    def test_bootstrap_payload_restore(self):
        if self.payload is None:
            self.skipTest("pass --payload PATH to test a bootstrap archive")
        work = self.work
        exporter = work / "export"
        exporter.write_text('''#!/usr/bin/python3
import subprocess,tarfile,sys
process=subprocess.Popen(['zstd','-dc',sys.argv[1]],stdout=subprocess.PIPE)
with tarfile.open(fileobj=process.stdout,mode='r|') as source, tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as destination:
 for entry in source:
  name=entry.name.removeprefix('./')
  prefix='.local/share/Steam/'
  if not name.startswith(prefix):continue
  stream=source.extractfile(entry) if entry.isfile() else None
  entry.name=name[len(prefix):]
  destination.addfile(entry,stream)
process.stdout.close()
assert process.wait()==0
''')
        exporter.chmod(0o755)
        source = work / "source"
        source.write_text(f'#!/bin/sh\nexec {shlex.quote(str(exporter))} {shlex.quote(str(self.payload))}\n')
        source.chmod(0o755)
        pkexec = work / "pkexec"
        pkexec.write_text('#!/bin/sh\nshift\nexec "$@"\n')
        pkexec.chmod(0o755)
        client = health.SteamMaintenance(work / "home", work / "run")
        seed(client.root, b"broken client")
        for relative in ["steamapps/common/game/save", "userdata/account/save", "config/loginusers.vdf"]:
            path = client.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("preserved")
        with patch.object(health, "SOURCE", str(source)), patch.dict(os.environ, {"PATH": f'{work}:{os.environ["PATH"]}'}):
            client.restore()
        assert (client.root / "config/loginusers.vdf").read_text() == "preserved"
        assert (client.root / "steamapps/common/game/save").read_text() == "preserved"
        assert (client.root / "userdata/account/save").read_text() == "preserved"
        assert not client.work.exists()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--payload", type=Path)
    arguments, remaining = parser.parse_known_args()
    IntegrationTests.payload = arguments.payload
    unittest.main(argv=[sys.argv[0], *remaining])
