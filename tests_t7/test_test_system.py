import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mosaic_mmc.errors import MMCError
from tools.common import source_snapshot
from tools_t7.test_system import contract, plan, resolve_source_pin, validate_discovery_profile
from tools_t7.test_runner import bind_runtime


ROOT = Path(__file__).resolve().parents[1]


class TestSystemTests(unittest.TestCase):
    def test_canonical_groups_preserve_compatibility_paths(self):
        value = contract()
        self.assertEqual([row["name"] for row in value["groups"][:6]],
                         [f"CAPABILITY_LAYER_{index}" for index in range(1, 7)])
        self.assertEqual(value["groups"][6]["name"], "RELEASE_CONVERGENCE")
        self.assertEqual([row["directory"] for row in value["groups"]],
                         ["tests", "tests_t2", "tests_t3", "tests_t4", "tests_t5", "tests_t6", "tests_t7"])
        self.assertEqual(value["artifact_checks"][0]["entry_point"],"mmc-installed-ci")
        self.assertFalse(value["artifact_checks"][0]["release_qualifying"])

    def test_discovery_profile_refuses_missing_environment(self):
        with self.assertRaises(MMCError) as caught:
            validate_discovery_profile({})
        self.assertEqual(caught.exception.code, "MMC_TEST_DISCOVERY_PROFILE_MISSING")

    def test_full_lane_is_exact_registry_denominator(self):
        expected = source_snapshot(ROOT)["root"]
        value = plan("full", expected)
        registry = json.loads((ROOT / "provenance/turn7/TEST-REGISTRY.json").read_text(encoding="utf-8"))
        self.assertEqual(value["selections"], registry["groups"])
        self.assertEqual(value["total"], sum(len(ids) for ids in registry["groups"].values()))
        self.assertTrue(value["release_qualifying"])

    def test_targeted_lanes_are_not_release_qualification(self):
        expected = source_snapshot(ROOT)["root"]
        for lane in ("smoke", "public-ci", "preflight", "contract", "integration", "platform", "publication"):
            with self.subTest(lane=lane):
                value = plan(lane, expected)
                self.assertFalse(value["release_qualifying"])
                self.assertGreater(value["total"], 0)

    def test_public_ci_uses_frozen_registry_without_claiming_release_profile(self):
        expected = source_snapshot(ROOT)["root"]
        value = plan("public-ci", expected)
        self.assertEqual(value["execution_profile"], "PUBLIC_CI_QUALIFICATION_EXTRA_FROM_PYPI")
        self.assertFalse(value["release_qualifying"])
        self.assertEqual(value["admitted_nonpasses"], {
            "tests_t7.test_product.ProductTests.test_exact_cmba_a7_wheel": {
                "outcome": "SKIP",
                "detail": "EXTERNAL_CMBA_A7_QUALIFICATION_WHEEL_NOT_SUPPLIED",
                "reason": "PUBLIC_SOURCE_CI_DOES_NOT_CARRY_OWNER_CUSTODY_NATIVE_WHEELS",
            }
        })

    def test_self_pin_is_diagnostic_only(self):
        expected, origin = resolve_source_pin("public-ci", None, True)
        self.assertEqual(expected, source_snapshot(ROOT)["root"])
        self.assertEqual(origin, "SELF_OBSERVED_DIAGNOSTIC")
        with self.assertRaises(MMCError) as caught:
            resolve_source_pin("full", None, True)
        self.assertEqual(caught.exception.code, "MMC_TEST_SYSTEM_FULL_REQUIRES_EXTERNAL_SOURCE_PIN")

    def test_runner_binds_disposable_state_outside_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary, patch.dict(os.environ, {}):
            output = Path(temporary) / "lane"
            output.mkdir()
            runtime = bind_runtime(output)
            self.assertFalse(runtime.resolve().is_relative_to(ROOT.resolve()))
            for name in ("TEMP", "TMP", "TMPDIR", "MMC_DISPOSABLE_TEMP_ROOT",
                         "MMC_INTEGRATION_TEMP_ROOT"):
                self.assertEqual(os.environ[name], str(runtime))

    def test_runner_child_import_envelope_matches_pinned_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary, patch.dict(
                os.environ, {"PYTHONPATH": "ambient-path-must-not-survive"}):
            output = Path(temporary) / "lane"
            output.mkdir()
            runtime = bind_runtime(output)
            expected = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
            self.assertEqual(os.environ["PYTHONPATH"], expected)
            self.assertEqual(os.environ["PYTHONNOUSERSITE"], "1")
            self.assertEqual(os.environ["PYTHONDONTWRITEBYTECODE"], "1")
            script = (
                "import json,mosaic_mmc,tools_t7.test_system as test_system;"
                "print(json.dumps({'runtime':mosaic_mmc.__file__,"
                "'tool':test_system.__file__},sort_keys=True))"
            )
            completed = subprocess.run(
                [sys.executable, "-c", script], cwd=runtime, env=dict(os.environ),
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            imported = json.loads(completed.stdout)
            self.assertTrue(Path(imported["runtime"]).resolve().is_relative_to((ROOT / "src").resolve()))
            self.assertTrue(Path(imported["tool"]).resolve().is_relative_to(ROOT.resolve()))

    def test_preflight_covers_profile_and_external_input_regressions(self):
        expected = source_snapshot(ROOT)["root"]
        selected = plan("preflight", expected)["selections"]["t7"]
        self.assertTrue(any(value.startswith("tests_t7.test_dependencies.") for value in selected))
        self.assertTrue(any(value.startswith("tests_t7.test_evidence_scope_adapter.") for value in selected))
        self.assertTrue(any(value.startswith("tests_t7.test_integrations.") for value in selected))
