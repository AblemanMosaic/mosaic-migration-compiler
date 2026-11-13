"""Deterministic Release Convergence r013 source and wheel packaging.

The ``t7`` path is a retained source-compatibility namespace, not a seventh capability layer.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical
from tools.package import build_source, regular_files, verify_source_archive, zip_bytes


def build_wheel(root: Path = ROOT) -> bytes:
    values = {relative: path.read_bytes() for relative, path in regular_files(root / "src")}
    base = "mosaic_migration_compiler-0.1.0a9.dist-info/"
    values[base + "METADATA"] = (
        b"Metadata-Version: 2.4\nName: mosaic-migration-compiler\nVersion: 0.1.0a9\n"
        b"Summary: Migration compiler, bounded controller, agent workflows, and explicit integration conformance\n"
        b"Requires-Python: >=3.12\nLicense-Expression: Apache-2.0\n"
        b"License-File: licenses/LICENSE\nLicense-File: licenses/NOTICE\n"
        b"Author: Adam Mazurk\nProvides-Extra: operational\nProvides-Extra: qualification\n"
        b"Requires-Dist: cryptography>=50.0.2,<51; extra == \"operational\" or extra == \"qualification\"\n"
        b"Requires-Dist: jsonschema>=4,<5; extra == \"qualification\"\n"
        b"Requires-Dist: Pillow>=13,<14; extra == \"qualification\"\n\n"
        b"Apache-2.0 public alpha; installation grants no production migration authority.\n"
    )
    values[base + "licenses/LICENSE"] = (root / "LICENSE").read_bytes()
    values[base + "licenses/NOTICE"] = (root / "NOTICE").read_bytes()
    values[base + "WHEEL"] = b"Wheel-Version: 1.0\nGenerator: mmc-stdlib-builder-t7\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    values[base + "entry_points.txt"] = (
        b"[console_scripts]\nmmc = mosaic_mmc.cli:main\nmmc-t2 = mosaic_mmc_t2.cli:main\n"
        b"mmc-t3 = mosaic_mmc_t3.cli:main\nmmc-agent = mosaic_mmc_t4.cli:main\n"
        b"mmc-workbench = mosaic_mmc_workbench.app:main\nmmc-foundry = mosaic_mmc_t5.cli:main\n"
        b"mmc-product = mosaic_mmc_product.cli:main\n"
        b"mmc-installed-ci = mosaic_mmc_product.installed_ci:main\n"
    )
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, value in sorted(values.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b"=").decode("ascii")
        writer.writerow([name, "sha256=" + encoded, str(len(value))])
    writer.writerow([base + "RECORD", "", ""])
    values[base + "RECORD"] = record.getvalue().encode("utf-8")
    return zip_bytes(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    parser.add_argument("--wheel")
    parser.add_argument("--verify-source")
    args = parser.parse_args()
    if args.source:
        Path(args.source).write_bytes(build_source(ROOT))
    if args.wheel:
        Path(args.wheel).write_bytes(build_wheel(ROOT))
    if args.verify_source:
        print(canonical(verify_source_archive(Path(args.verify_source).read_bytes())).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
