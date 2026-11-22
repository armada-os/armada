#!/usr/bin/env python3
# armada-components and components/publish.py end to end: signed manifests served over HTTP,
# install, replacement, refusals, and the Turnip picker seeing the installed build.
import contextlib
import functools
import http.server
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
import armada_turnip  # noqa: E402

loader = importlib.machinery.SourceFileLoader(
    "armada_components", str(ROOT / "system_files/usr/libexec/armada/armada-components"))
spec = importlib.util.spec_from_loader(loader.name, loader)
components = importlib.util.module_from_spec(spec)
loader.exec_module(components)
PUBLISH = ROOT / "components/publish.py"


def keypair(directory, name):
    key = directory / name
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    return key


class ComponentsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.out = self.dir / "published"
        self.key = keypair(self.dir, "key")
        signers = self.dir / "allowed_signers"
        signers.write_text(f'armada-components namespaces="armada-components" {Path(f"{self.key}.pub").read_text()}')

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.out))
        handler.log_message = lambda *args: None
        self.out.mkdir()
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        for name, value in (("ROOT", self.dir / "var"), ("SIGNERS", str(signers)),
                            ("BASE_URL", f"http://127.0.0.1:{server.server_port}")):
            setattr(components, name, value)
        os.environ["ARMADA_COMPONENTS_CHANNEL"] = "testing"
        self.addCleanup(os.environ.pop, "ARMADA_COMPONENTS_CHANNEL")
        # other tests leave fake Steam reapers running; tests opt in to a running game
        running = unittest.mock.patch.object(components, "game_running", return_value=False)
        running.start()
        self.addCleanup(running.stop)

    def payload(self, label):
        variant = self.dir / "payload" / label / "devel"
        (variant / "aarch64").mkdir(parents=True)
        (variant / "aarch64" / armada_turnip.LIBRARY).write_bytes(b"\x7fELF" + label.encode())
        (variant / "icd.aarch64.json").write_text('{"ICD": {}}')
        (variant / "variant.json").write_text(json.dumps({"label": "Devel", "version": label}))
        return variant.parent

    def publish(self, *args, key=None):
        subprocess.run([sys.executable, str(PUBLISH), *args, "--out", str(self.out),
                        "--key", str(key or self.key)], check=True, capture_output=True)

    def add(self, version, channel="testing", min_os_api=1, **kwargs):
        self.publish("add", "--channel", channel, "--name", "turnip", "--version", version,
                     "--payload", str(self.payload(version)), "--min-os-api", str(min_os_api), **kwargs)

    def update(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return components.main(["armada-components", "update"])

    def installed(self):
        return (components.installed("turnip") or {}).get("version")

    def home(self):
        return components.ROOT / "turnip"

    def test_install_replace_and_keep_one_old_build(self):
        self.add("1")
        self.assertEqual(self.update(), 0)
        self.assertEqual(self.installed(), "1")
        lib = self.home() / "current/devel/aarch64" / armada_turnip.LIBRARY
        self.assertEqual(lib.read_bytes(), b"\x7fELF1")
        self.assertEqual(self.update(), 0)  # nothing new: no change
        self.add("2")
        self.add("3")
        self.assertEqual(self.update(), 0)
        self.assertEqual(self.installed(), "3")
        self.add("4")
        self.assertEqual(self.update(), 0)
        builds = [p for p in self.home().iterdir() if p.is_dir() and not p.is_symlink()]
        self.assertEqual(len(builds), 1)
        self.assertEqual(sorted(p.name for p in self.home().iterdir() if p.name.startswith(".")), [])

    def test_republishing_the_same_bytes_keeps_the_entry(self):
        payload = str(self.payload("1"))
        for version in ("1+aaa", "1+bbb"):
            self.publish("add", "--channel", "testing", "--name", "turnip", "--version", version,
                         "--payload", payload)
        entry = json.loads((self.out / "testing.json").read_text())["components"]["turnip"]
        self.assertEqual(entry["version"], "1+aaa")
        self.assertEqual(entry["min_os_api"], components.OS_API)  # the tree's own

    def test_a_running_game_defers_activation_not_the_download(self):
        self.add("1")
        self.update()
        self.add("2")
        with unittest.mock.patch.object(components, "game_running", return_value=True):
            self.assertEqual(self.update(), 0)
        self.assertEqual(self.installed(), "1")
        for blob in (self.out / "turnip").iterdir():
            blob.unlink()  # already unpacked: activating must not download again
        self.assertEqual(self.update(), 0)
        self.assertEqual(self.installed(), "2")

    def test_refuses_a_manifest_signed_by_another_key(self):
        self.add("1", key=keypair(self.dir, "other"))
        self.assertEqual(self.update(), 1)
        self.assertIsNone(self.installed())

    def test_refuses_another_channels_manifest(self):
        self.add("1", channel="beta")
        (self.out / "beta.json").rename(self.out / "testing.json")
        (self.out / "beta.json.sig").rename(self.out / "testing.json.sig")
        self.assertEqual(self.update(), 1)
        self.assertIsNone(self.installed())

    def test_a_tampered_blob_leaves_the_old_build(self):
        self.add("1")
        self.update()
        self.add("2")
        blob = next(p for p in (self.out / "turnip").iterdir()
                    if p.name.startswith(json.loads((self.out / "testing.json").read_text())
                                         ["components"]["turnip"]["sha256"]))
        blob.write_bytes(blob.read_bytes()[:-1] + b"x")
        self.assertEqual(self.update(), 1)
        self.assertEqual(self.installed(), "1")
        self.assertFalse((self.home() / ".staging").exists() or (self.home() / ".download").exists())

    def test_skips_a_build_for_a_newer_os(self):
        self.add("1", min_os_api=components.OS_API + 1)
        self.assertEqual(self.update(), 0)
        self.assertIsNone(self.installed())

    def test_os_rollback_drops_a_build_the_image_is_too_old_for(self):
        self.add("1", min_os_api=components.OS_API)
        self.update()
        old_api = components.OS_API
        components.OS_API -= 1
        self.addCleanup(setattr, components, "OS_API", old_api)
        (self.out / "testing.json").unlink()  # offline: the check must not need the manifest
        self.assertEqual(self.update(), 1)
        self.assertIsNone(self.installed())
        self.assertFalse((self.home() / "current").exists())

    def test_unknown_components_are_ignored(self):
        self.publish("add", "--channel", "testing", "--name", "future", "--version", "1",
                     "--payload", str(self.payload("1")))
        self.assertEqual(self.update(), 0)
        self.assertFalse((components.ROOT / "future").exists())

    def test_promote_copies_the_entry_and_signs(self):
        self.add("1")
        self.publish("promote", "--from", "testing", "--to", "beta", "--name", "turnip")
        testing, beta = (json.loads((self.out / f"{c}.json").read_text()) for c in ("testing", "beta"))
        self.assertEqual(beta["channel"], "beta")
        self.assertEqual(beta["components"]["turnip"], testing["components"]["turnip"])
        os.environ["ARMADA_COMPONENTS_CHANNEL"] = "beta"
        self.assertEqual(self.update(), 0)
        self.assertEqual(self.installed(), "1")

    def test_turnip_picker_prefers_the_installed_build(self):
        system = self.dir / "image-turnip"
        for name, version in (("stable", "26.3.0"), ("devel", "image")):
            (system / name / "aarch64").mkdir(parents=True)
            (system / name / "aarch64" / armada_turnip.LIBRARY).write_bytes(b"")
            (system / name / "icd.aarch64.json").write_text("{}")
            (system / name / "variant.json").write_text(json.dumps({"label": name, "version": version}))
        self.add("remote")
        self.update()
        for name, value in (("SYSTEM_DIR", system), ("COMPONENT_DIR", self.home() / "current")):
            old = getattr(armada_turnip, name)
            setattr(armada_turnip, name, value)
            self.addCleanup(setattr, armada_turnip, name, old)
        listed = {d["id"]: d["version"] for d in armada_turnip.list_drivers(self.dir)}
        self.assertEqual(listed, {"stable": "26.3.0", "devel": "remote"})
        # arm64 from the remote build; x86 from the image's path, which the FEX guest provides
        self.assertEqual(armada_turnip.system_manifests("devel"),
                         [str(self.home() / "current/devel/icd.aarch64.json"),
                          str(system / "devel/icd.x86_64.json"), str(system / "devel/icd.i686.json")])
        self.assertIsNone(armada_turnip.flatpak_manifest("devel"))  # no flatpak manifest in the image fixture

    def test_same_bytes_with_new_metadata_refresh_the_record(self):
        self.publish("add", "--channel", "testing", "--name", "turnip", "--version", "1",
                     "--payload", str(self.payload("1")))
        self.update()
        manifest = json.loads((self.out / "testing.json").read_text())
        manifest["components"]["turnip"]["min_os_api"] = components.OS_API + 1
        (self.out / "testing.json").write_text(json.dumps(manifest))
        (self.out / "testing.json.sig").unlink()
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(self.key), "-n", "armada-components",
                        str(self.out / "testing.json")], check=True)
        self.assertEqual(self.update(), 0)  # too new for this image now: left installed
        self.assertEqual(components.installed("turnip")["min_os_api"], 1)
        manifest["components"]["turnip"]["min_os_api"] = components.OS_API
        manifest["components"]["turnip"]["version"] = "1-renamed"
        (self.out / "testing.json").write_text(json.dumps(manifest))
        (self.out / "testing.json.sig").unlink()
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(self.key), "-n", "armada-components",
                        str(self.out / "testing.json")], check=True)
        self.update()
        self.assertEqual(self.installed(), "1-renamed")

    def test_retire_runs_without_the_network(self):
        self.add("1")
        self.update()
        old_api = components.OS_API
        components.OS_API = 0
        self.addCleanup(setattr, components, "OS_API", old_api)
        components.BASE_URL = "http://127.0.0.1:9"  # nothing listens: retire must not fetch
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(components.main(["armada-components", "retire"]), 0)
        self.assertIsNone(self.installed())

    def test_proton_payload_gets_its_own_stable_tool_name(self):
        tree = self.dir / "proton-cachyos-11.0-arm64"
        (tree / "files").mkdir(parents=True)
        (tree / "proton").write_text("#!/bin/sh\n")
        (tree / "proton").chmod(0o755)
        (tree / "toolmanifest.vdf").write_text('"manifest" {}\n')
        (tree / "compatibilitytool.vdf").write_text('"proton-cachyos-11.0-arm64"\n')
        (tree / "files" / "link").symlink_to("../proton")
        payload = self.dir / "proton-payload"
        subprocess.run(["bash", str(ROOT / "components/proton/package.sh"), str(tree), str(payload),
                        "armada-proton", "Armada Proton"], check=True)
        self.publish("add", "--channel", "testing", "--name", "proton", "--version", "1",
                     "--payload", str(payload))
        self.assertEqual(self.update(), 0)
        tool = components.ROOT / "proton/current/armada-proton"
        vdf = (tool / "compatibilitytool.vdf").read_text()
        self.assertIn('"armada-proton"', vdf)
        self.assertIn('"display_name" "Armada Proton"', vdf)
        self.assertNotIn("cachyos", vdf)
        self.assertEqual(os.readlink(tool / "files/link"), "../proton")


if __name__ == "__main__":
    unittest.main()
