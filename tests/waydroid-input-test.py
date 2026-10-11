#!/usr/bin/python3
import ctypes
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import select
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "waydroid_input", str(ROOT / "system_files/usr/libexec/armada/waydroid-input-setup"))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class SelectionTests(unittest.TestCase):
    def test_only_tagged_hidden_event_nodes_are_selected(self):
        records = []
        for name, shared in [("event1", "1"), ("event2", "0"), ("js0", "1"), ("event3", "1")]:
            records.append(f"E: DEVNAME=/dev/input/{name}\nE: MAJOR=13\nE: MINOR=65\n"
                           f"E: INPUTPLUMBER_SHARED_GAMEPAD={shared}\nE: DEVPATH=/devices/input/input6/{name}")

        class NodeStat:
            st_rdev = os.makedev(13, 65)
            st_mode = stat.S_IFCHR

        def node_stat(path):
            result = NodeStat()
            if path.name == "event3":
                result.st_mode |= 0o660
            return result

        with patch.object(module, "command", return_value="\n\n".join(records)), \
                patch.object(Path, "stat", node_stat):
            self.assertEqual(module.shared_devices(), {"event1": (os.makedev(13, 65), "/devices/input/input6/event1")})

    def test_subscription_header_and_input_events_request_reconciliation(self):
        controller = module.ControllerInput()
        with patch.object(controller, "request") as request:
            controller.input_event("monitor will print the received events for:")
            request.assert_not_called()
            controller.input_event("UDEV - the event which udev sends out after rule processing")
            request.assert_called_once()
            controller.input_event("UDEV [12.0] remove /devices/test/input/input2/event5 (input)")
            controller.input_event("UDEV [12.1] add /devices/test/input/input8/event5 (input)")
            controller.input_event("UDEV [12.2] add /devices/test/input/input8/js0 (input)")
            self.assertEqual(request.call_count, 3)

    def test_container_restart_invalidates_preparation(self):
        controller = module.ControllerInput()
        controller.configured = ("123", 1, 2)
        with patch.object(controller, "request") as request:
            controller.container_event("'waydroid' changed state to [STOPPED]")
            self.assertIsNone(controller.configured)
            controller.container_event("'waydroid' changed state to [RUNNING]")
            request.assert_called_once()

    def test_event_arriving_during_reconciliation_causes_another_pass(self):
        controller = module.ControllerInput()
        passes = []
        script = ("import sys; "
                  "print('UDEV [1] add /devices/input/event5 (input)', flush=True); "
                  "sys.stdin.read(1); "
                  "print('UDEV [2] remove /devices/input/event5 (input)', flush=True); "
                  "sys.stdin.read(1)")
        process = subprocess.Popen(["/usr/bin/python3", "-c", script],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        def update():
            controller.pending = 0
            passes.append(1)
            if len(passes) == 1:
                process.stdin.write(b"1")
                process.stdin.flush()
                self.assertTrue(select.select([process.stdout], [], [], 2)[0])
            else:
                controller.loop.quit()
            return module.GLib.SOURCE_REMOVE

        controller.update = update
        with patch.object(module.subprocess, "Popen", return_value=process):
            controller.watch_process(["test-monitor"], controller.input_event)
        timeout = module.GLib.timeout_add(3000, lambda: controller.loop.quit())
        try:
            controller.loop.run()
            self.assertEqual(len(passes), 2)
        finally:
            module.GLib.source_remove(timeout)
            for process in controller.processes:
                process.terminate()
                process.wait()
                process.stdin.close()

    def test_bottom_screen_reconciles_to_empty_without_querying_controllers(self):
        controller = module.ControllerInput()
        with tempfile.TemporaryDirectory() as directory:
            dev = Path(directory)
            info = dev.stat()
            controller.configured = ("123", info.st_dev, info.st_ino)
            real_open = os.open
            result = subprocess.CompletedProcess([], 0, stdout="123\n")
            with patch.object(module.subprocess, "run", return_value=result), \
                    patch.object(module.os, "open", side_effect=lambda *_: real_open(dev, os.O_RDONLY)), \
                    patch.object(module, "BOTTOM_SCREEN", dev), \
                    patch.object(module, "shared_devices") as shared, \
                    patch.object(module, "reconcile_nodes") as reconcile:
                controller.update()
                shared.assert_not_called()
                self.assertEqual(reconcile.call_args.args[1], {})

    def test_saved_properties_load_before_disabling_hotplug_and_publishing(self):
        controller = module.ControllerInput()
        controller.deadline = module.time.monotonic() + 30
        with tempfile.TemporaryDirectory() as directory:
            dev = Path(directory)
            real_open = os.open
            result = subprocess.CompletedProcess([], 0, stdout="123\n")
            with patch.object(module.subprocess, "run", return_value=result), \
                    patch.object(module.os, "open", side_effect=lambda *_: real_open(dev, os.O_RDONLY)), \
                    patch.object(module, "command", return_value="") as command, \
                    patch.object(module, "reconcile_nodes") as reconcile:
                controller.update()
                reconcile.assert_not_called()
                self.assertEqual(command.call_args.args[-1], "ro.persistent_properties.ready")
                self.assertIsNone(controller.configured)
                module.GLib.source_remove(controller.pending)
                controller.pending = 0
                command.side_effect = ["true\n", ""]
                with patch.object(module, "install_keylayouts"), \
                        patch.object(module, "shared_devices", return_value={}):
                    controller.update()
                self.assertEqual(command.call_args.args[-2:], ("persist.waydroid.uevent", "false"))
                reconcile.assert_called_once()
                self.assertIsNotNone(controller.configured)


@unittest.skipUnless(os.geteuid() == 0, "device-node tests require root")
class NodeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.dev = self.root / "dev"
        self.inputs = self.dev / "input"
        self.inputs.mkdir(parents=True)
        os.mkfifo(self.inputs / "wl_touch_events")

    def tearDown(self):
        self.directory.cleanup()

    def test_reconcile_removes_stale_nodes_preserves_pipes_and_reopens_reused_number(self):
        desired = {"event5": (os.makedev(1, 3), "/devices/input/input1/event5")}
        module.reconcile_nodes(self.dev, desired, {})
        published = desired.copy()
        node = self.inputs / "event5"
        old_fd = os.open(node, os.O_RDONLY)
        try:
            old_inode = node.stat().st_ino
            module.reconcile_nodes(self.dev, desired, published)
            self.assertEqual(node.stat().st_ino, old_inode)
            desired["event5"] = (os.makedev(1, 3), "/devices/input/input2/event5")
            module.reconcile_nodes(self.dev, desired, published)
            self.assertNotEqual(node.stat().st_ino, old_inode)
        finally:
            os.close(old_fd)
        module.reconcile_nodes(self.dev, {}, desired)
        self.assertFalse(node.exists())
        self.assertTrue(stat.S_ISFIFO((self.inputs / "wl_touch_events").stat().st_mode))
        self.assertEqual(list(self.dev.glob(".armada-input-*")), [])

    def test_proc_root_publication_delivers_create_with_final_permissions(self):
        libc = ctypes.CDLL(None, use_errno=True)
        watch = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        self.assertGreaterEqual(watch, 0)
        self.addCleanup(os.close, watch)
        self.assertGreaterEqual(libc.inotify_add_watch(watch, os.fsencode(self.inputs), 0x100), 0)
        ready_r, ready_w = os.pipe()
        stop_r, stop_w = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(ready_r)
                os.close(stop_w)
                os.chroot(self.root)
                os.chdir("/")
                os.write(ready_w, b"1")
                os.read(stop_r, 1)
            finally:
                os._exit(0)
        os.close(ready_w)
        os.close(stop_r)
        try:
            self.assertTrue(select.select([ready_r], [], [], 5)[0])
            self.assertEqual(os.read(ready_r, 1), b"1")
            module.reconcile_nodes(Path(f"/proc/{pid}/root/dev"),
                                   {"event5": (os.makedev(1, 3), "/devices/input/input1/event5")}, {})
            self.assertTrue(select.select([watch], [], [], 5)[0])
            event = os.read(watch, 4096)
            _, mask, _, length = struct.unpack_from("iIII", event)
            self.assertTrue(mask & 0x100)
            self.assertEqual(event[16:16 + length].rstrip(b"\0"), b"event5")
            info = (self.inputs / "event5").stat()
            self.assertEqual((stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid), (0o660, 0, 1004))
        finally:
            os.close(ready_r)
            os.close(stop_w)
            os.waitpid(pid, 0)


if __name__ == "__main__":
    unittest.main()
