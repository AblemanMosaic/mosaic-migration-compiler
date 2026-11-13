"""Offline closure witnesses: exact pins, tamper, metadata and clean install."""
from __future__ import annotations

import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools_t7 import dependencies as deps
BUNDLE = Path(os.environ.get("MMC_QUALIFICATION_DEPENDENCY_BUNDLE", ROOT / "baseline/offline"))
if not (BUNDLE / "LOCK.json").is_file():
    raise unittest.SkipTest("EXTERNAL_OFFLINE_DEPENDENCY_BUNDLE_NOT_SUPPLIED")
EXPECTED_LOCK = os.environ.get("MMC_QUALIFICATION_DEPENDENCY_LOCK_ROOT", deps.LOCK_ROOT)
PROFILE = json.loads((BUNDLE / "LOCK.json").read_bytes())["profile"]
PINS = deps.PROFILES[PROFILE][2]


def options(root=ROOT):
    return {"dependency_bundle": BUNDLE if root == ROOT else root / "baseline/offline",
            "dependency_lock_root": EXPECTED_LOCK}


def verify(root=ROOT):
    return deps.verify_wheelhouse(root, **options(root))


class DependencyClosureTests(unittest.TestCase):
    def test_wheel_safe_directory_entries_preserve_closed_file_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.whl"
            for content, mode, expected in ((b"", 0o40755, None),
                                            (b"unexpected", 0o40755, "MMC_DEPENDENCY_WHEEL_DIRECTORY_CONTENT"),
                                            (b"", 0o120755, "MMC_DEPENDENCY_WHEEL_KIND")):
                with self.subTest(content=content, mode=mode):
                    with zipfile.ZipFile(path, "w") as archive:
                        directory = zipfile.ZipInfo("package/"); directory.external_attr = mode << 16
                        archive.writestr(directory, content)
                        archive.writestr("package/__init__.py", b"# exact file")
                    if expected is None:
                        self.assertEqual(deps._members(path), {"package/__init__.py": b"# exact file"})
                    else:
                        with self.assertRaisesRegex(ValueError, expected):
                            deps._members(path)

    def test_regular_canonicalizes_dot_segments_for_install_provenance(self):
        with tempfile.TemporaryDirectory(prefix="mmc-offline-path-") as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            path = root / "value.whl"
            path.write_bytes(b"fixture")
            self.assertEqual(deps.regular(root / "nested/../value.whl"), path.resolve())

    def copied(self):
        temporary = tempfile.TemporaryDirectory(prefix="mmc-offline-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        shutil.copytree(BUNDLE, root / "baseline/offline")
        return root

    def test_real_pypi_wheels_have_exact_complete_dependency_and_license_closure(self):
        receipt = verify(ROOT)
        self.assertEqual(receipt["status"], "PASS_EXACT_OFFLINE_CLOSURE")
        self.assertEqual(len(receipt["wheels"]), len(PINS))
        self.assertEqual(receipt["lock_root"], EXPECTED_LOCK)
        self.assertEqual({row["name"] for row in receipt["wheels"]}, set(PINS))
        self.assertTrue(all(row["license_files"] for row in receipt["wheels"]))
        self.assertTrue(any(row["provider"] == "typing-extensions" for row in receipt["dependency_edges"]))

    def test_current_bundle_requires_retained_security_snapshot_without_network_refresh(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("Offline verification contacted network")):
            receipt = verify(ROOT)
        if PROFILE not in deps.CURRENT_FULL_PROFILES:
            self.assertEqual(receipt["dependency_security"]["status"], "HISTORICAL_PROFILE_NOT_CLEARED")
            return
        lock = json.loads((BUNDLE / "LOCK.json").read_bytes())
        self.assertEqual(receipt["dependency_security"]["security_root"], lock["dependency_security"]["receipt_root"])
        self.assertEqual(receipt["dependency_security"]["status"], "NO_MATCHES_AS_OF_SCAN")
        root = self.copied(); path = root / "baseline/offline/LOCK.json"
        del lock["dependency_security"]
        lock["lock_root"] = deps.sha(deps.canonical({key: value for key, value in lock.items() if key != "lock_root"}))
        path.write_bytes(deps.canonical(lock))
        with patch("urllib.request.urlopen", side_effect=AssertionError("Missing snapshot was refreshed")):
            with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_SECURITY_SNAPSHOT_SHAPE"):
                deps.verify_wheelhouse(root, dependency_bundle=root / "baseline/offline", dependency_lock_root=lock["lock_root"])

    def test_extra_wheel_is_not_silently_admitted(self):
        root = self.copied()
        (root / "baseline/offline/wheels/extra-1-py3-none-any.whl").write_bytes(b"unexpected")
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_FILE_CLOSURE"):
            verify(root)

    def test_changed_wheel_refuses_before_importing_its_parser(self):
        root = self.copied()
        wheel = next((root / "baseline/offline/wheels").glob("pip-*.whl"))
        wheel.write_bytes(wheel.read_bytes() + b"tampered")
        with patch.object(deps, "_packaging_check") as parser:
            with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_WHEEL_HASH"):
                verify(root)
            parser.assert_not_called()

    def test_self_rehashed_lock_cannot_replace_embedded_reviewed_pin(self):
        root = self.copied()
        path = root / "baseline/offline/LOCK.json"
        lock = json.loads(path.read_bytes())
        lock["wheels"][0]["requires_python"] = ">=99"
        lock["lock_root"] = deps.sha(deps.canonical({key: value for key, value in lock.items() if key != "lock_root"}))
        path.write_bytes(deps.canonical(lock))
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_LOCK"):
            verify(root)

    def test_requirements_without_exact_hashes_are_refused(self):
        root = self.copied()
        (root / "baseline/offline/requirements.lock").write_bytes(b"cryptography==46.0.3\n")
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_REQUIREMENTS_HASHES"):
            verify(root)

    def test_missing_transitive_dependency_is_not_a_closed_profile(self):
        receipt = verify(ROOT)
        rows = [row for row in receipt["wheels"] if row["name"] != "pycparser"]
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_METADATA_CLOSURE"):
            deps._packaging_check(BUNDLE / "wheels", rows, roots=deps.PROFILES[PROFILE][3])

    def test_wheel_tags_and_requires_python_are_enforced(self):
        receipt = verify(ROOT)
        incompatible = "manylinux_2_34_x86_64" if sys.platform == "win32" else "win_amd64"
        crypto_version = next(row["version"] for row in receipt["wheels"] if row["name"] == "cryptography")
        for field, value in (("filename", "cryptography-" + crypto_version + "-cp311-abi3-" + incompatible + ".whl"),
                             ("requires_python", ">=99")):
            rows = [dict(row) for row in receipt["wheels"]]
            next(row for row in rows if row["name"] == "cryptography")[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_METADATA_CLOSURE"):
                deps._packaging_check(BUNDLE / "wheels", rows, roots=deps.PROFILES[PROFILE][3])

    def test_profile_does_not_claim_other_platforms(self):
        different = "Linux" if deps.PROFILES[PROFILE][0] == "Windows" else "Windows"
        with patch.object(deps.platform, "system", return_value=different):
            with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_PROFILE_UNSUPPORTED"):
                verify(ROOT)

    def test_observer_does_not_execute_unverified_startup_files(self):
        """The refusal itself must not import a .pth or sitecustomize fixture."""
        with tempfile.TemporaryDirectory(prefix="mmc-startup-observer-") as directory:
            root = Path(directory)
            environment = root / "venv"
            created = subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(environment)],
                                     capture_output=True, timeout=90)
            self.assertEqual(created.returncode, 0, created.stderr.decode("utf-8", "replace"))
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            purelib = environment / ("Lib/site-packages" if os.name == "nt" else
                                     f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
            marker = root / "startup-marker.txt"
            fixture = "import pathlib; pathlib.Path(" + repr(str(marker)) + ").write_text('fixture loaded')\n"
            for name in ("unverified.pth", "sitecustomize.py"):
                with self.subTest(name=name):
                    startup = purelib / name
                    startup.write_text(fixture, encoding="utf-8")
                    try:
                        run = subprocess.run(deps.observation_command(python, ROOT, **options()), capture_output=True, timeout=90)
                        self.assertNotEqual(run.returncode, 0)
                        self.assertIn(b"MMC_DEPENDENCY_INSTALLED_DISTRIBUTIONS", run.stderr)
                        self.assertFalse(marker.exists(), "Startup code ran before the integrity refusal")
                    finally:
                        startup.unlink()
                        marker.unlink(missing_ok=True)

    def test_installer_refuses_nonempty_target_without_executing_startup_files(self):
        with tempfile.TemporaryDirectory(prefix="mmc-startup-installer-") as directory:
            root = Path(directory)
            environment = root / "venv"
            created = subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(environment)],
                                     capture_output=True, timeout=90)
            self.assertEqual(created.returncode, 0, created.stderr.decode("utf-8", "replace"))
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            purelib = environment / ("Lib/site-packages" if os.name == "nt" else
                                     f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages")
            marker = root / "startup-marker.txt"
            (purelib / "unverified.pth").write_text(
                "import pathlib; pathlib.Path(" + repr(str(marker)) + ").write_text('fixture loaded')\n", encoding="utf-8")
            run = subprocess.run(deps.installation_command(python, ROOT, **options()), capture_output=True, timeout=90)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(b"MMC_DEPENDENCY_INSTALL_TARGET_NOT_EMPTY", run.stderr)
            self.assertFalse(marker.exists(), "Startup code ran before the fresh-target refusal")

    def test_clean_offline_install_then_installed_tamper_refuses(self):
        with tempfile.TemporaryDirectory(prefix="mmc-offline-install-") as directory:
            environment = Path(directory) / "venv"
            run = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(environment)],
                                 capture_output=True, timeout=90)
            self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace"))
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            command = deps.installation_command(python, ROOT, **options())
            self.assertIn("--require-hashes", command)
            self.assertIn("--no-index", command)
            self.assertIn("--isolated", command)
            env = {**os.environ, "PIP_INDEX_URL": "http://invalid.invalid/", "PIP_EXTRA_INDEX_URL": "http://invalid.invalid/"}
            installed = subprocess.run(command, capture_output=True, timeout=180, env=env)
            self.assertEqual(installed.returncode, 0, installed.stderr.decode("utf-8", "replace"))
            observed = subprocess.run(deps.observation_command(python, ROOT, **options()), capture_output=True, timeout=90)
            self.assertEqual(observed.returncode, 0, observed.stderr.decode("utf-8", "replace"))
            receipt = json.loads(observed.stdout)
            self.assertFalse(receipt["system_site_packages"])
            expected_files = sum(sum(not name.endswith(".dist-info/RECORD") for name in deps._members(BUNDLE / "wheels" / row["filename"]))
                                 for row in verify()["wheels"])
            self.assertEqual(receipt["immutable_files_verified"], expected_files)
            self.assertEqual(receipt["distributions"], PINS)
            purelib = Path(receipt["purelib"])
            for name in ("unexpected.py", "unexpected.pth"):
                extra = purelib / name
                extra.write_bytes(b"# undeclared file\n")
                refused = subprocess.run(deps.observation_command(python, ROOT, **options()), capture_output=True, timeout=90)
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn(b"MMC_DEPENDENCY_UNDECLARED_INSTALLED_FILES", refused.stderr)
                extra.unlink()
            duplicate = purelib / "duplicate_attrs-25.4.0.dist-info"
            duplicate.mkdir()
            metadata = duplicate / "METADATA"
            metadata.write_bytes((purelib / "attrs-25.4.0.dist-info/METADATA").read_bytes())
            refused = subprocess.run(deps.observation_command(python, ROOT, **options()), capture_output=True, timeout=90)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn(b"MMC_DEPENDENCY_DUPLICATE_INSTALLED_DISTRIBUTION", refused.stderr)
            metadata.unlink(); duplicate.rmdir()
            copied_root = self.copied()
            altered = deps.installation_command(python, copied_root, **options(copied_root))
            altered.insert(1, "-O")
            pip = next((copied_root / "baseline/offline/wheels").glob("pip-*.whl"))
            pip.write_bytes(pip.read_bytes() + b"changed after command construction")
            refused = subprocess.run(altered, capture_output=True, timeout=90)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn(b"MMC_DEPENDENCY_BOOTSTRAP_HASH", refused.stderr)
            source = Path(receipt["purelib"]) / "attrs/__init__.py"
            source.write_bytes(source.read_bytes() + b"\n# injected change\n")
            refused = subprocess.run(deps.observation_command(python, ROOT, **options()), capture_output=True, timeout=90)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn(b"MMC_DEPENDENCY_INSTALLED_FILE_HASH", refused.stderr)


if __name__ == "__main__":
    unittest.main()
