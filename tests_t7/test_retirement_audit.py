"""Retirement disposition witnesses found by the release audit."""
import unittest

from tests_t2.helpers import model, retirement
from mosaic_mmc_t2 import assess_retirement


class RetirementDispositionAudit(unittest.TestCase):
    def test_upgrade_cannot_relabel_legacy_worker(self):
        record = retirement()
        record["workers"][0]["disposition"] = "UPGRADE"
        self.assertEqual(assess_retirement(model(), record)["status"],
                         "BLOCKED_FOR_SUPPLIED_MODEL")

    def test_upgrade_cannot_keep_legacy_resume_path(self):
        record = retirement()
        record["workers"][0].update(disposition="UPGRADE", code_version="new")
        self.assertEqual(assess_retirement(model(), record)["status"],
                         "BLOCKED_FOR_SUPPLIED_MODEL")

    def test_upgrade_to_new_runtime_permits_retirement(self):
        record = retirement()
        record["workers"][0].update(disposition="UPGRADE", code_version="new",
                                     resume_version="new", status="UPGRADED")
        self.assertEqual(assess_retirement(model(), record)["status"],
                         "MODEL_RETIREMENT_CONDITIONS_MET")

    def test_fence_disposition_requires_worker_fence_without_producer_role(self):
        candidate = model()
        worker = next(row for row in candidate["objects"] if row["id"] == "producer.old")
        worker["attributes"]["roles"] = ["worker"]
        for flow in candidate["objects"]:
            if flow["kind"] == "Flow":
                flow["attributes"]["legacy"] = False
        record = retirement()
        record["producers"] = []
        record["workers"][0].update(code_version="new", resume_version="new",
                                     fenced=False, disposition="FENCE")
        self.assertEqual(assess_retirement(candidate, record)["status"],
                         "BLOCKED_FOR_SUPPLIED_MODEL")
        record["workers"][0]["fenced"] = True
        self.assertEqual(assess_retirement(candidate, record)["status"],
                         "MODEL_RETIREMENT_CONDITIONS_MET")


if __name__ == "__main__":
    unittest.main()
