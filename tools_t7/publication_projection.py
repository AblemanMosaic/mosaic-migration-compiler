"""Audit and bind the exact public Git projection of MMC.

This is a product-owned application adapter for the filesystem-to-Git boundary.
It prevents a source tree from being called publishable when ignored files,
line-ending conversion, private custody, or generated archives would make the
committed clone differ from the qualified tree.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical
from mosaic_mmc.errors import require
from tools.common import ROOT, regular_files, save_json, source_snapshot


PRIVATE_TRANSCRIPT_SHA256 = "303b30f49ba8c9a1b6b4ea4d922e30fac2d80d341edd4bc8be8bd6efb8812c0a"
FORBIDDEN_PREFIXES = ("baseline/", "evidence/")
FORBIDDEN_SUFFIXES = (".zip", ".whl", ".tar", ".tar.gz", ".pem", ".key", ".p12", ".pfx")


def _git(root: Path, *arguments: str, text: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
                              capture_output=True, text=text, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("MMC_PUBLIC_GIT_COMMAND:" + type(error).__name__) from error


def _links(root: Path) -> list[dict]:
    rows = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for relative, path in regular_files(root):
        if path.suffix.lower() != ".md":
            continue
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            clean = target.split("#", 1)[0]
            if not clean:
                continue
            resolved = (path.parent / clean).resolve()
            require(resolved.is_relative_to(root.resolve()) and resolved.exists(),
                    "MMC_PUBLIC_BROKEN_LINK", relative + ":" + target)
            rows.append({"document": relative, "target": target})
    return rows


def audit_filesystem(root: Path = ROOT) -> dict:
    rows = []
    for relative, path in regular_files(root):
        require(not relative.startswith(FORBIDDEN_PREFIXES), "MMC_PUBLIC_PRIVATE_CUSTODY", relative)
        require(not relative.lower().endswith(FORBIDDEN_SUFFIXES), "MMC_PUBLIC_BINARY_ARTIFACT", relative)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() != PRIVATE_TRANSCRIPT_SHA256,
                "MMC_PUBLIC_PRIVATE_TRANSCRIPT", relative)
        rows.append({"path": relative, "bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    links = _links(root)
    body = {"schema": "mosaic.mmc.public-filesystem-projection.v0.1",
            "files": rows, "links_checked": len(links), "authority_effect": "NONE"}
    return {**body, "root": hashlib.sha256(canonical(body)).hexdigest()}


def audit_git_index(root: Path = ROOT) -> dict:
    require((root / ".git").exists(), "MMC_PUBLIC_GIT_REQUIRED")
    raw = _git(root, "ls-files", "-z").stdout
    tracked = sorted(item.decode("utf-8") for item in raw.split(b"\0") if item)
    actual = sorted(relative for relative, _ in regular_files(root)
                    if not relative.startswith(".git/"))
    require(tracked == actual, "MMC_PUBLIC_GIT_CLOSURE")
    rows = []
    for relative in tracked:
        staged = _git(root, "show", ":" + relative).stdout
        working = (root / relative).read_bytes()
        require(staged == working, "MMC_PUBLIC_GIT_WORKTREE_BYTES", relative)
        rows.append({"path": relative, "bytes": len(staged),
                     "sha256": hashlib.sha256(staged).hexdigest()})
    body = {"schema": "mosaic.mmc.public-git-index.v0.1", "files": rows,
            "git_tree": _git(root, "write-tree", text=True).stdout.strip(),
            "authority_effect": "NONE"}
    return {**body, "root": hashlib.sha256(canonical(body)).hexdigest()}


def write_source_records(root: Path = ROOT) -> dict:
    snapshot = source_snapshot(root)
    save_json(root / "FILE-MANIFEST.json", snapshot)
    save_json(root / "provenance/SOURCE-ADMISSION.json", snapshot)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write-source-records", action="store_true")
    parser.add_argument("--require-git", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write_source_records:
        write_source_records(root)
    filesystem = audit_filesystem(root)
    result = {"schema": "mosaic.mmc.publication-projection-audit.v0.1",
              "status": "PASS_PUBLIC_FILESYSTEM_PROJECTION", "filesystem": filesystem,
              "git": audit_git_index(root) if args.require_git else None,
              "authority_effect": "NONE"}
    result["receipt_root"] = hashlib.sha256(canonical(result)).hexdigest()
    print(canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
