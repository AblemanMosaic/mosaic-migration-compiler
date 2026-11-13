"""Check or refresh the installed layer-schema bundle from repository schemas.

Run the native schema generators first when a native structural contract changes.
This command preserves signed 64-bit integers and checks schema read-set closure.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from mosaic_mmc.cli import read_local


def bundle_bytes():
    source = ROOT / "schemas"
    paths = sorted(source.rglob("*.json"), key=lambda path: path.relative_to(source).as_posix())
    require(bool(paths), "MMC_T7_SCHEMA_BUNDLE_EMPTY")
    values = {path.relative_to(source).as_posix(): decode(read_local(str(path)), limit=2 * 1024 * 1024)
              for path in paths}
    return canonical(values)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="replace the generated installed schema bundle")
    args = parser.parse_args(argv)
    target = ROOT / "src/mosaic_mmc_product/data/layer-schemas.json"
    expected = bundle_bytes()
    if args.refresh:
        target.write_bytes(expected + b"\n")
    require(canonical(decode(read_local(str(target)))) == expected, "MMC_T7_SCHEMA_BUNDLE_DRIFT")
    print("PASS_INSTALLED_SCHEMA_BUNDLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
