"""Real directory-alias refusal, including unprivileged Windows junctions.

These supplement file-symlink tests; a junction pass does not qualify those
tests when the Windows account cannot create symbolic links.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mosaic_mmc import MMCError, decode
from mosaic_mmc.cli import read_local
from mosaic_mmc_t3.storage import SimulatedStore
from mosaic_mmc_t4.collectors import FileCollector
from mosaic_mmc_t4.exports import LocalExport
from mosaic_mmc_product.transport_wire import safe_host_path
from tools.package import build_source


class NativeAliasTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.real = self.root / "real"
        self.real.mkdir()
        self.alias = self.root / "alias"
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(self.real), str(self.alias))
            self.addCleanup(self.alias.rmdir)
            self.assertTrue(self.alias.is_junction())
        else:
            self.alias.symlink_to(self.real, target_is_directory=True)
            self.assertTrue(self.alias.is_symlink())
        (self.real / "input.json").write_bytes(b"{}")

    def test_input_parent_alias_refused(self):
        with self.assertRaisesRegex(MMCError, "MMC_INPUT_LINK"):
            read_local(str(self.alias / "input.json"))

    def test_source_builder_alias_refused(self):
        with self.assertRaisesRegex(MMCError, "MMC_SOURCE_LINK"):
            build_source(self.root)

    def test_store_parent_alias_refused(self):
        with self.assertRaisesRegex(MMCError, "LINK"):
            SimulatedStore(self.alias / "target.sqlite")

    def test_t3_cli_parent_alias_refused(self):
        result = subprocess.run([sys.executable, "-B", "-m", "mosaic_mmc_t3.cli",
                                 "request", str(self.alias / "input.json")],
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(decode(result.stdout)["code"], "MMC_T3_FILE_LINK")

    def test_collector_parent_alias_refused(self):
        with self.assertRaisesRegex(MMCError, "MMC_T4_PATH_LINK"):
            FileCollector(self.root, "source.test", ["alias/input.json"])

    def test_export_directory_alias_refused(self):
        with self.assertRaisesRegex(MMCError, "MMC_T4_EXPORT_LINK"):
            LocalExport(self.alias)

    def test_worker_implementation_alias_refused(self):
        with self.assertRaisesRegex(MMCError, "MMC_TRANSPORT_IMPLEMENTATION_PATH"):
            safe_host_path(self.alias, directory=True)
