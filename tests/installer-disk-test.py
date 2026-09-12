#!/usr/bin/env python3
"""Exercise real GPT edits on sparse regular files, never on block devices."""
from dataclasses import replace
from pathlib import Path
import runpy
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
i = runpy.run_path(str(ROOT / "system_files/usr/libexec/armada/armada-installer"))
run, output = i["run"], i["output"]


class DiskTests(unittest.TestCase):
    def test_fresh_and_position_based_replacement(self):
        for names in (None, ("OTHER_BOOT", "OTHER_ROOT"), ("vendor", "metadata"), ("", "")):
            existing = names is not None
            with self.subTest(names=names), tempfile.TemporaryDirectory() as work:
                disk = Path(work) / "disk.img"
                with disk.open("wb") as stream:
                    stream.truncate(128 * i["GIB"])
                self.assertTrue(disk.is_file())
                self.assertFalse(disk.is_block_device())
                sector = 512
                end = 128 * i["GIB"] // sector - 2048
                userdata_end = 32 * i["GIB"] // sector if existing else end
                run("sgdisk", "--clear", "--new=30:2048:32767", '--change-name=30:vendor "A"\\backup α\n', "--typecode=30:8300",
                    f"--new=17:{i['GIB']//sector}:{userdata_end-1}", "--change-name=17:userdata", "--typecode=17:8300", "--attributes=17:set:0", "--attributes=17:set:63", disk)
                if existing:
                    boot_end = userdata_end + 512 * i["MIB"] // sector
                    run("sgdisk", f"--new=1:{userdata_end}:{boot_end-1}", f"--change-name=1:{names[0]}", "--typecode=1:0700",
                        f"--new=2:{boot_end}:{end-1}", f"--change-name=2:{names[1]}", "--typecode=2:0700", disk)
                original = i["read_table"](str(disk))
                plan = i["Plan"].make(original, None if existing else 16)
                plan.write()
                after = i["read_table"](str(disk))
                plan.verify(after)
                self.assertIn("No problems found", output("sgdisk", "--verify", disk))
                ud = next(p for p in after.parts if p.name == "userdata")
                self.assertEqual(replace(ud, end=plan.userdata.end), plan.userdata)
                self.assertIn(next(p for p in original.parts if p.number == 30), after.parts)
                if existing:
                    self.assertEqual(ud, plan.userdata)


if __name__ == "__main__":
    unittest.main()
