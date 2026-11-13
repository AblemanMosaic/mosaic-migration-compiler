"""Release boundary witnesses: substitution, tamper, and custody reuse."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import os
import json
import subprocess
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import MMCError, canonical
from tools_t7 import release_verify as release
from tools_t7.package import build_wheel


class ReleaseWorkflowTests(unittest.TestCase):
    def test_cleanup_timeout_cannot_bypass_terminal_custody(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            child = Mock(returncode=0)
            child.poll.return_value = 0
            child.communicate.side_effect = subprocess.TimeoutExpired("owned", 1, output=b"partial output", stderr=b"partial error")
            with patch.object(release.subprocess, "Popen", return_value=child), patch.object(release.time, "monotonic", side_effect=[0, 0, 2]):
                with self.assertRaisesRegex(MMCError, "MMC_RELEASE_COMMAND_FAILED"):
                    release._capture(output, "held-pipe", [sys.executable, "-c", "pass"], dict(os.environ), timeout=1)
            terminal = json.loads((output / "held-pipe.terminal.json").read_bytes())
            self.assertEqual(terminal["status"], "TIMEOUT")
            self.assertFalse(terminal["capture_complete"])
            self.assertIn("PIPE_DRAIN_TIMEOUT", terminal["cleanup_errors"])
            self.assertEqual((output / "held-pipe.stdout").read_bytes(), b"partial output")
            self.assertEqual((output / "held-pipe.stderr").read_bytes(), b"partial error")

    def test_self_rehashed_target_success_label_does_not_replace_workflow_evidence(self):
        fabricated = release.rooted({"status": "PASS_AUTHENTICATED_SQLITE_TARGET_MIGRATION"})
        with self.assertRaisesRegex(MMCError, "MMC_RELEASE_TARGET_SEMANTICS"):
            release.verify_target_receipt(fabricated)

    def test_command_timeout_preserves_output_and_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(MMCError, "MMC_RELEASE_COMMAND_FAILED"):
                release._capture(output, "deadline", [sys.executable, "-c",
                    "import time; print('partial output',flush=True); time.sleep(10)"], dict(os.environ), timeout=1)
            terminal = json.loads((output / "deadline.terminal.json").read_bytes())
            self.assertEqual(terminal["status"], "TIMEOUT")
            self.assertIn(b"partial output", (output / "deadline.stdout").read_bytes())
            self.assertEqual(terminal["stdout_bytes"], len((output / "deadline.stdout").read_bytes()))
            self.assertEqual(terminal["stderr_bytes"], len((output / "deadline.stderr").read_bytes()))
            self.assertIsNotNone(terminal["exit_code"])

    def test_new_failure_is_not_auto_exempted_by_os_error_text(self):
        from tools_t7.qualify import _host_limitation
        self.assertFalse(_host_limitation("tests_t7.test_adapter_safety.NewCase.test_link",
                                          "WinError 1314", "ERROR"))
        self.assertFalse(_host_limitation("tests_t7.NewCase.test_fifo",
                                          "module 'os' has no attribute 'mkfifo'", "ERROR"))

    def test_wheel_substitution_cannot_be_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
            (root / "NOTICE").write_bytes((ROOT / "NOTICE").read_bytes())
            module = root / "src/example.py"
            module.write_text("ORIGINAL = True\n", encoding="utf-8")
            wheel = build_wheel(root)
            self.assertEqual(release.verify_wheel(wheel, root)["status"], "PASS_EXACT_SOURCE_WHEEL")
            module.write_text("ORIGINAL = False\n", encoding="utf-8")
            with self.assertRaisesRegex(MMCError, "MMC_RELEASE_WHEEL_SOURCE_MISMATCH"):
                release.verify_wheel(wheel, root)

    def test_existing_attempt_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            witness = output / "prior.txt"
            witness.write_bytes(b"prior terminal custody")
            with self.assertRaisesRegex(MMCError, "MMC_RELEASE_CUSTODY_EXISTS"):
                release.release_verify(output, "unused", output, output, output, output)
            self.assertEqual(witness.read_bytes(), b"prior terminal custody")

    def test_source_mismatch_refuses_before_creating_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fresh"
            with self.assertRaisesRegex(MMCError, "MMC_RELEASE_SOURCE_PIN"):
                release.release_verify(output, "0" * 64, output, output, output, output)
            self.assertFalse(output.exists())

    def test_rehashed_qualification_cannot_hide_modified_raw_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provenance = root / "provenance/turn7"; provenance.mkdir(parents=True)
            identifier = "tests_t7.fixture.Case.test_obligation"
            (provenance / "TEST-REGISTRY.json").write_bytes(canonical({"groups": {"t7": [identifier]}}))
            log = b"original evidence"
            group = {"unexpected": [], "host_limitations": [], "successor_superseded_assertions": [],
                     "test_outcomes": {identifier: "PASS"},
                     "test_details": {},
                     "counts": {status: int(status == "PASS") for status in
                                ("PASS", "FAIL", "ERROR", "SKIP", "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS")},
                     "log": {"path": "t7-tests.txt", "bytes": len(log), "sha256": hashlib.sha256(log).hexdigest()}}
            (root / "t7-tests.json").write_bytes(canonical({**group, "test_ids": [identifier]}))
            (root / "t7-tests.txt").write_bytes(b"changed evidence")
            receipt = release.rooted({"status": "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS",
                                      "source_root": "pinned", "environment": {"platform": "Windows"}, "tests": {"t7": group}})
            path = root / "T7-QUALIFICATION.json"; path.write_bytes(canonical(receipt))
            with patch.object(release, "ROOT", root):
                with self.assertRaisesRegex(MMCError, "MMC_RELEASE_LOG_HASH"):
                    release.verify_qualification(path, "pinned")

    def test_rehashed_qualification_cannot_launder_failure_as_host_limitation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provenance = root / "provenance/turn7"; provenance.mkdir(parents=True)
            identifier = "tests_t7.fixture.Case.test_obligation"
            (provenance / "TEST-REGISTRY.json").write_bytes(canonical({"groups": {"t7": [identifier]}}))
            group = {"unexpected": [], "host_limitations": [identifier], "successor_superseded_assertions": [],
                     "test_outcomes": {identifier: "FAIL"}, "test_details": {identifier: "AssertionError: broken invariant"},
                     "counts": {status: int(status == "FAIL") for status in
                                ("PASS", "FAIL", "ERROR", "SKIP", "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS")}}
            (root / "t7-tests.json").write_bytes(canonical({**group, "test_ids": [identifier]}))
            receipt = release.rooted({"status": "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS",
                                      "source_root": "pinned", "environment": {"platform": "Windows"}, "tests": {"t7": group}})
            path = root / "T7-QUALIFICATION.json"; path.write_bytes(canonical(receipt))
            with patch.object(release, "ROOT", root):
                with self.assertRaisesRegex(MMCError, "MMC_RELEASE_TEST_ACCOUNTING"):
                    release.verify_qualification(path, "pinned")

    def test_retained_execution_uses_retained_test_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auditor = root / "auditor"
            subject = root / "retained-subject"
            evidence = root / "evidence"
            evidence.mkdir()
            for source in (auditor, subject):
                (source / "provenance/turn7").mkdir(parents=True)
            retained_id = "tests_t7.fixture.Case.test_retained"
            current_id = "tests_t7.fixture.Case.test_new_validator"
            (subject / "provenance/turn7/TEST-REGISTRY.json").write_bytes(
                canonical({"groups": {"t7": [retained_id]}}))
            (auditor / "provenance/turn7/TEST-REGISTRY.json").write_bytes(
                canonical({"groups": {"t7": [retained_id, current_id]}}))
            log = b"retained evidence"
            group = {
                "unexpected": [], "host_limitations": [],
                "successor_superseded_assertions": [],
                "test_outcomes": {retained_id: "PASS"}, "test_details": {},
                "counts": {status: int(status == "PASS") for status in
                           ("PASS", "FAIL", "ERROR", "SKIP", "EXPECTED_FAILURE",
                            "UNEXPECTED_SUCCESS")},
                "log": {"path": "t7-tests.txt", "bytes": len(log),
                        "sha256": hashlib.sha256(log).hexdigest()},
            }
            (evidence / "t7-tests.json").write_bytes(
                canonical({**group, "test_ids": [retained_id]}))
            (evidence / "t7-tests.txt").write_bytes(log)
            receipt = release.rooted({
                "status": "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS",
                "source_root": "pinned", "environment": {"platform": "Windows"},
                "tests": {"t7": group},
            })
            path = evidence / "T7-QUALIFICATION.json"
            path.write_bytes(canonical(receipt))
            with patch.object(release, "ROOT", auditor):
                # Reaching the next required section proves that the retained
                # denominator, not the auditor's newer registry, was used.
                with self.assertRaisesRegex(MMCError, "MMC_RELEASE_EVIDENCE_SCOPE"):
                    release.verify_qualification(path, "pinned", subject_root=subject)


if __name__ == "__main__":
    unittest.main()
