"""Product requests reuse the admitted bounded regular-file reader."""
from __future__ import annotations
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import decode
from mosaic_mmc_product.cli import main


class CLIInputBoundsTests(unittest.TestCase):
    def invoke(self, path):
        output = io.BytesIO()
        with patch("sys.stdout", SimpleNamespace(buffer=output)):
            status = main(["request", str(path)])
        return status, decode(output.getvalue())

    def test_large_file_is_refused_before_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversize.json"
            with path.open("wb") as handle:
                handle.seek(8 * 1024 * 1024)
                handle.write(b"x")
            with patch("mosaic_mmc.cli.os.open", side_effect=AssertionError("file was opened")):
                status, response = self.invoke(path)
            self.assertEqual(status, 2)
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "MMC_BYTE_LIMIT")

    def test_directory_has_typed_input_kind_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            status, response = self.invoke(Path(directory))
            self.assertEqual(status, 2)
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "MMC_INPUT_KIND")


if __name__ == "__main__":
    unittest.main()
