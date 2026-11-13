from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc_product.surface import operation_catalogue, layer_operation_catalogue
from mosaic_mmc_t2.abi import OPS as T2
from mosaic_mmc_t3.abi import OPERATIONS as T3
from mosaic_mmc_t4.abi import OPERATIONS as T4


class SurfaceTests(unittest.TestCase):
    def test_catalogue_tracks_actual_dispatcher_keys(self):
        catalogue = operation_catalogue()
        rows = catalogue["operations"]
        self.assertEqual(len(rows), catalogue["operation_count"])
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        for layer, expected in {"t2": {name: keys for name, (keys, _) in T2.items()}, "t3": T3, "t4": T4}.items():
            actual = {row["operation"]: set(row["argument_keys"]) for row in rows if row["layer"] == layer}
            self.assertEqual(actual, expected)
        self.assertEqual(sum(row["layer"] == "t1" for row in rows), 5)

    def test_effect_boundary_is_discoverable_and_detached(self):
        catalogue = operation_catalogue()
        self.assertEqual(catalogue["effect_adapter_abi"]["id"], "mmc.effect-adapter.python.v1")
        self.assertEqual(catalogue["effect_adapter_abi"]["production_profile"], "NOT_SHIPPED")
        layer = layer_operation_catalogue()
        controller = next(row for row in layer["host_only"] if row["python"] == "mosaic_mmc_t3.Controller")
        self.assertIn("commit", controller["operations"])
        catalogue["operations"].clear()
        self.assertEqual(operation_catalogue()["operation_count"], 47)
        self.assertEqual(len(operation_catalogue()["operations"]), 47)

    def test_catalogue_runs_without_site_packages_or_signing_backend(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        program = (
            "import sys;from mosaic_mmc_product.surface import operation_catalogue;"
            "assert operation_catalogue()['operation_count']==47;"
            "assert not any(x=='cryptography' or x.startswith('cryptography.') for x in sys.modules)"
        )
        result = subprocess.run([sys.executable, "-S", "-B", "-c", program], env=environment,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()
