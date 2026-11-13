from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from mosaic_mmc import MMCError
from tools_t7.qualification_index import (
    assess_reuse,
    build_index,
    require_reuse,
    verify_index,
)


RECEIPT = "a" * 64
EXTERNAL = {"dependency.lock": "b" * 64}


class QualificationIndexTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        values = {
            "src/example.py": b"VALUE = 1\n",
            "examples/example.json": b"{}\n",
            "tests_t7/test_example.py": b"# test\n",
            "tools_t7/qualification_index.py": b"# tool\n",
            "pyproject.toml": b"[build-system]\nrequires=[]\n",
            "docs/guide.md": b"guide\n",
            "provenance/record.json": b"{}\n",
            ".github/workflows/ci.yml": b"name: ci\n",
            ".gitignore": b"__pycache__/\n",
        }
        for relative, raw in values.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def test_public_tree_has_complete_component_coverage(self):
        index = build_index(Path(__file__).resolve().parents[1])
        self.assertEqual(verify_index(index), index)
        self.assertGreater(index["member_count"], 400)
        self.assertEqual(sum(row["member_count"] for row in index["components"].values()),
                         index["member_count"])

    def test_legacy_compare_never_authorizes_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            before = build_index(root, external_bindings=EXTERNAL)
            (root / "docs/guide.md").write_bytes(b"changed guide\n")
            after = build_index(root, external_bindings=EXTERNAL)
            with self.assertRaisesRegex(MMCError, "MMC_EVIDENCE_REUSE_REQUIRES_UCM_IMPACT"):
                require_reuse(before, after, "runtime-conformance", RECEIPT)
            refused = assess_reuse(before, after, "release-envelope", RECEIPT)
            self.assertEqual(refused["status"],
                             "REUSE_REFUSED_UCM_REQUALIFICATION_IMPACT_REQUIRED")
            self.assertEqual(refused["relevant_changed_components"], ["documentation"])

    def test_runtime_or_external_change_refuses_migration_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            before = build_index(root, external_bindings=EXTERNAL)
            (root / "src/example.py").write_bytes(b"VALUE = 2\n")
            changed = build_index(root, external_bindings=EXTERNAL)
            with self.assertRaisesRegex(MMCError, "MMC_EVIDENCE_REUSE_REQUIRES_UCM_IMPACT"):
                require_reuse(before, changed, "migration-lifecycle", RECEIPT)
            restored = build_index(root, external_bindings={"dependency.lock": "c" * 64})
            result = assess_reuse(changed, restored, "migration-lifecycle", RECEIPT)
            self.assertFalse(result["external_bindings_equal"])
            self.assertEqual(result["status"],
                             "REUSE_REFUSED_UCM_REQUALIFICATION_IMPACT_REQUIRED")

    def test_equal_empty_external_bindings_never_allow_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            before = build_index(root)
            after = build_index(root)
            result = assess_reuse(before, after, "runtime-conformance", RECEIPT)
            self.assertTrue(result["external_bindings_equal"])
            self.assertEqual(result["status"],
                             "REUSE_REFUSED_UCM_REQUALIFICATION_IMPACT_REQUIRED")

    def test_tampered_index_and_unclassified_file_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            index = build_index(root)
            tampered = deepcopy(index)
            tampered["components"]["runtime"]["root"] = "0" * 64
            with self.assertRaisesRegex(MMCError, "MMC_QUALIFICATION_INDEX_ROOT"):
                verify_index(tampered)
            (root / "unknown.bin").write_bytes(b"unknown")
            with self.assertRaisesRegex(MMCError, "MMC_QUALIFICATION_INDEX_UNCLASSIFIED"):
                build_index(root)


if __name__ == "__main__":
    unittest.main()
