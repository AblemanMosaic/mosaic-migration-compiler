"""Exact handoff negative witnesses do not invent native execution evidence."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from tools_t7 import dependencies as deps
from tools_t7 import platform_qualification as handoff


class PlatformHandoffTests(unittest.TestCase):
    def test_windows_fifo_inapplicability_requires_exact_platform_status_and_cause(self):
        t1 = "tests.test_boundaries.IOBoundaryTests.test_fifo_refused_before_block"
        t4 = "tests_t4.test_collectors.CollectorTests.test_fifo_refused"
        qualified = {"environment": {"platform": "Windows"}, "host_limitations": [t1, t4], "tests": {
            "t1": {"test_outcomes": {t1: "SKIP"}, "test_details": {t1: "POSIX FIFO facility not available; not a Windows pass"}},
            "t4": {"test_outcomes": {t4: "ERROR"}, "test_details": {t4: "Traceback (most recent call last):\nAttributeError: module 'os' has no attribute 'mkfifo'\n"}}}}
        original = handoff.canonical(qualified)
        result = handoff.platform_applicability(qualified)
        self.assertEqual(result["platform_inapplicable_tests"], [t1, t4])
        self.assertEqual(result["actionable_host_limitations"], [])
        self.assertEqual(handoff.canonical(qualified), original)
        for group, field, value in (("t1", "test_details", "POSIX FIFO facility not available"),
                                     ("t4", "test_details", "PermissionError: fixture failure"),
                                     ("t4", "test_outcomes", "FAIL")):
            modified = json.loads(original); identifier = t1 if group == "t1" else t4
            modified["tests"][group][field][identifier] = value
            with self.subTest(group=group, field=field):
                self.assertNotIn(identifier, handoff.platform_applicability(modified)["platform_inapplicable_tests"])
                self.assertIn(identifier, handoff.platform_applicability(modified)["actionable_host_limitations"])
        for system in ("Linux", "Darwin"):
            modified = json.loads(original); modified["environment"]["platform"] = system
            with self.subTest(system=system):
                self.assertEqual(handoff.platform_applicability(modified)["platform_inapplicable_tests"], [])
                self.assertEqual(handoff.platform_applicability(modified)["actionable_host_limitations"], [t1, t4])

    def test_acquisition_and_git_timeouts_preserve_partial_capture(self):
        for capture, name in ((deps._capture_acquisition, "acquisition"), (handoff._capture_git, "ucm-clone")):
            with self.subTest(capture=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                failure = subprocess.TimeoutExpired(["fixture"], 1, output=b"partial output", stderr=b"partial error")
                with patch.object(subprocess, "run", side_effect=failure), self.assertRaises(subprocess.TimeoutExpired):
                    if name == "acquisition":
                        capture(["fixture"], directory, timeout=1)
                    else:
                        capture(["fixture"], directory, name, timeout=1)
                self.assertEqual((directory / (name + ".stdout")).read_bytes(), b"partial output")
                self.assertEqual((directory / (name + ".stderr")).read_bytes(), b"partial error")
                terminal = json.loads((directory / (name + ".terminal.json")).read_bytes())
                self.assertEqual(terminal["status"], "TIMEOUT")
                self.assertIsNone(terminal["exit_code"])
                self.assertTrue((directory / (name + ".started.json")).exists())

    def test_command_captures_require_hash_length_and_installed_agent_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); name = "installed-agent"
            for suffix in ("stdout", "stderr", "stdin"):
                (directory / (name + "." + suffix)).write_bytes(suffix.encode())
            body = {"name": name, "status": "COMPLETED", "exit_code": 0, "capture_complete": True, "cleanup_errors": []}
            for suffix in ("stdout", "stderr", "stdin"):
                raw = suffix.encode(); body[suffix + "_sha256"] = handoff.sha(raw); body[suffix + "_bytes"] = len(raw)
            path = directory / (name + ".terminal.json")
            path.write_bytes(handoff.canonical(handoff.rooted(body)))
            handoff.verify_command_capture(directory, path)
            for field, value, error in (("stdout_sha256", None, "MMC_PLATFORM_AUDIT_CAPTURE_HASH_REQUIRED"),
                                         ("stderr_sha256", "bad", "MMC_PLATFORM_AUDIT_CAPTURE_HASH_REQUIRED"),
                                         ("stdin_sha256", None, "MMC_PLATFORM_AUDIT_CAPTURE_HASH_REQUIRED"),
                                         ("stdout_bytes", None, "MMC_PLATFORM_AUDIT_COMMAND_CAPTURE")):
                with self.subTest(field=field):
                    path.write_bytes(handoff.canonical(handoff.rooted({**body, field: value})))
                    with self.assertRaisesRegex(ValueError, error):
                        handoff.verify_command_capture(directory, path)

    def test_post_run_audit_rebuilds_index_from_retained_execution_source(self):
        expected_source = "a" * 64
        auditor_source = "9" * 64
        with tempfile.TemporaryDirectory() as temporary:
            location = Path(temporary) / "execution"
            source = location / "source"
            release = location / "release"
            qualification_dir = release / "qualification"
            source.mkdir(parents=True)
            qualification_dir.mkdir(parents=True)
            (release / "MMC-SOURCE.zip").write_bytes(b"source")
            (release / "mosaic_migration_compiler-0.1.0a9-py3-none-any.whl").write_bytes(b"wheel")
            target = handoff.rooted({"status": "PASS"})
            (release / "installed-target-migration.stdout").write_bytes(handoff.canonical(target))

            qualification = {
                "receipt_root": "b" * 64,
                "environment": {"platform": "Windows"},
                "host_limitations": [],
                "tests": {},
            }
            execution = handoff.rooted({
                "schema": "mmc.platform-execution.v1",
                "status": "PASS_EXECUTED_SCOPED_PLATFORM",
                "source_root": expected_source,
                "qualification": "FULL_SOURCE_AND_INSTALLED_ARTIFACT_EXECUTED",
                "exit_code": 0,
                "release_root": "c" * 64,
                "dependency_profile": "fixture",
                "dependency_lock_root": "d" * 64,
                "host_limitations": [],
                "host": {"system": "Windows"},
            })
            release_record = handoff.rooted({
                "status": "PASS_SCOPED_ALPHA_CANDIDATE",
                "source_root": expected_source,
                "platform": "Windows",
                "qualification_root": qualification["receipt_root"],
                "source_archive": {"sha256": "e" * 64},
                "wheel": {"sha256": "f" * 64},
                "installed": {"target_migration_receipt_root": target["receipt_root"]},
                "offline_dependencies": {"lock_root": "d" * 64, "profile": "fixture"},
            })
            execution["release_root"] = release_record["receipt_root"]
            execution = handoff.rooted({key: value for key, value in execution.items()
                                        if key != "receipt_root"})
            (location / "PLATFORM-EXECUTION.json").write_bytes(handoff.canonical(execution))
            (release / "RELEASE-VERIFICATION.json").write_bytes(handoff.canonical(release_record))

            with patch("tools.common.source_snapshot", return_value={"root": auditor_source}), \
                    patch("tools_t7.release_verify.verify_qualification",
                          return_value=qualification) as verify_qualification, \
                    patch("tools_t7.release_verify.verify_source_archive",
                          return_value=release_record["source_archive"]), \
                    patch("tools_t7.release_verify.verify_wheel",
                          return_value={**release_record["wheel"], "files": []}), \
                    patch("tools_t7.release_verify.verify_target_receipt"), \
                    patch.object(handoff, "verify_command_set"):
                audit = handoff.audit_executions([location], expected_source)

            self.assertEqual(audit["executions"][0]["execution_root"], execution["receipt_root"])
            self.assertEqual(audit["source_root"], expected_source)
            self.assertEqual(audit["auditor_source_root"], auditor_source)
            self.assertEqual(verify_qualification.call_args.kwargs["subject_root"], source)

    def test_release_command_set_refuses_missing_unknown_and_duplicate(self):
        names = sorted(handoff.RELEASE_COMMANDS)
        handoff.verify_command_set(names)
        for invalid in (names[:-1], [*names, "unadmitted"], [*names, names[0]]):
            with self.subTest(names=invalid), self.assertRaisesRegex(ValueError, "MMC_PLATFORM_AUDIT_COMMAND_SET"):
                handoff.verify_command_set(invalid)

    def test_macos_cross_acquisition_cannot_select_windows_profile(self):
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_CROSS_TARGET_UNSUPPORTED"):
            deps._cross_target(deps.PROFILE)
        for profile in ("macos-cpython312-arm64-full-qualification.v2",):
            target = deps._cross_target(profile)
            self.assertEqual(target["environment"]["sys_platform"], "darwin")
            self.assertTrue(all(tag.startswith("macosx_") for tag in target["platforms"]))
        with self.assertRaisesRegex(ValueError, "BLOCKED_UPSTREAM_PATCHED_WHEEL_UNAVAILABLE"):
            deps._cross_target("macos-cpython312-x86_64-full-qualification.v2")

    def test_patched_bootstrap_refuses_changed_metadata_or_bytes_before_import(self):
        pip = deps.BOOTSTRAP_PIP
        good = {"filename": pip["filename"], "digests": {"sha256": pip["sha256"]}, "url": pip["url"],
                "size": pip["bytes"], "packagetype": "bdist_wheel", "yanked": False}
        for metadata, error in (({**good, "digests": {"sha256": "0" * 64}}, "MMC_DEPENDENCY_PIP_ACQUISITION_PIN"),
                                 (good, "MMC_DEPENDENCY_PIP_ACQUISITION_HASH")):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "fresh"
                with patch("urllib.request.urlopen") as request, patch.object(deps, "wheel_facts") as inspect, \
                        patch.object(deps, "_capture_acquisition") as download:
                    request.return_value.__enter__.return_value.read.side_effect = [deps.canonical({"urls": [metadata]}), b"changed"]
                    with self.assertRaisesRegex(ValueError, error):
                        deps.acquire_bundle(output, "macos-cpython312-arm64-full-qualification.v2", cross_target=True)
                    inspect.assert_not_called()
                    download.assert_not_called()
                terminal = json.loads((output / "ACQUISITION.json").read_bytes())
                self.assertEqual(terminal["status"], "FAILED")

    def fixture(self, directory):
        names = ["RUNNER.py", "MMC-SOURCE.zip", "mosaic.whl", "ucm.bundle", "PIPPI-SOURCE.zip",
                 "semcrys.bundle", "SUBJECT.zip",
                 "dependencies/LOCK.json", "dependencies/requirements.lock", "dependencies/wheels/fixture.whl"]
        for name in names:
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("fixture:" + name).encode())
        for identity in handoff.NATIVE_INPUTS.values():
            path = directory / "native-inputs" / identity["filename"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")
            original = identity["sha256"]
            self.addCleanup(identity.__setitem__, "sha256", original)
            identity["sha256"] = handoff.sha(b"fixture")
        body = {"schema": "mmc.platform-handoff.v1", "source_root": "a" * 64, "wheel": "mosaic.whl",
                "runner_sha256": handoff.sha((directory / "RUNNER.py").read_bytes()),
                "pippi": {"archive_sha256": handoff.sha((directory / "PIPPI-SOURCE.zip").read_bytes()),
                          "source_manifest_root": "b" * 64},
                "files": handoff.inventory(directory), "qualification": "NOT_EXECUTED", "authority_effect": "NONE"}
        manifest = handoff.rooted(body)
        (directory / "HANDOFF.json").write_bytes(handoff.canonical(manifest))
        return manifest

    def test_exact_envelope_includes_runner_and_dependency_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = self.fixture(directory)
            self.assertEqual(handoff.verify_handoff(directory, manifest["receipt_root"]), manifest)
            self.assertEqual(manifest["qualification"], "NOT_EXECUTED")

    def test_changed_runner_and_extra_file_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = self.fixture(directory)
            path = directory / "RUNNER.py"; original = path.read_bytes()
            path.write_bytes(original + b"# changed")
            with self.assertRaisesRegex(ValueError, "MMC_PLATFORM_HANDOFF_CLOSURE"):
                handoff.verify_handoff(directory, manifest["receipt_root"])
            path.write_bytes(original)
            (directory / "unadmitted.py").write_bytes(b"# must not import")
            with self.assertRaisesRegex(ValueError, "MMC_PLATFORM_HANDOFF_CLOSURE"):
                handoff.verify_handoff(directory, manifest["receipt_root"])

    def test_self_rehashed_manifest_cannot_change_separate_expected_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = self.fixture(directory)
            expected = manifest["receipt_root"]
            body = {key: value for key, value in manifest.items() if key != "receipt_root"}
            body["source_root"] = "b" * 64
            (directory / "HANDOFF.json").write_bytes(handoff.canonical(handoff.rooted(body)))
            with self.assertRaisesRegex(ValueError, "MMC_PLATFORM_HANDOFF_ROOT"):
                handoff.verify_handoff(directory, expected)

    def test_failed_envelope_preserves_terminal_before_source_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); directory = root / "handoff"; directory.mkdir()
            self.fixture(directory)
            output = root / "failed-attempt"
            with self.assertRaisesRegex(ValueError, "MMC_PLATFORM_HANDOFF_ROOT"):
                handoff.run(directory, "0" * 64, output)
            terminal = json.loads((output / "PLATFORM-EXECUTION.json").read_bytes())
            self.assertEqual(terminal["status"], "FAILED")
            self.assertFalse((output / "source").exists())
            self.assertEqual(terminal["authority_effect"], "NONE")
            with self.assertRaisesRegex(ValueError, "MMC_PLATFORM_RUN_CUSTODY_EXISTS"):
                handoff.run(directory, "0" * 64, output)

    def test_external_dependency_bundle_requires_independent_root(self):
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_BUNDLE_PIN_REQUIRED"):
            deps._bundle(Path.cwd(), Path.cwd(), None)
        with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_BUNDLE_PIN_REQUIRED"):
            deps._bundle(Path.cwd(), None, "a" * 64)

    def test_named_profile_does_not_override_native_host(self):
        with patch.object(deps.platform, "system", return_value="Windows"):
            with self.assertRaisesRegex(ValueError, "MMC_DEPENDENCY_PROFILE_UNSUPPORTED"):
                deps._profile("macos-cpython312-arm64-full-qualification.v2")
        self.assertEqual(deps.PROFILES[deps.PROFILE][2], deps.PINS)
        self.assertEqual(deps.FULL_PINS["pillow"], "13.0.0")
        self.assertEqual(deps.FULL_PINS["cryptography"], "50.0.2")
        self.assertEqual(deps.FULL_PINS["pip"], "26.3")


if __name__ == "__main__":
    unittest.main()
