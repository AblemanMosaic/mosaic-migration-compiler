"""Renew implementation bindings for explicitly reviewed successor paths.

This mechanical maintenance is not independent semantic evidence. New or newly
changed predecessor paths require an explicit --reviewed-path PATH=REASON
disposition, including a fresh reason when an already-reviewed path changes again.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = str(ROOT.parent / ("binding-import-cache-" + uuid.uuid4().hex))
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from tools.common import source_snapshot


BINDINGS = (
    "model/foundation/REALIZATION-BINDING.json",
    "model/domain-t2/REALIZATION-BINDING.json",
    "model/operational-t3/REALIZATION-BINDING.json",
    "model/interfaces-t4/REALIZATION-BINDING.json",
    "model/qualification-t5/REALIZATION-BINDING.json",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_binding_rows() -> None:
    """Refresh current realization rows after deterministic fixture generation."""
    for relative in BINDINGS:
        path=ROOT/relative
        binding=decode(path.read_bytes(),limit=8*1024*1024)
        for row in binding["files"]:
            member=ROOT/row["path"]
            require(member.is_file(),"MMC_T7_BINDING_FILE",row["path"])
            row["sha256"]=_sha(member)
        path.write_bytes(canonical(binding))


def _reviewed_rows(existing: dict[str, dict], additions: dict[str, str]) -> list[dict]:
    """Retain exactly the current differences in governed predecessor manifests."""
    from tools.public_predecessor import load_public_predecessor
    previous: dict[str,set[str]]={}
    for layer in (2,3,5,6):
        for row in load_public_predecessor(layer,ROOT,verify_current=False)["rows"]:
            previous.setdefault(row["path"],set()).add(row["sha256"])
    required={path for path,hashes in previous.items()
              if (ROOT/path).is_file() and any(_sha(ROOT/path)!=value for value in hashes)}
    for path in additions:
        require(path in required,"MMC_T7_BINDING_REVIEW_PATH",path)
    rows=[]
    for path in sorted(required):
        hashes=previous[path]
        require(len(hashes)==1,"MMC_T7_BINDING_PREDECESSOR_AMBIGUOUS",path)
        reason=additions.get(path,existing.get(path,{}).get("reason",""))
        require(reason.strip(),"MMC_T7_BINDING_REVIEW_REQUIRED",path)
        rows.append({"path":path,"old_sha256":next(iter(hashes)),
                     "new_sha256":_sha(ROOT/path),"reason":reason})
    return rows


def renew(expected_source: str, additions: dict[str, str]) -> dict:
    require(source_snapshot(ROOT)["root"] == expected_source, "MMC_T7_BINDING_SOURCE_PIN")
    ledger_path = ROOT / "provenance/turn7/REVIEWED-SUCCESSOR-CHANGES.json"
    ledger = decode(ledger_path.read_bytes(), limit=8 * 1024 * 1024)
    rows = {row["path"]: row for row in ledger["changes"]}
    for path, reason in additions.items():
        require(reason.strip(), "MMC_T7_BINDING_REVIEW_PATH", path)
        if path in rows:
            require(rows[path].get("path") == path
                    and len(rows[path].get("old_sha256", "")) == 64,
                    "MMC_T7_BINDING_REVIEW_HISTORY", path)
            rows[path]["reason"] = reason
    from tools_t7.author_successor_vectors import main as vectors
    from tools_t7.rebind_t4 import rebind
    from mosaic_mmc_t2.common import realization_identity
    from mosaic_mmc_t3.common import realization
    from mosaic_mmc_t5.foundry import realization as t5_realization
    vectors(); rebind(); _refresh_binding_rows()
    roots = {"schema": "mmc.portable-realization-roots.t7", "t2": realization_identity(),
             "t3": realization(), "t5": t5_realization()}
    (ROOT / "provenance/turn7/REALIZATION-ROOTS.json").write_bytes(canonical(roots))
    ledger["changes"] = _reviewed_rows(rows,additions)
    ledger_path.write_bytes(canonical(ledger))
    from tools_t7.preservation import check_preservation
    audit = check_preservation()
    return {"schema": "mmc.binding-renewal.v1", "input_source_root": expected_source,
            "output_source_root": source_snapshot(ROOT)["root"], "realizations": roots,
            "preservation_root": audit["receipt_root"], "reviewed_paths": sorted(rows),
            "independent_semantic_evidence": False, "authority_effect": "NONE"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--reviewed-path", action="append", default=[])
    args = parser.parse_args()
    additions = {}
    for value in args.reviewed_path:
        path, separator, reason = value.partition("=")
        require(separator and path not in additions, "MMC_T7_BINDING_REVIEW_ARGUMENT")
        additions[path] = reason
    result = renew(args.expected_source, additions)
    print(canonical(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
