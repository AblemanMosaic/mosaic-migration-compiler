"""Verify public, hash-only predecessor manifests.

The public repository does not redistribute the private source archives used
during development.  These manifests retain only the paths and digests needed
to prove preservation of executable and contract semantics.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from mosaic_mmc import canonical
from mosaic_mmc.errors import require
from tools.common import ROOT, read_json, sha


def load_public_predecessor(turn: int, root: Path = ROOT, *, verify_current: bool = True,
                            error_stage: int | None = None) -> dict:
    record = read_json(root / f"provenance/public-predecessors/turn{turn}.json")
    require(record.get("schema") == "mosaic.mmc.public-predecessor-manifest.v0.1",
            "MMC_PUBLIC_PREDECESSOR_SCHEMA")
    require(record.get("turn") == turn and record.get("authority_effect") == "NONE",
            "MMC_PUBLIC_PREDECESSOR_IDENTITY")
    supplied = record.get("root")
    body = {key: value for key, value in record.items() if key != "root"}
    require(supplied == hashlib.sha256(canonical(body)).hexdigest(),
            "MMC_PUBLIC_PREDECESSOR_ROOT")
    rows = record.get("rows")
    require(isinstance(rows, list) and len(rows) == record.get("row_count"),
            "MMC_PUBLIC_PREDECESSOR_COUNT")
    paths: set[str] = set()
    for row in rows:
        require(set(row) == {"path", "bytes", "sha256"} and
                isinstance(row["bytes"], int) and row["bytes"] >= 0 and
                row["path"] not in paths,
                "MMC_PUBLIC_PREDECESSOR_ROW")
        paths.add(row["path"])
        if verify_current:
            path = root / row["path"]
            require(path.is_file() and not path.is_symlink() and
                    path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                    f"MMC_T{error_stage if error_stage is not None else turn + 1}_PREDECESSOR_CHANGED",
                    row["path"])
    return record
