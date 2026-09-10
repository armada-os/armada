#!/usr/bin/env python3
import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import replace
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/armada/armada-installer"
loader = importlib.machinery.SourceFileLoader("installer", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
i = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = i
loader.exec_module(i)


def table(names=(), device="/dev/sda", sector=4096):
    def part(number, start_mib, end_mib, name, kind=i.LINUX_TYPE):
        return i.Partition(number, start_mib * i.MIB // sector, end_mib * i.MIB // sector,
                           name, kind, str(uuid.UUID(int=number)))
    parts = [part(30, 1, 16, "vendor_a", "01234567-1234-1234-1234-123456789abc"),
             part(17, 1024, 32 * 1024 if names else 128 * 1024, "userdata")]
    bounds = [32 * 1024, 32 * 1024 + 512, 34 * 1024, 128 * 1024]
    for index, name in enumerate(names):
        end = bounds[index + 1] if index < len(names) - 1 else 128 * 1024
        parts.append(part(index + 1, bounds[index], end, name, i.ESP_TYPE if index == 0 else i.LINUX_TYPE))
    return i.Table(device, sector, 34, 256 * i.GIB // sector - 34, str(uuid.UUID(int=100)), tuple(sorted(parts, key=lambda p: p.number)))


def applied(plan):
    parts = [replace(p, end=plan.userdata_end) if p == plan.userdata else p
             for p in plan.table.parts if p not in plan.remove]
    parts += [replace(p, uuid=str(uuid.UUID(int=1000 + p.number))) for p in plan.create]
    return replace(plan.table, parts=tuple(sorted(parts, key=lambda p: p.number)), unused=())


def table_json(t):
    return dict(partitiontable=dict(device=t.device, label="gpt", unit="sectors", sectorsize=t.sector_size,
                                   firstlba=t.first, lastlba=t.last, id=t.disk_id, **{"table-length": str(t.entry_count)},
                                   partitions=[dict(node=i.part_node(t.device, p.number), start=p.start, size=p.end-p.start,
                                                    name=p.name, type=p.type, uuid=p.uuid, attrs=p.attrs) for p in t.parts]))


class PlanningTests(unittest.TestCase):
    def test_unused_gpt_slots_ignore_stale_overlapping_geometry(self):
        t = replace(table(), entry_count=32)
        data = table_json(t)
        data["partitiontable"]["partitions"].append(dict(node="/dev/sda18", start=1000, size=999999999,
                                                       type="00000000-0000-0000-0000-000000000000"))
        t = replace(t, unused=(18,))
        self.assertEqual(i.Table.parse(t.device, data), t)
        plan = i.Plan.make(t, 32)
        self.assertNotIn("999999999", plan.script())
        plan.verify(applied(plan))
        with self.assertRaises(i.Error):
            plan.verify(replace(applied(plan), entry_count=128))

    def test_planner_does_not_allocate_beyond_gpt_capacity(self):
        t = table()
        t = replace(t, entry_count=3, parts=tuple(replace(p, number=n) for n, p in enumerate(t.parts, 1)))
        with self.assertRaisesRegex(i.Error, "Not enough free GPT partition slots"):
            i.Plan.make(t, 32)

    def test_parse_roundtrip_devices_and_sector_sizes(self):
        for device in ("/dev/sda", "/dev/mmcblk0", "/dev/nvme0n1"):
            for sector in (512, 4096):
                t = table(device=device, sector=sector)
                self.assertEqual(i.Table.parse(device, table_json(t)), t)
                plan = i.Plan.make(t, 16)
                plan.verify(applied(plan))
                self.assertEqual(plan.create[0].start, plan.userdata_end)
                self.assertEqual((plan.create[0].end-plan.create[0].start)*sector, i.ESP_SIZE)
                self.assertGreaterEqual((plan.create[-1].end-plan.create[-1].start)*sector, i.ROOT_MIN)

    def test_bad_partition_output_is_rejected(self):
        t = table()
        for change in (
            lambda d: d.update(label="dos"),
            lambda d: d.pop("sectorsize"),
            lambda d: d.update(sectorsize=True),
            lambda d: d["partitions"][0].update(node="/dev/sdb1"),
            lambda d: d["partitions"][0].update(size=-1),
            lambda d: d["partitions"][0].update(start=True),
            lambda d: d["partitions"][0].update(start=d["lastlba"]),
            lambda d: d["partitions"][1].update(start=d["partitions"][0]["start"]),
        ):
            data = table_json(t)
            change(data["partitiontable"])
            with self.assertRaises(i.Error):
                i.Table.parse(t.device, data)

    def test_fresh_preserves_android_start_type_uuid_and_high_numbered_vendor(self):
        plan = i.Plan.make(table(), 16)
        actual = applied(plan)
        plan.verify(actual)
        android = next(p for p in actual.parts if p.name == "userdata")
        self.assertEqual(replace(android, end=plan.userdata.end), plan.userdata)
        self.assertEqual([p.number for p in plan.create], [18, 19, 20])
        self.assertIn(next(p for p in plan.table.parts if p.name == "vendor_a"), actual.parts)
        self.assertIn(f"uuid={plan.userdata.uuid}", plan.script())
        self.assertIn(f"/dev/sda17: start={plan.userdata.start}, size={plan.userdata_end-plan.userdata.start}", plan.script())

    def test_replacement_reuses_slots_immediately_after_userdata(self):
        t = table(["ARMADA", "ARMADA_BOOT", "ARMADA_ROOT"])
        t = replace(t, parts=tuple(replace(p, number=p.number+17) if p.number < 4 else p for p in t.parts))
        plan = i.Plan.make(t)
        self.assertEqual([p.number for p in plan.create], [18, 19, 20])
        plan.verify(applied(plan))

    def test_occupied_preferred_slot_falls_back_without_moving_vendor(self):
        for names in ((), ("OTHER_BOOT", "OTHER_ROOT")):
            for occupied in (18, 19, 20):
                with self.subTest(names=names, occupied=occupied):
                    t = table(names)
                    t = replace(t, parts=tuple(replace(p, number=occupied) if p.number == 30 else p for p in t.parts))
                    plan = i.Plan.make(t, None if names else 16)
                    self.assertEqual([p.number for p in plan.create], [1, 2, 3])
                    self.assertIn(next(p for p in t.parts if p.number == occupied), applied(plan).parts)
                    plan.verify(applied(plan))

    def test_preferred_slots_beyond_capacity_fall_back(self):
        t = table()
        t = replace(t, entry_count=32, parts=tuple(replace(p, number=31) if p.name == "userdata" else p for p in t.parts))
        plan = i.Plan.make(t, 16)
        self.assertEqual([p.number for p in plan.create], [1, 2, 3])
        plan.verify(applied(plan))

    def test_userdata_attributes_are_preserved(self):
        attrs = "RequiredPartition LegacyBIOSBootable GUID:48,60,63"
        t = table()
        t = replace(t, parts=tuple(replace(p, attrs=attrs) if p.name == "userdata" else p for p in t.parts))
        self.assertIn('attrs="' + attrs + '"', i.Plan.make(t, 16).script())

    def test_replacement_uses_position_regardless_of_names_or_types(self):
        for names in (["ARMADA", "ARMADA_BOOT", "ARMADA_ROOT"], ["OTHER_BOOT", "OTHER_ROOT"],
                      ["ROCKNIX", "STORAGE"], ["vendor", "metadata"], ["root", "root"], ["", ""]):
            with self.subTest(names=names):
                t = table(names)
                t = replace(t, parts=tuple(replace(p, type="01234567-1234-1234-1234-123456789abc")
                                          if p.name in names else p for p in t.parts))
                plan = i.Plan.make(t)
                self.assertEqual(t.info()["mode"], "occupied")
                self.assertEqual(plan.operation, "replace")
                self.assertEqual(plan.userdata_end, plan.userdata.end)
                self.assertEqual(plan.remove, tuple(sorted((p for p in t.parts if p.start >= plan.userdata.end), key=lambda p: p.start)))
                self.assertNotIn(plan.userdata, plan.remove)
                self.assertIn("Erase ALL partitions after Android userdata", plan.describe())
                for p in plan.remove:
                    self.assertIn(i.part_node(t.device, p.number), plan.describe())
                    self.assertIn(i.part_node(t.device, p.number), t.info()["partition_names"])
                plan.verify(applied(plan))

    def test_single_unknown_tail_partition_can_be_replaced(self):
        plan = i.Plan.make(table(["custom-storage"]))
        self.assertEqual(len(plan.remove), 1)
        self.assertEqual(len(plan.create), 3)

    def test_earlier_partitions_are_preserved_regardless_of_label_or_number(self):
        for name in ("ARMADA", "vendor_a", ""):
            t = table(["custom-storage"])
            t = replace(t, parts=tuple(replace(p, name=name) if p.number == 30 else p for p in t.parts))
            plan = i.Plan.make(t)
            before = next(p for p in t.parts if p.number == 30)
            self.assertNotIn(before, plan.remove)
            self.assertIn(before, applied(plan).parts)
            plan.verify(applied(plan))

    def test_missing_or_duplicate_userdata_is_rejected(self):
        for old, new in (("vendor_a", "userdata"), ("userdata", "data")):
            t = table()
            parts = tuple(replace(p, name=new) if p.name == old else p for p in t.parts)
            with self.assertRaises(i.Error):
                i.Plan.make(replace(t, parts=parts), 16)

    def test_too_small_and_invalid_sizes_are_rejected(self):
        t = table()
        for size in (None, True, 0, 7, 1000):
            with self.assertRaises(i.Error):
                i.Plan.make(t, size)
        short = replace(t, parts=tuple(replace(p, end=p.start+16*i.GIB//t.sector_size) if p.name == "userdata" else p for p in t.parts))
        self.assertEqual(short.info()["mode"], "toosmall")
        with self.assertRaises(i.Error):
            i.Plan.make(short, 8)
        with self.assertRaises(i.Error):
            i.Plan.make(table(["OTHER_BOOT", "OTHER_ROOT"]), 16)

    def test_verification_rejects_changed_android_and_extra_partitions(self):
        plan = i.Plan.make(table(["OTHER_BOOT", "OTHER_ROOT"]))
        good = applied(plan)
        for t in (replace(good, disk_id=str(uuid.uuid4())),
                  replace(good, parts=tuple(replace(p, end=p.end-1) if p.name == "userdata" else p for p in good.parts)),
                  replace(good, parts=tuple(replace(p, uuid=str(uuid.uuid4())) if p.name == "vendor_a" else p for p in good.parts)),
                  replace(good, parts=good.parts[:-1])):
            with self.assertRaises(i.Error):
                plan.verify(t)


class ExecutionTests(unittest.TestCase):
    def test_fingerprint_binds_table_and_kernel_device_identity(self):
        t = table()
        with patch.object(i.os, "stat", return_value=argparse.Namespace(st_rdev=os.makedev(8, 0))), patch.object(Path, "read_text", return_value="10\n"):
            expected = i.table_fingerprint(t)
            self.assertEqual(expected, i.table_fingerprint(t))
            for changed in (replace(t, device="/dev/sdb"), replace(t, disk_id="changed"),
                            replace(t, parts=tuple(replace(p, end=p.end-1) if p.name == "userdata" else p for p in t.parts))):
                self.assertNotEqual(expected, i.table_fingerprint(changed))
            with patch.object(Path, "read_text", return_value="11\n"):
                self.assertNotEqual(expected, i.table_fingerprint(t))
            with patch.object(i.os, "stat", return_value=argparse.Namespace(st_rdev=os.makedev(8, 16))):
                self.assertNotEqual(expected, i.table_fingerprint(t))

    def test_changed_confirmation_aborts_before_planning(self):
        args = argparse.Namespace(command="install", device="/dev/sda", expect_table="confirmed")
        with patch.object(i.os, "geteuid", return_value=0), patch.object(i, "discover_device", return_value="/dev/sda"), patch.object(i, "read_table", return_value=table()), patch.object(i, "table_fingerprint", return_value="changed"), patch.object(i.Plan, "make") as make, patch.object(i, "run") as run:
            with self.assertRaisesRegex(i.Error, "changed after confirmation"):
                i.execute(args)
        make.assert_not_called()
        run.assert_not_called()

    def test_kernel_geometry_in_512_byte_sectors_and_device_nodes(self):
        for sector in (512, 4096):
            for names, size in (((), 16), (("OTHER_BOOT", "OTHER_ROOT"), None)):
                plan = i.Plan.make(table(names, sector=sector), size)
                parts = {i.part_node(plan.table.device, p.number): p for p in applied(plan).parts}
                def read(path):
                    p = parts["/dev/" + path.parent.name]
                    return dict(start=str(p.start * sector // 512), size=str((p.end-p.start) * sector // 512), dev=f"8:{p.number}")[path.name]
                def stat(node):
                    return argparse.Namespace(st_rdev=os.makedev(8, parts[node].number))
                with patch.object(Path, "read_text", read), patch.object(i.os, "stat", side_effect=stat):
                    plan.verify_kernel()
                    for attribute in ("start", "size", "dev"):
                        def bad_read(path):
                            return ("8:99" if attribute == "dev" else "1") if path.name == attribute else read(path)
                        with patch.object(Path, "read_text", bad_read), self.assertRaisesRegex(i.Error, "does not match"):
                            plan.verify_kernel()
                    with patch.object(Path, "read_text", side_effect=FileNotFoundError("missing partition")), self.assertRaisesRegex(i.Error, "Could not verify"):
                        plan.verify_kernel()

    def test_kernel_mismatch_stops_before_userdata_wipe(self):
        plan = i.Plan.make(table(), 16)
        job = i.Installation(plan)
        with patch.object(i, "refuse_boot_disk"), patch.object(i, "require_idle"), patch.object(i, "read_table", side_effect=[plan.table, applied(plan)]), patch.object(i.Plan, "verify_kernel", side_effect=i.Error("stale kernel geometry")), patch.object(i, "run") as run:
            with self.assertRaisesRegex(i.Error, "stale kernel geometry"):
                job.partition()
        self.assertFalse(any(call.args[0] == "dd" for call in run.call_args_list))
        self.assertTrue(job.changed)

    def test_preflight_uses_source_context_without_target_discovery(self):
        for failed in (False, True):
            events = []
            @contextmanager
            def source():
                events.append("locked")
                try:
                    if failed:
                        raise i.Error("corrupt source")
                    yield Mock(checksum="selected")
                finally:
                    events.append("released")
            with patch.object(i.os, "geteuid", return_value=0), patch.object(i, "locked_source", source), patch.object(i, "inhibit_sleep", return_value=nullcontext()), patch.object(i, "repo_path", return_value="/source/repo"), patch.object(i, "run") as run, patch.object(i, "discover_device") as discover, patch.object(i.Installation, "partition") as partition, patch("sys.stdout", new_callable=io.StringIO) as out:
                if failed:
                    with self.assertRaisesRegex(i.Error, "corrupt source"):
                        i.execute(argparse.Namespace(command="preflight"))
                else:
                    i.execute(argparse.Namespace(command="preflight"))
                    self.assertIn("Validated source commit: selected", out.getvalue())
                    self.assertIn("seconds; internal storage was not touched", out.getvalue())
                    run.assert_called_once_with("ostree", "fsck", "--repo=/source/repo")
            self.assertEqual(events, ["locked", "released"])
            discover.assert_not_called()
            partition.assert_not_called()

    def test_changed_table_aborts_without_writing(self):
        plan = i.Plan.make(table(), 16)
        job = i.Installation(plan)
        with patch.object(i, "refuse_boot_disk"), patch.object(i, "read_table", return_value=replace(plan.table, disk_id="changed")), patch.object(i, "run") as run:
            with self.assertRaisesRegex(i.Error, "changed after inspection"):
                job.partition()
        run.assert_not_called()
        self.assertFalse(job.changed)

    def test_in_use_target_aborts_without_writing(self):
        plan = i.Plan.make(table(), 16)
        job = i.Installation(plan)
        with patch.object(i, "refuse_boot_disk"), patch.object(i, "read_table", return_value=plan.table), patch.object(i, "require_idle", side_effect=i.Error("in use")), patch.object(i, "run") as run:
            with self.assertRaisesRegex(i.Error, "in use"):
                job.partition()
        run.assert_not_called()
        self.assertFalse(job.changed)

    def test_partition_operations_wipe_android_only_on_fresh_install(self):
        for t, size in ((table(), 16), (table(["OTHER_BOOT", "OTHER_ROOT"]), None)):
            plan = i.Plan.make(t, size)
            job = i.Installation(plan)
            with patch.object(i, "refuse_boot_disk"), patch.object(i, "require_idle"), patch.object(i, "read_table", side_effect=[t, applied(plan)]), patch.object(i.Plan, "verify_kernel"), patch.object(i, "run") as run:
                job.partition()
            commands = [call.args for call in run.call_args_list]
            self.assertEqual(sum(c[0] == "dd" for c in commands), int(plan.operation == "fresh"))
            self.assertTrue(job.changed)

    def test_partition_failure_arms_recovery_and_stops_commands(self):
        plan = i.Plan.make(table(), 16)
        with patch.object(i, "refuse_boot_disk"), patch.object(i, "require_idle"), patch.object(i, "read_table", return_value=plan.table), patch.object(i, "run", side_effect=i.Error("write failed")) as run, patch("sys.stderr", new_callable=io.StringIO) as err:
            with self.assertRaisesRegex(i.Error, "write failed"):
                with i.operation(plan) as job:
                    job.partition()
        self.assertEqual(run.call_count, 1)
        self.assertIn("Internal storage was modified", err.getvalue())

    def test_source_repository_is_readonly_before_validation(self):
        for remount_fails in (False, True):
            api = Mock()
            sysroot = api.Sysroot.new_default.return_value
            repo = Mock()
            repo.get_path.return_value.get_path.return_value = "/sysroot/ostree/repo"
            sysroot.get_repo.return_value = (True, repo)
            events = []
            def command(*args):
                events.append(args)
                if remount_fails and "remount,bind,ro" in args:
                    raise i.Error("read-only mount failed")
            def validate(*args):
                self.assertIn(("mount", "-o", "remount,bind,ro", "/sysroot/ostree/repo"), events)
                return "validated"
            with patch.object(i, "ostree_api", return_value=(Mock(), api)), patch.object(i, "repo_path", return_value="/sysroot/ostree/repo"), patch.object(i, "run", side_effect=command), patch.object(i.SourceImage, "read", side_effect=validate) as read:
                if remount_fails:
                    with self.assertRaisesRegex(i.Error, "read-only mount failed"):
                        with i.locked_source():
                            self.fail("unprotected source was accepted")
                    read.assert_not_called()
                else:
                    with i.locked_source() as source:
                        self.assertEqual(source, "validated")
                        sysroot.unlock.assert_not_called()
                self.assertEqual(events[-1], ("umount", "/sysroot/ostree/repo"))
                sysroot.unlock.assert_called_once()

    def test_source_failure_never_reaches_partitioning(self):
        args = argparse.Namespace(command="install", device=None, userdata_gib=16, assume_yes=True, expect_table=None)
        @contextmanager
        def bad_source():
            raise i.Error("missing source layer")
            yield
        with tempfile.TemporaryFile() as lock, patch.object(i.os, "geteuid", return_value=0), patch.object(i, "discover_device", return_value="/dev/sda"), patch.object(i, "read_table", return_value=table()), patch.object(i, "require_commands"), patch.object(i, "refuse_boot_disk"), patch.object(i, "require_idle"), patch.object(i, "open", return_value=lock, create=True), patch.object(i, "inhibit_sleep", return_value=nullcontext()), patch.object(i, "base_kargs", return_value=[]), patch.object(i, "locked_source", bad_source), patch.object(i.Installation, "partition") as partition:
            with self.assertRaisesRegex(i.Error, "missing source layer"):
                i.execute(args)
        partition.assert_not_called()

    def test_boot_image_scratch_ignores_sd_tmpdir(self):
        job = i.Installation(i.Plan.make(table(), 16))
        source = Mock(checksum="selected")
        source.origin.to_data.return_value = ("origin", 6)
        mkdtemp = tempfile.mkdtemp
        with tempfile.TemporaryDirectory() as work:
            def temporary(*args, **kwargs):
                if kwargs.get("dir") == "/run":
                    kwargs["dir"] = work
                return mkdtemp(*args, **kwargs)
            def command(*args, **kwargs):
                if args[:2] == ("ostree", "checkout"):
                    args[-1].mkdir()
                elif args[0] == i.BOOTIMG:
                    env = kwargs["env"]
                    scratch = Path(env["TMPDIR"])
                    self.assertEqual(scratch.parent, job.work / "target")
                    self.assertTrue(scratch.is_dir())
                    (Path(env["ESP"]) / "KERNEL").write_bytes(b"boot image")
            with patch.dict(i.os.environ, TMPDIR="/sd/slow"), patch.object(i.tempfile, "mkdtemp", side_effect=temporary), patch.object(i, "output", return_value="valid-uuid"), patch.object(i, "run", side_effect=command) as run, patch.object(i, "configure_deployment"):
                job.deploy(source, [])
                self.assertTrue(any(call.args[0] == i.BOOTIMG for call in run.call_args_list))
                self.assertTrue(any(call.args[-2:] == ("sysroot.readonly", "true") for call in run.call_args_list))
                self.assertEqual(list((job.work / "target").glob(".armada-bootimg.*")), [])
                job.close()

    def test_interrupted_mount_is_still_cleaned_up(self):
        for mounted in (True, False):
            job = i.Installation(i.Plan.make(table(), 16))
            with tempfile.TemporaryDirectory() as work:
                target = Path(work) / "target"
                with patch.object(i, "run", side_effect=i.Interrupted(signal.SIGTERM)), patch.object(Path, "is_mount", return_value=mounted):
                    with self.assertRaises(i.Interrupted):
                        job.mount("/dev/fake", target)
                self.assertEqual(job.mounts, [target] if mounted else [])

    def test_copy_failure_prevents_deployment_and_boot_image(self):
        job = i.Installation(i.Plan.make(table(), 16))
        source = Mock()
        source.copy.side_effect = i.Error("corrupt destination")
        with tempfile.TemporaryDirectory() as work:
            with patch.object(i.tempfile, "mkdtemp", return_value=work), patch.object(i, "output", return_value="a-valid-uuid"), patch.object(i, "run") as run:
                with self.assertRaisesRegex(i.Error, "corrupt destination"):
                    job.deploy(source, [])
                commands = [call.args for call in run.call_args_list]
                self.assertFalse(any(c[:3] == ("ostree", "admin", "deploy") or c[0] == i.BOOTIMG for c in commands))
                source.copy.assert_called_once_with(Path(work) / "target")
                mounts = list(job.mounts)
                job.close()
                self.assertEqual([call.args[1] for call in run.call_args_list if call.args[0] == "umount"][1:], list(reversed(mounts)))

    def test_cleanup_is_reverse_order_and_preserves_failed_mount(self):
        job = i.Installation(i.Plan.make(table(), 16))
        with tempfile.TemporaryDirectory() as work:
            job.work = Path(work) / "keep"
            job.work.mkdir()
            job.mounts = [job.work / "root", job.work / "root/boot", job.work / "root/boot/efi"]
            def unmount(*args):
                if args[1] == job.mounts[-1]:
                    raise i.Error("busy")
            with patch.object(i, "run", side_effect=unmount) as run, patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(i.Error):
                    job.close()
            self.assertEqual([call.args[1] for call in run.call_args_list], list(reversed(job.mounts)))
            self.assertTrue(job.work.exists())

    def test_cleanup_failure_does_not_hide_original_failure(self):
        with patch.object(i.Installation, "close", side_effect=i.Error("cleanup failed")):
            with self.assertRaisesRegex(i.Error, "original"):
                with i.operation(i.Plan.make(table(), 16)):
                    raise i.Error("original")

    def test_boot_disk_alias_is_rejected(self):
        with patch.object(Path, "is_mount", return_value=True), patch.object(Path, "is_block_device", return_value=True), patch.object(i, "output", side_effect=["/dev/dm-0[/root]", "253:0\n8:2\n8:0"]), patch.object(i.os, "stat", return_value=argparse.Namespace(st_rdev=os.makedev(8, 0))):
            with self.assertRaisesRegex(i.Error, "booted from"):
                i.refuse_boot_disk("/dev/disk/by-id/internal")

    def test_mount_in_pid1_namespace_blocks_install(self):
        plan = i.Plan.make(table(), 16)
        def read(path, *args, **kwargs):
            return "1 0 8:17 / /android rw - ext4 /dev/sda17 rw\n" if str(path) == "/proc/1/mountinfo" else "Filename Type Size Used Priority\n" if str(path) == "/proc/swaps" else ""
        with patch.object(Path, "read_text", read), patch.object(Path, "iterdir", return_value=iter(())), patch.object(i.os, "stat", return_value=argparse.Namespace(st_rdev=os.makedev(8, 17))):
            with self.assertRaisesRegex(i.Error, "in use"):
                i.require_idle(plan)

    def test_gui_confirms_all_tail_partitions_without_distro_detection(self):
        info = table(["vendor", "metadata"]).info()
        info.update(device="/dev/sda", table_fingerprint="confirmed")
        gui = i.Gui(None)
        with patch.object(i, "output", return_value=json.dumps(info)), patch.object(gui, "confirm") as confirm, patch.object(gui, "progress") as progress, patch.object(gui, "dialog", return_value=Mock(returncode=1)):
            gui.start()
        self.assertIn("All data in that space will be erased", confirm.call_args.args[0])
        self.assertIn(info["partition_names"], confirm.call_args.args[0])
        progress.assert_called_once_with(["install", "--expect-table", "confirmed"])
        self.assertEqual(gui.command, ["sudo", i.SELF, "--device", "/dev/sda"])

    def test_gui_failure_shows_bounded_log_and_recovery(self):
        gui = i.Gui(None)
        with tempfile.TemporaryDirectory() as work:
            log = Path(work) / "install.log"
            fd = os.open(log, os.O_CREAT | os.O_WRONLY, 0o600)
            def command(*args, **kwargs):
                kwargs["stdout"].write("old output\n" * 1000 + "ERROR: missing source layer\n")
                return Mock(returncode=1)
            with patch.object(i.tempfile, "mkstemp", return_value=(fd, str(log))), patch.object(i.subprocess, "Popen"), patch.object(i, "run", side_effect=command):
                with self.assertRaises(i.Error) as error:
                    gui.progress(["install"])
            message = str(error.exception)
            self.assertIn("ERROR: missing source layer", message)
            self.assertIn("select SD as the boot source in ABL", message)
            self.assertIn("available until reboot", message)
            self.assertLess(len(message), 5000)

    def test_reset_is_not_a_command(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "reset", "-y"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("UNINSTALL CFW", result.stdout)
        self.assertNotIn("reset", result.stdout)

    def test_toml_kargs_are_parsed_and_filtered(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root/"a.toml").write_text('kargs = ["quiet", "root=old", "rootflags=old", "ostree=old"]\n')
            (root/"b.toml").write_text('match-architectures = ["other"]\nkargs = ["bad"]\n')
            self.assertEqual(i.base_kargs(root), ["quiet"])

    def test_subprocess_cancellation_waits_for_cleanup(self):
        with tempfile.TemporaryDirectory() as work:
            ready, cleaned = Path(work)/"ready", Path(work)/"cleaned"
            child_code = f"""
import signal,sys,time
from pathlib import Path
def stop(signum, frame):
    time.sleep(0.1)
    Path({str(cleaned)!r}).touch()
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
Path({str(ready)!r}).touch()
time.sleep(10)
"""
            parent_code = f"""
import runpy,sys
m=runpy.run_path({str(SCRIPT)!r})
try: m['run'](sys.executable, '-c', {child_code!r})
except m['Interrupted']: sys.exit(143)
"""
            parent = subprocess.Popen([sys.executable, "-c", parent_code])
            try:
                deadline = time.monotonic()+5
                while not ready.exists() and time.monotonic()<deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists())
                parent.send_signal(signal.SIGTERM)
                self.assertEqual(parent.wait(timeout=5), 143)
                self.assertTrue(cleaned.exists())
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait()


if __name__ == "__main__":
    unittest.main()
