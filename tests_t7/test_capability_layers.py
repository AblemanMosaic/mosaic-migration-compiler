"""Canonical capability-layer terminology and compatibility boundaries."""
from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

from tools.common import ROOT, read_json, source_snapshot


class CapabilityLayerTerminologyTests(unittest.TestCase):
    def test_program_has_exact_six_layers_and_deprecated_turn_aliases(self):
        program = read_json(ROOT / "constitution/PROGRAM.json")
        layers = program["capability_layers"]
        self.assertEqual([row["id"] for row in layers], [f"T{index}" for index in range(1, 7)])
        self.assertEqual(program["turns"], layers)
        self.assertFalse(program["capability_layer_model"]["release_convergence_is_capability_layer"])
        self.assertEqual(program["capability_layer_model"]["canonical_noun"], "CAPABILITY_LAYER")
        for row in program["workstreams"]:
            self.assertRegex(row["capability_layer"], r"^T[1-6]$")
            self.assertEqual(row["turn"], int(row["capability_layer"][1:]))

    def test_requirements_and_gates_use_layer_field(self):
        requirements = read_json(ROOT / "constitution/REQUIREMENTS.json")["requirements"]
        gates = read_json(ROOT / "constitution/GATES.json")["gates"]
        self.assertEqual(len(requirements), 84)
        self.assertEqual(len(gates), 6)
        for row in requirements:
            self.assertRegex(row["capability_layer"], r"^T[1-6]$")
            self.assertEqual(row["turn"], int(row["capability_layer"][1:]))
        for row in gates:
            self.assertRegex(row["capability_layer"], r"^T[1-6]$")
            self.assertEqual(row["turn"], row["capability_layer"])

    def test_current_orientation_never_presents_turn_as_product_noun(self):
        current = [
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "docs/PROGRAM.md",
            ROOT / "docs/architecture/CAPABILITY-LAYERS.md",
            ROOT / "docs/turn7/README.md",
            ROOT / "docs/turn7/RELEASE-PREPARATION.md",
        ]
        pattern = re.compile(r"\bTurns? [1-7]\b")
        for path in current:
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path.as_posix())

    def test_runtime_and_constitution_copies_match(self):
        for name in ("PROGRAM.json", "REQUIREMENTS.json", "GATES.json"):
            self.assertEqual(
                (ROOT / "constitution" / name).read_bytes(),
                (ROOT / "src/mosaic_mmc/data" / name).read_bytes(),
            )

    def test_worktree_git_pointer_is_not_product_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")
            (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            rows = source_snapshot(root)["body"]["files"]
        self.assertEqual([row["path"] for row in rows], ["tracked.txt"])


if __name__ == "__main__":
    unittest.main()
