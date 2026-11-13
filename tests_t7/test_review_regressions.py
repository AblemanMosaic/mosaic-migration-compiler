from __future__ import annotations

import io
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from mosaic_mmc import MMCError
from mosaic_mmc_product import disposable
from tools_t7.qualify import _host_limitation, _outcomes, _superseded

ROOT = Path(__file__).resolve().parents[1]


class ReviewRegressionTests(unittest.TestCase):
    def test_linux_ci_uses_versioned_copied_interpreter(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("../mmc-ci-venv/bin/python3.12", workflow)
        self.assertNotIn("../mmc-ci-venv/bin/python\n", workflow)

    def test_copy_corruption_with_recomputed_checksum_is_rejected(self):
        original = sqlite3.connect
        class CorruptingConnection(sqlite3.Connection):
            def execute(self, sql, parameters=(), /):
                if sql.strip().startswith("INSERT INTO new_records"):
                    parameters = (*parameters[:2], "CORRUPTED", disposable._sha(b"CORRUPTED"))
                return super().execute(sql, parameters)
        def connect(*args, **kwargs):
            return original(*args, factory=CorruptingConnection, **kwargs)
        with patch.object(disposable.sqlite3, "connect", side_effect=connect):
            with self.assertRaisesRegex(RuntimeError, "SOURCE_DESTINATION_MISMATCH"):
                disposable.run_disposable_migration()

    def test_subtest_failure_cannot_be_counted_as_pass(self):
        class Probe(unittest.TestCase):
            def runTest(self):
                with self.subTest(record=1):
                    self.fail("witness")
        case = Probe()
        result = unittest.TextTestRunner(stream=io.StringIO()).run(case)
        outcomes, details = _outcomes([case.id()], result)
        self.assertEqual(outcomes[case.id()], "FAIL")
        self.assertIn("witness", details[case.id()])

    def test_expected_failure_and_unexpected_success_are_visible(self):
        class Probe(unittest.TestCase):
            @unittest.expectedFailure
            def test_failure(self): self.fail("expected")
            @unittest.expectedFailure
            def test_success(self): pass
        cases = [Probe("test_failure"), Probe("test_success")]
        result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite(cases))
        outcomes, _ = _outcomes([case.id() for case in cases], result)
        self.assertEqual(set(outcomes.values()), {"EXPECTED_FAILURE", "UNEXPECTED_SUCCESS"})

    def test_empty_suite_is_not_a_pass(self):
        with self.assertRaises(MMCError):
            _outcomes([], unittest.TestResult())

    def test_historical_id_does_not_exempt_arbitrary_error(self):
        identifier = "tests_t3.test_qualification.QualificationTests.test_predecessor_runtime_preserved"
        self.assertFalse(_superseded(identifier, "RuntimeError: broken\n", "ERROR"))
        self.assertFalse(_superseded(identifier, "mosaic_mmc.errors.MMCError: MMC_T3_PREDECESSOR_CHANGED at interop/t2-known-answers.json: \n", "ERROR"))
        for layer, test_id in (
            (2, "tests_t2.test_integration.IntegrationTests.test_t1_runtime_exact_preservation"),
            (3, identifier),
            (4, "tests_t4.test_release.ReleaseTests.test_original_runtime_exact"),
            (5, "tests_t5.test_qualification.QualificationTests.test_all_predecessor_runtime_semantics_exact"),
            (6, "tests_t6.test_release.ReleaseTests.test_runtime_preserved"),
        ):
            with self.subTest(layer=layer):
                detail = (f"mosaic_mmc.errors.MMCError: MMC_T{layer}_PREDECESSOR_CHANGED "
                          "at constitution/AMENDMENT-POLICY.md: \n")
                self.assertTrue(_superseded(test_id, detail, "ERROR"))
        t2_error = "tests_t2.test_integration.IntegrationTests.test_t1_runtime_exact_preservation"
        self.assertTrue(_superseded(t2_error, "mosaic_mmc.errors.MMCError: MMC_T2_PREDECESSOR_CHANGED at constitution/AMENDMENT-POLICY.md: \n", "ERROR"))
        t2_failure = "tests_t2.test_integration.IntegrationTests.test_t1_compilation_exact_against_predecessor"
        actual = "c521579584b4f6c7a53146c9e6006e65654ec09f69671ecaf7f4895de157598b"
        predecessor = "b8387cf06a06e26b290b8c3827c644068defd4ce8484167de98186d87452ee64"
        detail = f"AssertionError: '{actual}' != '{predecessor}'\n- {actual}\n+ {predecessor}\n"
        self.assertTrue(_superseded(t2_failure, detail, "FAIL"))

    def test_arbitrary_gui_and_export_errors_are_not_host_limitations(self):
        with patch("tools_t7.qualify.platform.system", return_value="Windows"):
            self.assertFalse(_host_limitation("tests_t4.test_native_gui.GUIQualificationTests.test_actual_tk_interaction", "RuntimeError: regression", "ERROR"))
            self.assertFalse(_host_limitation("tests_t4.test_exports.ExportTests.test_one_use_host_token", "MMC_T4_EXPORT_INSTALL_UNSUPPORTED", "ERROR"))

    def test_host_limitation_uses_recorded_host_when_reviewed_elsewhere(self):
        identifier = "tests.test_boundaries.IOBoundaryTests.test_symlink_refused"
        with patch("tools_t7.qualify.platform.system", return_value="Linux"):
            self.assertTrue(_host_limitation(identifier, "WinError 1314", "ERROR", host_system="Windows"))
        with patch("tools_t7.qualify.platform.system", return_value="Windows"):
            self.assertFalse(_host_limitation(identifier, "WinError 1314", "ERROR", host_system="Linux"))

    def test_ucm_effect_declaration_has_no_fabricated_observation(self):
        # Inspect this pure helper without importing optional UCM into the product.
        import ast
        source = (Path(__file__).resolve().parents[1] / "tools_t7/build_stage1.py").read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_ucm_effect_facts")
        self.assertNotIn("journal_append_observed", ast.unparse(function))


if __name__ == "__main__":
    unittest.main()
