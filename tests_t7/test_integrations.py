from __future__ import annotations

import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]


def cmba_a7_wheel() -> Path:
    supplied = os.environ.get("MMC_QUALIFICATION_CMBA_A7_WHEEL")
    if not supplied:
        raise unittest.SkipTest("EXTERNAL_CMBA_A7_QUALIFICATION_WHEEL_NOT_SUPPLIED")
    return Path(supplied)

from mosaic_mmc import MMCError
from mosaic_mmc_product import integrations


@contextmanager
def git_source_fixture():
    with tempfile.TemporaryDirectory(prefix="mmc-git-bytes-", dir=ROOT.parent) as temporary:
        root = Path(temporary)
        (root / "src").mkdir()
        (root / ".gitattributes").write_text("* -text\n", encoding="utf-8")
        (root / "src/example.py").write_text("VALUE = 'original'\n", encoding="utf-8")
        (root / ".gitignore").write_text("src/shadow.py\nsrc/shadow.json\nsrc/__pycache__/\n", encoding="utf-8")
        command = ["git", "-C", str(root)]
        subprocess.run(command + ["init", "--quiet"], check=True, capture_output=True)
        subprocess.run(command + ["add", "."], check=True, capture_output=True)
        subprocess.run(command + ["-c", "user.name=MMC Test", "-c", "user.email=mmc-test@example.invalid",
                                   "commit", "--quiet", "-m", "exact-byte fixture"], check=True, capture_output=True)
        commit = subprocess.run(command + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        tree = subprocess.run(command + ["rev-parse", "HEAD^{tree}"], check=True, capture_output=True, text=True).stdout.strip()
        with patch.object(integrations, "_pins", return_value={"integrations": {"ucm": {"git_commit": commit, "git_tree": tree}}}):
            yield root, command


class IntegrationBoundaryTests(unittest.TestCase):
    def test_exact_cmba_wheel_ignores_adjacent_shadow_packages(self):
        with tempfile.TemporaryDirectory(prefix="mmc-cmba-shadow-", dir=ROOT.parent) as temporary:
            directory = Path(temporary)
            wheel = directory / "cmba_core-0.1.0a7-py3-none-any.whl"
            shutil.copyfile(cmba_a7_wheel(), wheel)
            for package in ("cmba_core", "cmba_agent"):
                shadow = directory / package
                shadow.mkdir()
                (shadow / "__init__.py").write_text(
                    "raise RuntimeError('adjacent shadow package executed')\n", encoding="utf-8")
            result = integrations.probe_cmba_agent(wheel)
            self.assertEqual(result["status"], "PASS_EXACT_WHEEL_EXECUTED_BINDING")
            self.assertEqual(result["dimensions"], ["effect-executor", "semantic-authority", "subject-root"])

    def test_cmba_requires_all_expected_dimensions(self):
        manifest = {"distribution_version": "0.1.0a7", "authority_effect": "NONE"}
        executed = {"binding": {"binding_root": "0" * 64}, "inspection": {
            "status": "BINDING_STRUCTURE_VALID", "external_anchor": "MATCHED_CALLER_EXPECTATION",
            "dimensions": [],
        }}
        with patch.object(integrations, "_run_json", side_effect=[manifest, executed]):
            with self.assertRaises(MMCError) as caught:
                integrations.probe_cmba_agent(cmba_a7_wheel())
        self.assertEqual(caught.exception.code, "MMC_T7_CMBA_BINDING_DIMENSIONS")

    def test_dependency_timeout_has_typed_refusal(self):
        with patch.object(integrations.subprocess, "run", side_effect=subprocess.TimeoutExpired("dependency", 90)):
            with self.assertRaises(MMCError) as caught:
                integrations._run_json(["dependency"], cwd=ROOT)
        self.assertEqual(caught.exception.code, "MMC_T7_INTEGRATION_TIMEOUT")

    def test_missing_dependency_executable_has_typed_refusal(self):
        with patch.object(integrations.subprocess, "run", side_effect=FileNotFoundError()):
            with self.assertRaises(MMCError) as caught:
                integrations.verify_git_source("ucm", ROOT)
        self.assertEqual(caught.exception.code, "MMC_T7_INTEGRATION_UNAVAILABLE")

    def test_nonobject_dependency_response_is_refused(self):
        completed = subprocess.CompletedProcess(["dependency"], 0, b"[]", b"")
        with patch.object(integrations.subprocess, "run", return_value=completed):
            with self.assertRaises(MMCError) as caught:
                integrations._run_json(["dependency"], cwd=ROOT)
        self.assertEqual(caught.exception.code, "MMC_T7_INTEGRATION_RESPONSE")

    def test_source_parent_link_is_refused_before_git(self):
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == ROOT.parent or original(path)):
            with patch.object(integrations.subprocess, "run") as run:
                with self.assertRaises(MMCError) as caught:
                    integrations.verify_git_source("ucm", ROOT)
        self.assertEqual(caught.exception.code, "MMC_T7_SOURCE_PATH")
        run.assert_not_called()

    def test_unrelated_amcas_contract_is_not_mmc_conformance(self):
        with tempfile.TemporaryDirectory(prefix="mmc-foreign-contract-", dir=ROOT.parent) as temporary:
            contract = Path(temporary) / "contract.json"
            contract.write_text(json.dumps({"contract_root": "0" * 64}), encoding="utf-8")
            with patch.object(integrations, "verify_git_source", return_value={"source": ROOT}):
                with self.assertRaises(MMCError) as caught:
                    integrations.probe_ucm(ROOT, contract)
        self.assertEqual(caught.exception.code, "MMC_T7_AMCAS_CONTRACT_IDENTITY")

    def test_exact_source_fixture_passes_without_index_shortcuts(self):
        with git_source_fixture() as (root, _):
            self.assertEqual(integrations.verify_git_source("ucm", root)["source"], root)

    def test_modified_source_hidden_by_index_flags_is_refused(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), git_source_fixture() as (root, command):
                subprocess.run(command + ["update-index", flag, "src/example.py"], check=True, capture_output=True)
                (root / "src/example.py").write_text("VALUE = 'tampered'\n", encoding="utf-8")
                status = subprocess.run(command + ["status", "--porcelain", "--untracked-files=all"],
                                        check=True, capture_output=True, text=True)
                self.assertEqual(status.stdout, "")
                with self.assertRaises(MMCError) as caught:
                    integrations.verify_git_source("ucm", root)
                self.assertEqual(caught.exception.code, "MMC_T7_SOURCE_BYTES")

    def test_ignored_source_or_json_cannot_participate_in_clean_probe(self):
        for filename in ("shadow.py", "shadow.json"):
            with self.subTest(filename=filename), git_source_fixture() as (root, command):
                (root / "src" / filename).write_text("{}\n", encoding="utf-8")
                status = subprocess.run(command + ["status", "--porcelain", "--untracked-files=all"],
                                        check=True, capture_output=True, text=True)
                self.assertEqual(status.stdout, "")
                with self.assertRaises(MMCError) as caught:
                    integrations.verify_git_source("ucm", root)
                self.assertEqual(caught.exception.code, "MMC_T7_SOURCE_EXTRA_IMPORT")

    def test_fresh_cache_prefix_ignores_valid_malicious_cached_bytecode(self):
        with tempfile.TemporaryDirectory(prefix="mmc-pyc-proof-", dir=ROOT.parent) as temporary:
            root = Path(temporary)
            source = root / "example.py"
            source.write_text("print('{\"status\":\"CACHED\"}')\n", encoding="utf-8")
            injected_cache = str(root / "injected-cache")
            # Make the deliberately vulnerable control independent of the
            # qualification runner's inherited isolation/cache configuration.
            with patch.object(sys, "pycache_prefix", injected_cache):
                py_compile.compile(str(source), doraise=True)
            stamp = source.stat().st_mtime_ns
            source.write_text("print('{\"status\":\"SOURCE\"}')\n", encoding="utf-8")
            os.utime(source, ns=(stamp, stamp))
            program = f"import sys; sys.path.insert(0, {str(root)!r}); import example"
            # Preserve the failing witness: -B alone still reads the injected
            # timestamp-valid cache although source bytes say SOURCE.
            vulnerable = integrations._run_json([sys.executable, "-B", "-X",
                "pycache_prefix=" + injected_cache, "-c", program], cwd=root)
            self.assertEqual(vulnerable["status"], "CACHED")
            with patch.dict(os.environ, {"MMC_INTEGRATION_TEMP_ROOT": str(root)}):
                with integrations._source_python() as python:
                    protected = integrations._run_json(python + ["-c", program], cwd=root)
            self.assertEqual(protected["status"], "SOURCE")


if __name__ == "__main__":
    unittest.main()
