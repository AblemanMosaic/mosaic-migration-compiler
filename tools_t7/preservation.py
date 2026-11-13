"""Check every predecessor obligation, allowing only exact reviewed replacements.

Historical byte-preservation tests remain meaningful historical witnesses. This
successor audit scans past their first mismatch and repeats the full T5 symbol
and test traceability audit without changing any frozen contract or oracle.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import sys

if __name__ == "__main__":
    _root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(_root), str(_root / "src")]

from mosaic_mmc import canonical
from mosaic_mmc.errors import require
from mosaic_mmc_t5._pins import CONTRACT_ROOT
from tools.common import ROOT, read_json, sha, verify_freeze
from tools.public_predecessor import load_public_predecessor


def _relevant(path: str) -> bool:
    return path.startswith(("src/", "constitution/", "schemas/", "interop/")) or (
        path.startswith("model/") and Path(path).name in {"CONTRACT.json", "COMMITMENT.json"})


def _regular(root: Path, relative: str) -> Path:
    path = root / relative
    require(path.is_file() and not path.is_symlink(), "MMC_T7_PRESERVATION_FILE", relative)
    for parent in (path, *path.parents):
        if parent == root.parent:
            break
        require(not parent.is_symlink() and not (
            hasattr(parent, "is_junction") and parent.is_junction()),
            "MMC_T7_PRESERVATION_LINK", relative)
    return path


def _changes(root: Path) -> dict[str, dict]:
    record = read_json(root / "provenance/turn7/REVIEWED-SUCCESSOR-CHANGES.json")
    require(record.get("schema") == "mmc.reviewed-successor-changes.v1" and
            record.get("authority_effect") == "NONE" and
            record.get("standing") == "SAME_AUTHOR_ENGINEERING_REVIEW",
            "MMC_T7_REVIEWED_CHANGES_SCHEMA")
    result = {}
    for row in record["changes"]:
        require(set(row) == {"path", "old_sha256", "new_sha256", "reason"} and
                row["path"] not in result and bool(row["reason"]),
                "MMC_T7_REVIEWED_CHANGE_ROW")
        require(row["old_sha256"] != row["new_sha256"] and all(
            type(row[key]) is str and len(row[key]) == 64 and
            set(row[key]) <= set("0123456789abcdef")
            for key in ("old_sha256", "new_sha256")), "MMC_T7_REVIEWED_CHANGE_HASH")
        result[row["path"]] = row
    return result


def _verify_rows(root: Path, rows: list[dict], changes: dict[str, dict],
                 used: set[str]) -> dict:
    paths = set()
    replaced = []
    for row in rows:
        relative = row["path"]
        require(relative not in paths, "MMC_T7_PRESERVATION_DUPLICATE", relative)
        paths.add(relative)
        actual = sha(_regular(root, relative))
        if actual == row["sha256"]:
            continue
        change = changes.get(relative)
        require(change is not None and change["old_sha256"] == row["sha256"] and
                change["new_sha256"] == actual,
                "MMC_T7_UNREVIEWED_PREDECESSOR_CHANGE", relative)
        used.add(relative)
        replaced.append(relative)
    return {"checked_files": len(paths), "reviewed_replacements": sorted(replaced),
            "unchanged_files": len(paths) - len(replaced)}


def _manifest_rows(root: Path, turn: int) -> list[dict]:
    return load_public_predecessor(turn, root, verify_current=False)["rows"]


def _t5_traceability(root: Path, changes: dict[str, dict], used: set[str],
                     executed: dict[str, str] | None) -> dict:
    contract_path = _regular(root, "model/qualification-t5/CONTRACT.json")
    require(hashlib.sha256(b"MMC/T5/CONTRACT\0" + contract_path.read_bytes()).hexdigest() ==
            CONTRACT_ROOT, "MMC_T5_CONTRACT_PIN")
    require(_regular(root, "src/mosaic_mmc_t5/data/CONTRACT.json").read_bytes() ==
            contract_path.read_bytes(), "MMC_T5_CONTRACT_COPY")
    require(read_json(root / "model/qualification-t5/COMMITMENT.json")["sha256"] ==
            CONTRACT_ROOT, "MMC_T5_COMMITMENT")
    binding = read_json(root / "model/qualification-t5/REALIZATION-BINDING.json")
    require(binding["contract_root"] == CONTRACT_ROOT, "MMC_T5_MODEL_ROOT")
    files = _verify_rows(root, binding["files"], changes, used)
    listed = {row["path"] for row in binding["files"]}
    expected = {row["id"] for row in read_json(root / "constitution/REQUIREMENTS.json")["requirements"]
                if row["capability_layer"] == "T5"}
    require(len(binding["obligations"]) == len(expected) == 8 and
            {row["requirement"] for row in binding["obligations"]} == expected,
            "MMC_T5_MODEL_COVERAGE")
    registry = read_json(root / "provenance/turn5/TEST-REGISTRY.json")["tests"]
    require(len(registry) == len(set(registry)), "MMC_T5_MODEL_TEST_IDENTITIES")
    for obligation in binding["obligations"]:
        require(obligation["symbols"] and obligation["tests"] and
                all(identifier in registry for identifier in obligation["tests"]),
                "MMC_T5_MODEL_BINDING")
        for symbol in obligation["symbols"]:
            require(symbol["path"] in listed, "MMC_T5_MODEL_SYMBOL_UNBOUND")
            tree = ast.parse(_regular(root, symbol["path"]).read_text(encoding="utf-8"))
            names = {node.name for node in ast.walk(tree)
                     if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
            require(symbol["name"] in names, "MMC_T5_MODEL_SYMBOL")
        if executed is not None:
            require(all(executed.get(identifier) == "PASS" for identifier in obligation["tests"]),
                    "MMC_T5_MODEL_TEST_FAILURE")
    return {**files, "obligations": len(expected),
            "tests": "CHECKED" if executed is not None else "NOT_SUPPLIED"}


def check_preservation(root: Path = ROOT, *, executed: dict[str, str] | None = None) -> dict:
    verify_freeze(root)
    changes = _changes(root)
    used: set[str] = set()
    rows = {
        "t3": _manifest_rows(root, 2),
        "t4": _manifest_rows(root, 3),
        "t5": _manifest_rows(root, 5),
        "t6": _manifest_rows(root, 6),
    }
    reports = {name: _verify_rows(root, group, changes, used) for name, group in rows.items()}
    traceability = _t5_traceability(root, changes, used, executed)
    require(used == set(changes), "MMC_T7_UNUSED_REVIEWED_CHANGE")
    body = {
        "schema": "mmc.successor-preservation-audit.v1",
        "status": "PASS_PUBLIC_PREDECESSOR_HASH_MANIFESTS_WITH_EXACT_REVIEWED_REPLACEMENTS",
        "predecessors": reports, "t5_traceability": traceability,
        "reviewed_changes": sorted(used),
        "semantic_equivalence_proof": "NOT_ESTABLISHED", "authority_effect": "NONE",
    }
    return {**body, "receipt_root": hashlib.sha256(canonical(body)).hexdigest()}


if __name__ == "__main__":
    print(canonical(check_preservation()).decode("utf-8"))
