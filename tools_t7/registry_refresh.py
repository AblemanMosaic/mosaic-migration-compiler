"""Deterministic, source-admitted test discovery. Does not execute test methods."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = str(ROOT.parent / ("registry-import-cache-" + uuid.uuid4().hex))
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from tools.common import source_snapshot, regular_files
from tools.qualify import flattened
from tools_t7.test_system import groups as canonical_groups, validate_discovery_profile

GROUPS = canonical_groups()


def test_inputs(root: Path = ROOT) -> dict:
    rows = [{"path": path, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
            for path, file in regular_files(root)
            if path.split("/")[0] in GROUPS.values() and path.endswith(".py")]
    return {"files": rows, "sha256": hashlib.sha256(canonical(rows)).hexdigest()}


def refresh(expected_source: str, *, write: bool = False) -> dict:
    before = source_snapshot(ROOT)
    require(before["root"] == expected_source, "MMC_T7_REGISTRY_SOURCE_PIN")
    profile = validate_discovery_profile()
    inputs = test_inputs()
    groups = {}
    for name, directory in GROUPS.items():
        suite = unittest.defaultTestLoader.discover(str(ROOT / directory), top_level_dir=str(ROOT))
        ids = sorted(case.id() for case in flattened(suite))
        require(ids and len(ids) == len(set(ids)) and
                not any("_FailedTest" in value for value in ids), "MMC_T7_REGISTRY_DISCOVERY", name)
        groups[name] = ids
    require(source_snapshot(ROOT) == before, "MMC_T7_REGISTRY_SOURCE_CHANGED")
    record = {"schema": "mmc.admitted-tests.t7", "groups": groups,
              "authority_effect": "NONE"}
    path = ROOT / "provenance/turn7/TEST-REGISTRY.json"
    current = decode(path.read_bytes(), limit=8 * 1024 * 1024)
    # Preserve the existing registry's metadata, while updating its exact denominator.
    record = {**current, "groups": groups}
    if "total" in record:
        record["total"] = sum(map(len, groups.values()))
    drift = current != record
    if write:
        path.write_bytes(canonical(record))
    else:
        require(not drift, "MMC_T7_TEST_REGISTRY_DRIFT")
    return {"schema": "mmc.registry-refresh.v1", "status": "UPDATED" if drift else "UNCHANGED",
            "input_source_root": expected_source, "output_source_root": source_snapshot(ROOT)["root"],
            "test_inputs": inputs, "discovery_profile": profile,
            "total": sum(map(len, groups.values())),
            "registry_sha256": hashlib.sha256(canonical(record)).hexdigest(),
            "test_methods_executed": False, "authority_effect": "NONE"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--write", action="store_true", help="explicitly replace the admitted registry")
    args = parser.parse_args()
    print(canonical(refresh(args.expected_source, write=args.write)).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
