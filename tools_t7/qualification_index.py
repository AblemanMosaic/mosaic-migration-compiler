"""Legacy component inventory retained for release-record compatibility.

This module no longer decides evidence reuse.  The r013 application adapter in
``tools_t7.evidence_scope_adapter`` maps MMC into UCM r038, whose
``EVALUATE_REQUALIFICATION_IMPACT`` surface owns closure, freshness, and typed
dispositions.  The comparison entry point remains only to fail closed for old
automation.  Unknown files and ambiguous inputs still refuse.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from tools.common import regular_files, source_snapshot


SCHEMA = "mosaic.mmc.qualification-index.v0.1"
REUSE_SCHEMA = "mosaic.mmc.evidence-reuse-assessment.v0.1"
COMPONENTS = (
    "runtime",
    "fixtures",
    "qualification",
    "packaging",
    "documentation",
    "provenance",
    "ci",
    "source_projection",
)
EVIDENCE_POLICIES = {
    "runtime-conformance": ("runtime", "fixtures", "qualification", "provenance"),
    "migration-lifecycle": ("runtime", "fixtures", "qualification", "provenance"),
    "installed-runtime": ("runtime", "packaging", "qualification", "provenance"),
    "ci-rehearsal": ("runtime", "qualification", "packaging", "ci", "source_projection"),
    "documentation-audit": ("documentation",),
    "release-envelope": tuple(COMPONENTS),
    "full-qualification": tuple(COMPONENTS),
}
PACKAGING_TOOLS = {
    "tools/package.py",
    "tools_t7/build_backend.py",
    "tools_t7/package.py",
    "tools_t7/public_release.py",
    "tools_t7/publication_projection.py",
}
TOP_DOCUMENTS = {
    "AGENTS.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE-STATUS.md",
    "README.md", "SECURITY.md",
}
TOP_PACKAGING = {"LICENSE", "NOTICE", "THIRD-PARTY-NOTICES.md", "pyproject.toml"}
TOP_PROVENANCE = {"FILE-MANIFEST.json", "PINNED-PROGRAM-ROOT.txt"}
TOP_PROJECTION = {".gitattributes", ".gitignore"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rooted(body: dict) -> dict:
    return {**body, "root": sha(canonical(body))}


def component_for(path: str) -> str:
    if path.startswith(".github/"):
        return "ci"
    if path in TOP_PROJECTION:
        return "source_projection"
    if path in TOP_PACKAGING or path in PACKAGING_TOOLS:
        return "packaging"
    if path in TOP_DOCUMENTS or path.startswith("docs/"):
        return "documentation"
    if path in TOP_PROVENANCE or path.startswith("provenance/"):
        return "provenance"
    if path.startswith(("src/", "model/", "schemas/", "interop/", "constitution/", "profiles/")):
        return "runtime"
    if path.startswith(("examples/", "study/")):
        return "fixtures"
    if path.startswith(("tests/", "tests_t2/", "tests_t3/", "tests_t4/",
                        "tests_t5/", "tests_t6/", "tests_t7/")):
        return "qualification"
    if path.startswith(("tools/", "tools_t2/", "tools_t3/", "tools_t4/",
                        "tools_t5/", "tools_t6/", "tools_t7/")):
        return "qualification"
    require(False, "MMC_QUALIFICATION_INDEX_UNCLASSIFIED", path)
    raise AssertionError(path)


def _external(values: dict[str, str] | None) -> dict[str, str]:
    result = {}
    for key, value in sorted((values or {}).items()):
        require(re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", key) is not None,
                "MMC_QUALIFICATION_EXTERNAL_KEY", key)
        require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                "MMC_QUALIFICATION_EXTERNAL_ROOT", key)
        result[key] = value
    return result


def build_index(root: Path = ROOT, *, external_bindings: dict[str, str] | None = None) -> dict:
    root = root.resolve()
    grouped: dict[str, list[dict]] = {name: [] for name in COMPONENTS}
    coverage = []
    for relative, path in regular_files(root):
        component = component_for(relative)
        raw = path.read_bytes()
        row = {"path": relative, "bytes": len(raw), "sha256": sha(raw)}
        grouped[component].append(row)
        coverage.append({"path": relative, "component": component})
    require(coverage and len({row["path"].casefold() for row in coverage}) == len(coverage),
            "MMC_QUALIFICATION_INDEX_COVERAGE")
    components = {}
    for name in COMPONENTS:
        members = sorted(grouped[name], key=lambda row: row["path"])
        record = rooted({
            "schema": "mosaic.mmc.qualification-component.v0.1",
            "component": name,
            "members": members,
            "member_count": len(members),
            "logical_bytes": sum(row["bytes"] for row in members),
            "authority_effect": "NONE",
        })
        components[name] = {
            "root": record["root"],
            "member_count": record["member_count"],
            "logical_bytes": record["logical_bytes"],
        }
    coverage_body = {
        "schema": "mosaic.mmc.qualification-coverage.v0.1",
        "members": sorted(coverage, key=lambda row: row["path"]),
    }
    body = {
        "schema": SCHEMA,
        "classification": "MMC_APPLICATION_ADAPTER_V1",
        "source_root": source_snapshot(root)["root"],
        "components": components,
        "coverage_root": sha(canonical(coverage_body)),
        "member_count": len(coverage),
        "external_bindings": _external(external_bindings),
        "evidence_policies": {key: list(value) for key, value in EVIDENCE_POLICIES.items()},
        "reuse_semantics": "ONLY_EXACT_RELEVANT_COMPONENT_AND_EXTERNAL_ROOT_EQUALITY",
        "authority_effect": "NONE",
    }
    return rooted(body)


def verify_index(value: dict) -> dict:
    require(isinstance(value, dict) and value.get("schema") == SCHEMA,
            "MMC_QUALIFICATION_INDEX_SCHEMA")
    body = {key: row for key, row in value.items() if key != "root"}
    require(value.get("root") == sha(canonical(body)), "MMC_QUALIFICATION_INDEX_ROOT")
    require(set(value.get("components", {})) == set(COMPONENTS),
            "MMC_QUALIFICATION_INDEX_COMPONENTS")
    for name, row in value["components"].items():
        require(set(row) == {"root", "member_count", "logical_bytes"}
                and re.fullmatch(r"[0-9a-f]{64}", row["root"]) is not None
                and isinstance(row["member_count"], int) and row["member_count"] >= 0
                and isinstance(row["logical_bytes"], int) and row["logical_bytes"] >= 0,
                "MMC_QUALIFICATION_INDEX_COMPONENT", name)
    require(value.get("evidence_policies") ==
            {key: list(row) for key, row in EVIDENCE_POLICIES.items()},
            "MMC_QUALIFICATION_INDEX_POLICIES")
    _external(value.get("external_bindings"))
    require(isinstance(value.get("source_root"), str)
            and re.fullmatch(r"[0-9a-f]{64}", value["source_root"]),
            "MMC_QUALIFICATION_INDEX_SOURCE")
    require(isinstance(value.get("coverage_root"), str)
            and re.fullmatch(r"[0-9a-f]{64}", value["coverage_root"])
            and isinstance(value.get("member_count"), int) and value["member_count"] > 0,
            "MMC_QUALIFICATION_INDEX_COVERAGE")
    return value


def summary(index: dict) -> dict:
    verify_index(index)
    return {
        "schema": index["schema"],
        "root": index["root"],
        "source_root": index["source_root"],
        "components": index["components"],
        "coverage_root": index["coverage_root"],
        "member_count": index["member_count"],
        "external_bindings": index["external_bindings"],
        "authority_effect": "NONE",
    }


def assess_reuse(before: dict, after: dict, evidence_class: str,
                 prior_receipt_root: str) -> dict:
    verify_index(before)
    verify_index(after)
    require(evidence_class in EVIDENCE_POLICIES, "MMC_EVIDENCE_REUSE_CLASS")
    require(re.fullmatch(r"[0-9a-f]{64}", prior_receipt_root or "") is not None,
            "MMC_EVIDENCE_REUSE_RECEIPT_ROOT")
    relevant = EVIDENCE_POLICIES[evidence_class]
    changed = sorted(name for name in COMPONENTS
                     if before["components"][name]["root"] != after["components"][name]["root"])
    relevant_changed = sorted(set(changed) & set(relevant))
    external_equal = before["external_bindings"] == after["external_bindings"]
    body = {
        "schema": REUSE_SCHEMA,
        "status": "REUSE_REFUSED_UCM_REQUALIFICATION_IMPACT_REQUIRED",
        "evidence_class": evidence_class,
        "prior_receipt_root": prior_receipt_root,
        "before_index_root": before["root"],
        "after_index_root": after["root"],
        "relevant_components": list(relevant),
        "changed_components": changed,
        "relevant_changed_components": relevant_changed,
        "external_bindings_equal": external_equal,
        "claim": "LEGACY_INDEX_IS_NOT_AN_EVIDENCE_REUSE_DECISION",
        "authority_effect": "NONE",
    }
    return rooted(body)


def require_reuse(before: dict, after: dict, evidence_class: str,
                  prior_receipt_root: str) -> dict:
    result = assess_reuse(before, after, evidence_class, prior_receipt_root)
    require(False, "MMC_EVIDENCE_REUSE_REQUIRES_UCM_IMPACT",
            ",".join(result["relevant_changed_components"]))
    return result


def _bindings(rows: list[str]) -> dict[str, str]:
    values = {}
    for row in rows:
        key, separator, value = row.partition("=")
        require(separator == "=", "MMC_QUALIFICATION_EXTERNAL_ARGUMENT", row)
        require(key not in values, "MMC_QUALIFICATION_EXTERNAL_DUPLICATE", key)
        values[key] = value
    return _external(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    build = sub.add_parser("build")
    build.add_argument("--root", type=Path, default=ROOT)
    build.add_argument("--external", action="append", default=[])
    build.add_argument("--out", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--before", type=Path, required=True)
    compare.add_argument("--after", type=Path, required=True)
    compare.add_argument("--evidence-class", choices=sorted(EVIDENCE_POLICIES), required=True)
    compare.add_argument("--prior-receipt-root", required=True)
    compare.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.operation == "build":
        result = build_index(args.root, external_bindings=_bindings(args.external))
    else:
        result = assess_reuse(decode(args.before.read_bytes(), limit=8 * 1024 * 1024),
                              decode(args.after.read_bytes(), limit=8 * 1024 * 1024),
                              args.evidence_class, args.prior_receipt_root)
    raw = canonical(result) + b"\n"
    if args.out is not None:
        require(not args.out.exists(), "MMC_QUALIFICATION_INDEX_OUTPUT_EXISTS")
        args.out.write_bytes(raw)
    print(raw.decode("utf-8"), end="")
    return 0 if args.operation == "build" else 2


if __name__ == "__main__":
    raise SystemExit(main())
