"""Successor exceptions must not conceal unrelated predecessor or model drift."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mosaic_mmc import MMCError
from tools.common import ROOT, read_json
from tools_t7 import preservation as audit
from tools_t7.renew_bindings import BINDINGS


class PreservationTests(unittest.TestCase):
    def test_current_realization_binding_rows_match_exact_files(self):
        for relative in BINDINGS:
            binding=read_json(ROOT/relative)
            for row in binding["files"]:
                with self.subTest(binding=relative,path=row["path"]):
                    self.assertEqual(hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest(),
                                     row["sha256"])

    def test_all_predecessor_rows_and_eight_obligations_checked(self):
        result = audit.check_preservation()
        self.assertEqual(result["t5_traceability"]["obligations"], 8)
        self.assertEqual(set(result["reviewed_changes"]), set(audit._changes(ROOT)))
        self.assertGreater(sum(row["checked_files"] for row in result["predecessors"].values()), 400)

    def test_later_unreviewed_change_is_not_hidden_by_first_reviewed_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first").write_bytes(b"replacement")
            (root / "second").write_bytes(b"unreviewed drift")
            digest = lambda value: hashlib.sha256(value).hexdigest()
            rows = [{"path": "first", "sha256": digest(b"old")},
                    {"path": "second", "sha256": digest(b"original")}]
            changes = {"first": {"old_sha256": digest(b"old"),
                                   "new_sha256": digest(b"replacement")}}
            used = set()
            with self.assertRaisesRegex(MMCError, "MMC_T7_UNREVIEWED_PREDECESSOR_CHANGE.*second"):
                audit._verify_rows(root, rows, changes, used)
            self.assertEqual(used, {"first"})

    def test_reviewed_new_bytes_require_exact_old_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "file").write_bytes(b"new")
            digest = lambda value: hashlib.sha256(value).hexdigest()
            with self.assertRaisesRegex(MMCError, "MMC_T7_UNREVIEWED_PREDECESSOR_CHANGE"):
                audit._verify_rows(root, [{"path": "file", "sha256": digest(b"different old")}],
                                   {"file": {"old_sha256": digest(b"old"), "new_sha256": digest(b"new")}}, set())

    def test_removed_predecessor_file_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(MMCError, "MMC_T7_PRESERVATION_FILE"):
                audit._verify_rows(Path(directory), [{"path": "missing", "sha256": "0" * 64}], {}, set())

    def _traceability_with_binding(self, mutate):
        def reader(path):
            value = read_json(path)
            if path.name == "REALIZATION-BINDING.json":
                value = copy.deepcopy(value)
                mutate(value)
            return value
        with patch.object(audit, "read_json", side_effect=reader):
            return audit._t5_traceability(ROOT, audit._changes(ROOT), set(), None)

    def test_missing_obligation_refused_even_with_reviewed_realization(self):
        with self.assertRaisesRegex(MMCError, "MMC_T5_MODEL_COVERAGE"):
            self._traceability_with_binding(lambda value: value["obligations"].pop())

    def test_missing_symbol_refused_even_with_reviewed_realization(self):
        def mutate(value):
            value["obligations"][0]["symbols"][0]["name"] = "unimplemented_symbol"
        with self.assertRaisesRegex(MMCError, "MMC_T5_MODEL_SYMBOL"):
            self._traceability_with_binding(mutate)

    def test_failed_obligation_test_cannot_be_promoted_by_rebinding(self):
        registry = read_json(ROOT / "provenance/turn5/TEST-REGISTRY.json")["tests"]
        executed = {identifier: "PASS" for identifier in registry}
        executed["tests_t5.test_scenarios.EndToEndTests.test_ac_e2e_02_dormant_worker"] = "FAIL"
        with self.assertRaisesRegex(MMCError, "MMC_T5_MODEL_TEST_FAILURE"):
            audit._t5_traceability(ROOT, audit._changes(ROOT), set(), executed)


if __name__ == "__main__":
    unittest.main()
