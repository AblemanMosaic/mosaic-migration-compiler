from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import decode
from mosaic_mmc_product import capabilities, integration_status
from mosaic_mmc_product.integrations import AMCAS_CONTRACT_ROOT, verify_cmba_wheel
from mosaic_mmc_product.disposable import run_disposable_migration
from mosaic_mmc_product.installed_ci import installed_origins
from mosaic_mmc_t2.common import realization_identity as t2_identity
from mosaic_mmc_t3.common import realization as t3_identity
from mosaic_mmc_t5.foundry import realization as t5_identity
from mosaic_mmc_workbench.model import Workbench
from tools_t4.check_vectors import check as check_t4


class ProductTests(unittest.TestCase):
    def test_installed_ci_refuses_source_checkout_imports(self):
        from mosaic_mmc import MMCError
        with self.assertRaisesRegex(MMCError,'MMC_INSTALLED_CI_SOURCE_IMPORT'):
            installed_origins(ROOT)

    def test_unified_capabilities_cover_requested_model(self):
        result = capabilities()
        self.assertEqual(result["version"], "0.1.0a9")
        self.assertEqual(result["revision"], "RELEASE-CONVERGENCE-r013")
        self.assertEqual(
            result["public_release"],
            "APACHE_2_0_SOURCE_AND_DKN_ENDORSED_ASSETS_AUTHORIZED_FOR_PUBLICATION",
        )
        self.assertEqual(result["uniform_effect_abi"], "MMC_EFFECT_ADAPTER_PYTHON_V1_HOST_SELECTED")
        self.assertEqual(result["production_effect_adapter"], "NOT_SHIPPED")
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(set(result["model_coverage"]), {
            "PERSISTED_DATA", "PRODUCERS", "CONSUMERS", "DEPENDENCY_ORDER",
            "COEXISTENCE", "COHORTS", "USE_CASES", "UNCERTAINTY", "EVIDENCE",
            "RETIREMENT_GATES", "TARGETED_ROLLBACK", "POINT_OF_EFFECT_RECHECK",
            "RECONCILIATION",
        })

    def test_current_integrations_are_exact_and_non_authorizing(self):
        result = integration_status()
        self.assertEqual(result["integrations"]["cmba"]["version"], "0.1.0a7")
        self.assertEqual(result["integrations"]["ucm"]["git_commit"], "9877d745129fa31f9141d74e245fa90fc3c51d8b")
        self.assertFalse(result["integrations"]["semcrys"]["migration_eligibility_source"])
        self.assertEqual(result["native_semantic_authority"], "MMC_NATIVE")
        self.assertEqual(result["effect_executor"], "MMC_NATIVE_CONTROLLER")
        self.assertEqual(result["authority_effect"], "NONE")

    def test_exact_cmba_a7_wheel(self):
        supplied = os.environ.get("MMC_QUALIFICATION_CMBA_A7_WHEEL")
        if not supplied:
            self.skipTest("EXTERNAL_CMBA_A7_QUALIFICATION_WHEEL_NOT_SUPPLIED")
        result = verify_cmba_wheel(Path(supplied))
        self.assertEqual(result["status"], "PASS_EXACT_WHEEL")

    def test_amcas_subject_and_control_plane_match(self):
        contract = json.loads((ROOT / "interop/ucm/MMC-AMCAS-CONTRACT.json").read_text(encoding="utf-8"))
        binding = json.loads((ROOT / "interop/ucm/SUBJECT-BINDING.json").read_text(encoding="utf-8"))
        control = json.loads((ROOT / "interop/ucm/CONTROL-PLANE-DISPOSITION.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["subject"]["source_root"], binding["source_root"])
        self.assertEqual(contract["subject"]["manifest_root"], binding["manifest_root"])
        self.assertEqual(contract["integration_boundary"]["control_plane_root"], control["root"])
        self.assertEqual(contract["integration_boundary"]["semantic_authority"], "MMC_NATIVE")
        self.assertEqual(contract["integration_boundary"]["effect_executor"], "MMC_NATIVE_CONTROLLER")
        self.assertEqual(contract["contract_root"], AMCAS_CONTRACT_ROOT)
        reconcile = next(row for row in contract["capabilities"] if row["id"] == "RECONCILE_CONTROLLER")
        self.assertEqual(reconcile["effect_class"], "WRITE_WORKSPACE")
        self.assertEqual(contract["effects"], [{
            "capability_id": "RECONCILE_CONTROLLER",
            "ceiling": "NONE",
            "effect_class": "WRITE_WORKSPACE",
            "id": "RECONCILE_JOURNAL_OUTCOME",
            "operation": "mmc.controller.reconcile.outcome",
        }])

    def test_portable_realization_roots(self):
        expected = json.loads((ROOT / "provenance/turn7/REALIZATION-ROOTS.json").read_text(encoding="utf-8"))
        self.assertEqual(t2_identity(), expected["t2"])
        self.assertEqual(t3_identity(), expected["t3"])
        self.assertEqual(t5_identity(), expected["t5"])

    def test_cli_current_surface(self):
        environment = dict(__import__("os").environ)
        environment["PYTHONPATH"] = str(ROOT / "src")
        run = subprocess.run([sys.executable, "-B", "-m", "mosaic_mmc_product", "capabilities"],
                             cwd=ROOT, env=environment, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace"))
        self.assertEqual(decode(run.stdout)["schema"], "mmc.product-capabilities.v1")

    def test_t4_demo_and_exact_vectors_survive_successor_identity(self):
        demo = decode((ROOT / "src/mosaic_mmc_t4/data/demo.json").read_bytes())
        workbench = Workbench()
        self.assertEqual(workbench.load(demo["workspace"])["schema"], "mmc.workbench-status.t4")
        self.assertEqual(len(check_t4()["cases"]), 33)

    def test_real_disposable_migration(self):
        receipt = run_disposable_migration()
        self.assertEqual(receipt["status"], "PASS_NATIVE_CONTROLLER_DISPOSABLE_MIGRATION_RETIREMENT_RECOVERY")
        self.assertIn("T3_NATIVE_CONTROLLER", receipt["execution_path"])
        self.assertEqual(receipt["lost_ack_reconciliation"]["after_restart"], "APPLIED")
        self.assertEqual(receipt["recovery"]["route"], "RECOVERY_DUAL")
        self.assertEqual(len(receipt["completed_transitions"]), 7)
        self.assertEqual(receipt["dormant_worker_resume"]["status"], "LEGACY_WRITE_FENCED")
        self.assertEqual(receipt["retirement_status"], "MODEL_RETIREMENT_CONDITIONS_MET")
        self.assertEqual(receipt["recovery_legacy_write"], "LEGACY_WRITE_FENCED")


if __name__ == "__main__":
    unittest.main()
