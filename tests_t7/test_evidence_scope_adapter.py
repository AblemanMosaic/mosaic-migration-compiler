from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
import json

from tools_t7.evidence_scope_adapter import (
    REQUIRED_EXTERNAL_BINDINGS,
    build_inventory,
    claim_map_request,
    impact_request,
    run_ucm_builder,
    scope_request,
    verify_ucm_source,
)
from mosaic_mmc import MMCError


H = {
    "atlas": "1" * 64,
    "ucm": "2" * 64,
    "jurisdiction": "3" * 64,
    "receipt": "4" * 64,
    "freshness": "5" * 64,
}


class EvidenceScopeAdapterTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        values = {
            "src/mosaic_mmc/runtime.py": b"VALUE = 1\n",
            "src/mosaic_mmc/data/model.schema.json": b"{}\n",
            "src/mosaic_mmc_product/adapter.py": b"ADAPTER = 1\n",
            "tests_t7/test_example.py": b"# test\n",
            "tools_t7/check.py": b"# validator\n",
            "docs/guide.md": b"guide\n",
            "pyproject.toml": b"[build-system]\nrequires=[]\n",
        }
        for relative, raw in values.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def external(self) -> dict[str, str]:
        return {key: format(index + 10, "064x")
                for index, key in enumerate(sorted(REQUIRED_EXTERNAL_BINDINGS))}

    def ucm_roots(self, ucm: Path) -> tuple[str, str]:
        manifest = json.loads((ucm / "release/SOURCE-MANIFEST.json").read_text(encoding="utf-8"))
        atlas = json.loads((ucm / "spec/PIPPI-CONSTITUTIONAL-STANDARDS-ATLAS.json").read_text(
            encoding="utf-8"))
        return manifest["root"], atlas["atlas_root"]

    def test_public_tree_maps_every_file_and_unbound_external_is_incomplete(self):
        root = Path(__file__).resolve().parents[1]
        inventory = build_inventory(
            root, external_bindings={}, atlas_root=H["atlas"],
            ucm_source_manifest_root=H["ucm"])
        self.assertGreater(inventory["member_count"], 400)
        self.assertEqual(inventory["external_closure"], "INCOMPLETE")
        self.assertEqual(
            {row["role"] for row in inventory["components"]},
            {"RUNTIME_EFFECTS", "PROTOCOLS_SCHEMAS", "ADAPTERS", "TESTS",
             "VALIDATORS", "PACKAGING_CI_DOCS", "EXTERNAL_DEPENDENCIES"})

    def test_unknown_source_member_refuses_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            subject = Path(temporary)
            self.fixture(subject)
            (subject / "unknown.bin").write_bytes(b"unknown")
            with self.assertRaisesRegex(MMCError, "MMC_EVIDENCE_SCOPE_UNCLASSIFIED"):
                build_inventory(
                    subject, external_bindings={}, atlas_root=H["atlas"],
                    ucm_source_manifest_root=H["ucm"])

    @unittest.skipUnless(os.environ.get("MMC_UCM_R038_SOURCE"),
                         "exact UCM r038 source is an external qualification input")
    def test_substituted_ucm_identity_refuses_before_cli(self):
        ucm = Path(os.environ["MMC_UCM_R038_SOURCE"])
        _, atlas_root = self.ucm_roots(ucm)
        with self.assertRaisesRegex(MMCError, "MMC_EVIDENCE_SCOPE_UCM_SOURCE_MISMATCH"):
            verify_ucm_source(
                ucm, expected_source_manifest_root="f" * 64,
                expected_atlas_root=atlas_root)

    @unittest.skipUnless(os.environ.get("MMC_UCM_R038_SOURCE"),
                         "exact UCM r038 source is an external qualification input")
    def test_packaging_only_change_uses_ucm_impact_engine(self):
        ucm = Path(os.environ["MMC_UCM_R038_SOURCE"])
        ucm_root, atlas_root = self.ucm_roots(ucm)
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            subject = workspace / "subject"
            out = workspace / "out"
            self.fixture(subject)
            external = self.external()
            before_inventory = build_inventory(
                subject, external_bindings=external, atlas_root=atlas_root,
                ucm_source_manifest_root=ucm_root)
            before = run_ucm_builder(
                ucm_source=ucm, operation="scope-profile",
                request=scope_request(before_inventory, jurisdiction_root=H["jurisdiction"]),
                output=out / "before.json", expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            claims = run_ucm_builder(
                ucm_source=ucm, operation="claim-map",
                request=claim_map_request(
                    before, effect_raw_evidence_roots=[H["receipt"]],
                    validator_raw_evidence_roots=[H["receipt"]]),
                output=out / "claims.json", expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            (subject / "docs/guide.md").write_bytes(b"changed guide\n")
            after_inventory = build_inventory(
                subject, external_bindings=external, atlas_root=atlas_root,
                ucm_source_manifest_root=ucm_root)
            after = run_ucm_builder(
                ucm_source=ucm, operation="scope-profile",
                request=scope_request(after_inventory, jurisdiction_root=H["jurisdiction"]),
                output=out / "after.json", expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            impact = run_ucm_builder(
                ucm_source=ucm, operation="impact",
                request=impact_request(
                    before_profile=before, after_profile=after, claim_map=claims,
                    effect_freshness_root=H["freshness"],
                    portability_freshness_root=None, release_candidate=False,
                    candidate_frozen=False, review_saturation_root=None),
                output=out / "impact.json", expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            dispositions = {row["claim_id"]: row["disposition"]
                            for row in impact["claim_dispositions"]}
            self.assertEqual(dispositions["runtime-conformance"], "RETAIN")
            self.assertEqual(dispositions["migration-lifecycle"], "RETAIN")
            self.assertEqual(dispositions["packaging-custody"], "RERUN_PURE_CHECK")
            self.assertEqual(dispositions["portability"], "REFRESH_OBSERVATION")
            self.assertFalse(impact["effect_execution_authorized"])
            self.assertFalse(impact["release_qualified"])

    @unittest.skipUnless(os.environ.get("MMC_UCM_R038_SOURCE"),
                         "exact UCM r038 source is an external qualification input")
    def test_empty_external_closure_forces_full_qualification(self):
        ucm = Path(os.environ["MMC_UCM_R038_SOURCE"])
        ucm_root, atlas_root = self.ucm_roots(ucm)
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            subject = workspace / "subject"
            out = workspace / "out"
            self.fixture(subject)
            inventory = build_inventory(
                subject, external_bindings={}, atlas_root=atlas_root,
                ucm_source_manifest_root=ucm_root)
            profile = run_ucm_builder(
                ucm_source=ucm, operation="scope-profile",
                request=scope_request(inventory, jurisdiction_root=H["jurisdiction"]),
                output=out / "profile.json", expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            claims = run_ucm_builder(
                ucm_source=ucm, operation="claim-map",
                request=claim_map_request(profile), output=out / "claims.json",
                expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            impact = run_ucm_builder(
                ucm_source=ucm, operation="impact",
                request=impact_request(
                    before_profile=profile, after_profile=profile, claim_map=claims,
                    effect_freshness_root=None, portability_freshness_root=None,
                    release_candidate=False, candidate_frozen=False,
                    review_saturation_root=None),
                output=out / "impact.json", expected_ucm_source_manifest_root=ucm_root,
                expected_atlas_root=atlas_root)
            self.assertEqual(impact["status"], "FULL_QUALIFICATION_REQUIRED")
            self.assertEqual(impact["global_reason_codes"],
                             ["DEPENDENCY_CLOSURE_INCOMPLETE"])
            self.assertEqual(impact["disposition_counts"]["FULL_QUALIFICATION"],
                             impact["claim_denominator"])


if __name__ == "__main__":
    unittest.main()
