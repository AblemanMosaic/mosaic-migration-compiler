"""MMC adapter for UCM r038 evidence-scope and requalification records.

MMC owns only the application mapping in this module.  Dependency closure,
freshness, dispositions, mutation holds, and release-candidate rules are
computed by the exact UCM implementation supplied to ``run_ucm_builder``.
Nothing here executes a migration, qualifies a release, or grants authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from tools.common import regular_files, source_snapshot


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PROFILE_ID = "MOSAIC.MMC.EVIDENCE_SCOPE"
PROFILE_VERSION = "v0.1"
MAP_ID = "MOSAIC.MMC.CLAIM_DEPENDENCIES"
MAP_VERSION = "v0.1"
ATLAS_RULE = "EVIDENCE_SCOPE_AND_REQUALIFICATION_DISCIPLINE"
ROLES = (
    "RUNTIME_EFFECTS",
    "PROTOCOLS_SCHEMAS",
    "ADAPTERS",
    "TESTS",
    "VALIDATORS",
    "PACKAGING_CI_DOCS",
    "EXTERNAL_DEPENDENCIES",
)
COMPONENTS = {
    "runtime": ("RUNTIME_EFFECTS", ["protocol"]),
    "protocol": ("PROTOCOLS_SCHEMAS", ["external"]),
    "adapter": ("ADAPTERS", ["protocol", "runtime"]),
    "tests": ("TESTS", ["adapter", "runtime"]),
    "validator": ("VALIDATORS", ["protocol"]),
    "packaging": ("PACKAGING_CI_DOCS", ["runtime"]),
    "external": ("EXTERNAL_DEPENDENCIES", []),
}
REQUIRED_EXTERNAL_BINDINGS = {
    "cmba.a4.wheel",
    "cmba.a7.wheel",
    "dependency.lock",
    "dkn.rc5.wheel",
    "semcrys.git.identity",
    "subject.source",
    "pippi.source.manifest",
    "ucm.git.identity",
}

PACKAGING_TOOLS = {
    "tools/package.py",
    "tools_t7/build_backend.py",
    "tools_t7/package.py",
    "tools_t7/public_release.py",
    "tools_t7/publication_projection.py",
}
ADAPTER_SOURCE = {
    "src/mosaic_mmc_product/adapter.py",
    "src/mosaic_mmc_product/adapter_worker.py",
    "src/mosaic_mmc_product/disposable.py",
    "src/mosaic_mmc_product/integrations.py",
    "src/mosaic_mmc_product/sqlite_target.py",
    "src/mosaic_mmc_product/target_qualification.py",
    "src/mosaic_mmc_product/transport.py",
    "src/mosaic_mmc_product/transport_wire.py",
    "src/mosaic_mmc_t4/collectors.py",
    "src/mosaic_mmc_t4/exports.py",
    "src/mosaic_mmc_t4/extensions.py",
    "src/mosaic_mmc_t4/host.py",
    "src/mosaic_mmc_t4/integrations.py",
    "src/mosaic_mmc_t4/sdk.py",
}
VALIDATOR_SOURCE = {
    "src/mosaic_mmc_product/conformance.py",
    "src/mosaic_mmc_product/release_certification.py",
}
TOP_PACKAGING = {
    ".gitattributes", ".gitignore", "AGENTS.md", "CHANGELOG.md",
    "CONTRIBUTING.md", "LICENSE", "LICENSE-STATUS.md", "NOTICE",
    "README.md", "SECURITY.md", "THIRD-PARTY-NOTICES.md", "pyproject.toml",
}
TOP_VALIDATOR = {"FILE-MANIFEST.json", "PINNED-PROGRAM-ROOT.txt"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rooted(value: Any) -> str:
    return sha(canonical(value))


def _root(value: str, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def _external(values: dict[str, str] | None) -> dict[str, str]:
    result = {}
    for key, value in sorted((values or {}).items()):
        require(re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", key) is not None,
                "MMC_EVIDENCE_SCOPE_EXTERNAL_KEY", key)
        result[key] = _root(value, "MMC_EVIDENCE_SCOPE_EXTERNAL_ROOT")
    return result


def component_for(path: str) -> str:
    """Map every admitted MMC source member into one neutral UCM role."""
    if path.startswith(".github/") or path.startswith("docs/") or path in TOP_PACKAGING:
        return "packaging"
    if path in PACKAGING_TOOLS:
        return "packaging"
    if path in TOP_VALIDATOR or path.startswith("provenance/"):
        return "validator"
    if path.startswith(("tests/", "tests_t2/", "tests_t3/", "tests_t4/",
                        "tests_t5/", "tests_t6/", "tests_t7/", "examples/", "study/")):
        return "tests"
    if path.startswith(("tools/", "tools_t2/", "tools_t3/", "tools_t4/",
                        "tools_t5/", "tools_t6/", "tools_t7/")):
        return "validator"
    if path in ADAPTER_SOURCE:
        return "adapter"
    if path in VALIDATOR_SOURCE:
        return "validator"
    if path.startswith(("model/", "schemas/", "interop/", "profiles/", "constitution/")):
        return "protocol"
    if path.startswith("src/"):
        name = Path(path).name
        if "/data/" in path or name in {
                "abi.py", "contracts.py", "model.py", "protocol.py", "schema_graph.py",
                "schemas.py", "statements.py"}:
            return "protocol"
        return "runtime"
    require(False, "MMC_EVIDENCE_SCOPE_UNCLASSIFIED", path)
    raise AssertionError(path)


def build_inventory(root: Path = ROOT, *, external_bindings: dict[str, str] | None = None,
                    atlas_root: str, ucm_source_manifest_root: str) -> dict[str, Any]:
    """Build MMC-owned exact inputs; UCM remains the record authority."""
    root = root.resolve()
    atlas_root = _root(atlas_root, "MMC_EVIDENCE_SCOPE_ATLAS_ROOT")
    ucm_source_manifest_root = _root(
        ucm_source_manifest_root, "MMC_EVIDENCE_SCOPE_UCM_SOURCE_ROOT")
    external = _external(external_bindings)
    grouped: dict[str, list[dict[str, Any]]] = {
        component_id: [] for component_id in COMPONENTS if component_id != "external"}
    coverage = []
    for relative, path in regular_files(root):
        component_id = component_for(relative)
        raw = path.read_bytes()
        row = {"path": relative, "bytes": len(raw), "sha256": sha(raw)}
        grouped[component_id].append(row)
        coverage.append({"path": relative, "component_id": component_id})
    require(coverage and len({row["path"].casefold() for row in coverage}) == len(coverage),
            "MMC_EVIDENCE_SCOPE_COVERAGE")
    mapping_policy = {
        "schema": "mosaic.mmc.evidence-scope-adapter-policy.v0.1",
        "profile_id": PROFILE_ID,
        "atlas_rule": ATLAS_RULE,
        "atlas_root": atlas_root,
        "required_external_binding_ids": sorted(REQUIRED_EXTERNAL_BINDINGS),
        "authority_effect": "NONE",
    }
    policy_root = rooted(mapping_policy)
    components = []
    for component_id in sorted(grouped):
        members = sorted(grouped[component_id], key=lambda row: row["path"])
        role, dependencies = COMPONENTS[component_id]
        state_root = rooted({
            "schema": "mosaic.mmc.evidence-scope-component-state.v0.1",
            "component_id": component_id,
            "role": role,
            "members": members,
        })
        components.append({
            "component_id": component_id,
            "role": role,
            "state_root": state_root,
            "semantic_root": rooted({
                "schema": "mosaic.mmc.evidence-scope-component-semantics.v0.1",
                "component_id": component_id,
                "role": role,
                "mapping_version": PROFILE_VERSION,
            }),
            "governance_root": rooted({
                "schema": "mosaic.mmc.evidence-scope-component-governance.v0.1",
                "component_id": component_id,
                "policy_root": policy_root,
                "authority_effect": "NONE",
            }),
            "environment_root": rooted({
                "schema": "mosaic.mmc.evidence-scope-component-environment.v0.1",
                "component_id": component_id,
                "dependency_lock_root": external.get("dependency.lock"),
                "ucm_builder_source_manifest_root": (
                    ucm_source_manifest_root if component_id == "validator" else None),
            }),
            "depends_on_component_ids": dependencies,
            "closure_coverage": "COMPLETE",
        })
    external_complete = set(external) == REQUIRED_EXTERNAL_BINDINGS
    components.append({
        "component_id": "external",
        "role": "EXTERNAL_DEPENDENCIES",
        "state_root": rooted({
            "schema": "mosaic.mmc.evidence-scope-external-state.v0.1",
            "bindings": external,
            "required_binding_ids": sorted(REQUIRED_EXTERNAL_BINDINGS),
        }),
        "semantic_root": rooted({
            "schema": "mosaic.mmc.evidence-scope-external-semantics.v0.1",
            "binding_ids": sorted(external),
        }),
        "governance_root": rooted({
            "schema": "mosaic.mmc.evidence-scope-external-governance.v0.1",
            "required_binding_ids": sorted(REQUIRED_EXTERNAL_BINDINGS),
            "policy_root": policy_root,
        }),
        "environment_root": rooted({
            "schema": "mosaic.mmc.evidence-scope-external-environment.v0.1",
            "bindings": external,
        }),
        "depends_on_component_ids": [],
        "closure_coverage": "COMPLETE" if external_complete else "INCOMPLETE",
    })
    coverage_body = {
        "schema": "mosaic.mmc.evidence-scope-coverage.v0.1",
        "members": sorted(coverage, key=lambda row: row["path"]),
    }
    return {
        "schema": "mosaic.mmc.evidence-scope-adapter-inventory.v0.1",
        "subject_root": source_snapshot(root)["root"],
        "components": sorted(components, key=lambda row: row["component_id"]),
        "coverage_root": rooted(coverage_body),
        "member_count": len(coverage),
        "external_bindings": external,
        "external_closure": "COMPLETE" if external_complete else "INCOMPLETE",
        "policy": mapping_policy,
        "policy_root": policy_root,
        "authority_effect": "NONE",
    }


def scope_request(inventory: dict[str, Any], *, jurisdiction_root: str) -> dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "subject_root": inventory["subject_root"],
        "jurisdiction_root": _root(jurisdiction_root, "MMC_EVIDENCE_SCOPE_JURISDICTION_ROOT"),
        "policy_root": inventory["policy_root"],
        "components": inventory["components"],
    }


def claim_map_request(profile: dict[str, Any], *,
                      effect_raw_evidence_roots: list[str] | None = None,
                      validator_raw_evidence_roots: list[str] | None = None) -> dict[str, Any]:
    effect_roots = sorted({_root(value, "MMC_EVIDENCE_SCOPE_RAW_EVIDENCE_ROOT")
                           for value in (effect_raw_evidence_roots or [])})
    validator_roots = sorted({_root(value, "MMC_EVIDENCE_SCOPE_RAW_EVIDENCE_ROOT")
                              for value in (validator_raw_evidence_roots or [])})

    def claim(claim_id: str, claim_class: str, component_ids: list[str], *,
              operation_class: str = "PURE", freshness: bool = False,
              raw_roots: list[str] | None = None) -> dict[str, Any]:
        roots = raw_roots or []
        return {
            "claim_id": claim_id,
            "lane_id": f"mmc:{claim_id}:lane",
            "case_id": f"mmc:{claim_id}:case",
            "claim_class": claim_class,
            "component_ids": sorted(set(component_ids + ["validator"])),
            "environment_roots": [profile["environment_commitment_root"]],
            "validator_component_id": "validator",
            "raw_evidence_roots": roots,
            "operation_class": operation_class,
            "raw_evidence_revalidation_allowed": bool(roots),
            "freshness_required": freshness,
            "closure_coverage": "COMPLETE" if profile["closure_complete"] else "INCOMPLETE",
        }

    claims = [
        claim("adapter-conformance", "ADAPTER_CONFORMANCE", ["adapter"]),
        claim("migration-lifecycle", "EFFECT_SAFETY", ["adapter", "runtime"],
              operation_class="MUTATION", freshness=True, raw_roots=effect_roots),
        claim("packaging-custody", "PACKAGING_CUSTODY", ["packaging"]),
        claim("portability", "PORTABILITY", ["packaging", "runtime"],
              operation_class="OBSERVATION", freshness=True),
        claim("protocol-conformance", "PROTOCOL_CONFORMANCE", ["protocol"]),
        claim("release-integrity", "RELEASE_INTEGRITY",
              ["adapter", "external", "packaging", "protocol", "runtime", "tests"]),
        claim("runtime-conformance", "RUNTIME_BEHAVIOR", ["runtime"]),
        claim("test-conformance", "TEST_CONFORMANCE", ["tests"]),
        claim("validator-conformance", "VALIDATOR_CONFORMANCE", ["validator"],
              raw_roots=validator_roots),
    ]
    return {
        "profile": profile,
        "map_id": MAP_ID,
        "map_version": MAP_VERSION,
        "claims": claims,
    }


def impact_request(*, before_profile: dict[str, Any], after_profile: dict[str, Any],
                   claim_map: dict[str, Any], effect_freshness_root: str | None,
                   portability_freshness_root: str | None,
                   release_candidate: bool, candidate_frozen: bool,
                   review_saturation_root: str | None) -> dict[str, Any]:
    freshness = []
    for claim_id, evidence_root in (
            ("migration-lifecycle", effect_freshness_root),
            ("portability", portability_freshness_root)):
        freshness.append({
            "claim_id": claim_id,
            "status": "FRESH" if evidence_root is not None else "UNKNOWN",
            "evidence_root": (_root(evidence_root, "MMC_EVIDENCE_SCOPE_FRESHNESS_ROOT")
                              if evidence_root is not None else None),
        })
    return {
        "before_profile": before_profile,
        "after_profile": after_profile,
        "claim_map": claim_map,
        "current_freshness": freshness,
        "release_candidate": bool(release_candidate),
        "candidate_frozen": bool(candidate_frozen),
        "review_saturation_root": review_saturation_root,
    }


def verify_ucm_source(ucm_source: Path, *, expected_source_manifest_root: str,
                      expected_atlas_root: str) -> None:
    """Bind the executed UCM CLI to its exact declared source and atlas."""
    source = ucm_source.resolve()
    source_root = _root(expected_source_manifest_root,
                        "MMC_EVIDENCE_SCOPE_UCM_SOURCE_ROOT")
    atlas_root = _root(expected_atlas_root, "MMC_EVIDENCE_SCOPE_ATLAS_ROOT")
    manifest_path = source / "release/SOURCE-MANIFEST.json"
    atlas_path = source / "spec/PIPPI-CONSTITUTIONAL-STANDARDS-ATLAS.json"
    require(manifest_path.is_file() and atlas_path.is_file(),
            "MMC_EVIDENCE_SCOPE_UCM_IDENTITY_MISSING")
    manifest = decode(manifest_path.read_bytes(), limit=8 * 1024 * 1024)
    body = {key: value for key, value in manifest.items() if key != "root"}
    require(manifest.get("root") == source_root == rooted(body),
            "MMC_EVIDENCE_SCOPE_UCM_SOURCE_MISMATCH")
    require(manifest.get("member_count") == len(manifest.get("members", [])),
            "MMC_EVIDENCE_SCOPE_UCM_DENOMINATOR_MISMATCH")
    admitted_paths = set()
    for row in manifest["members"]:
        relative = row.get("path")
        require(isinstance(relative, str) and relative and "\\" not in relative
                and ":" not in relative and not relative.startswith("/")
                and ".." not in Path(relative).parts,
                "MMC_EVIDENCE_SCOPE_UCM_MEMBER_PATH")
        path = source / relative
        require(path.is_file() and path.stat().st_size == row.get("bytes")
                and sha(path.read_bytes()) == row.get("sha256"),
                "MMC_EVIDENCE_SCOPE_UCM_MEMBER_MISMATCH", relative)
        require(relative.casefold() not in admitted_paths,
                "MMC_EVIDENCE_SCOPE_UCM_MEMBER_ALIAS", relative)
        admitted_paths.add(relative.casefold())
    for relative, _ in regular_files(source / "src"):
        require(("src/" + relative).casefold() in admitted_paths,
                "MMC_EVIDENCE_SCOPE_UCM_EXECUTABLE_EXTRA", relative)
    atlas = decode(atlas_path.read_bytes(), limit=2 * 1024 * 1024)
    atlas_body = {key: value for key, value in atlas.items() if key != "atlas_root"}
    require(atlas.get("atlas_root") == atlas_root == rooted(atlas_body),
            "MMC_EVIDENCE_SCOPE_ATLAS_MISMATCH")
    require(ATLAS_RULE in {row.get("rule_id") for row in atlas.get("rules", [])},
            "MMC_EVIDENCE_SCOPE_RULE_MISSING")


def run_ucm_builder(*, ucm_source: Path, operation: str, request: dict[str, Any],
                    output: Path, expected_ucm_source_manifest_root: str,
                    expected_atlas_root: str) -> dict[str, Any]:
    """Invoke the exact UCM CLI; do not reproduce its decision engine."""
    require(operation in {"scope-profile", "claim-map", "impact"},
            "MMC_EVIDENCE_SCOPE_UCM_OPERATION")
    source = ucm_source.resolve()
    verify_ucm_source(
        source, expected_source_manifest_root=expected_ucm_source_manifest_root,
        expected_atlas_root=expected_atlas_root)
    require(not output.exists(), "MMC_EVIDENCE_SCOPE_OUTPUT_EXISTS")
    require(not output.resolve().is_relative_to(source)
            and not output.resolve().is_relative_to(ROOT),
            "MMC_EVIDENCE_SCOPE_OUTPUT_INSIDE_SOURCE")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mmc-ucm-request-", dir=output.parent) as temporary:
        request_path = Path(temporary) / "request.json"
        request_path.write_bytes(canonical(request) + b"\n")
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PATHEXT": os.environ.get("PATHEXT", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(source / "src"),
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "ucm.cli", "qualification-build",
                 operation, str(request_path), str(output)],
                cwd=str(source), env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            require(False, "MMC_EVIDENCE_SCOPE_UCM_TIMEOUT", operation)
        require(completed.returncode == 0, "MMC_EVIDENCE_SCOPE_UCM_REFUSED",
                completed.stderr.decode("utf-8", errors="replace")[:2000])
    verify_ucm_source(
        source, expected_source_manifest_root=expected_ucm_source_manifest_root,
        expected_atlas_root=expected_atlas_root)
    return decode(output.read_bytes(), limit=16 * 1024 * 1024)


def _bindings(rows: list[str]) -> dict[str, str]:
    result = {}
    for row in rows:
        key, separator, value = row.partition("=")
        require(separator == "=" and key not in result,
                "MMC_EVIDENCE_SCOPE_EXTERNAL_ARGUMENT", row)
        result[key] = value
    return _external(result)


def _load(path: Path) -> dict[str, Any]:
    return decode(path.read_bytes(), limit=16 * 1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    profile = sub.add_parser("profile")
    profile.add_argument("--root", type=Path, default=ROOT)
    profile.add_argument("--ucm-source", type=Path, required=True)
    profile.add_argument("--ucm-source-manifest-root", required=True)
    profile.add_argument("--atlas-root", required=True)
    profile.add_argument("--jurisdiction-root", required=True)
    profile.add_argument("--external", action="append", default=[])
    profile.add_argument("--inventory-out", type=Path)
    profile.add_argument("--out", type=Path, required=True)
    mapping = sub.add_parser("claim-map")
    mapping.add_argument("--profile", type=Path, required=True)
    mapping.add_argument("--ucm-source", type=Path, required=True)
    mapping.add_argument("--ucm-source-manifest-root", required=True)
    mapping.add_argument("--atlas-root", required=True)
    mapping.add_argument("--effect-evidence-root", action="append", default=[])
    mapping.add_argument("--validator-evidence-root", action="append", default=[])
    mapping.add_argument("--out", type=Path, required=True)
    impact = sub.add_parser("impact")
    impact.add_argument("--before-profile", type=Path, required=True)
    impact.add_argument("--after-profile", type=Path, required=True)
    impact.add_argument("--claim-map", type=Path, required=True)
    impact.add_argument("--ucm-source", type=Path, required=True)
    impact.add_argument("--ucm-source-manifest-root", required=True)
    impact.add_argument("--atlas-root", required=True)
    impact.add_argument("--effect-freshness-root")
    impact.add_argument("--portability-freshness-root")
    impact.add_argument("--release-candidate", action="store_true")
    impact.add_argument("--candidate-frozen", action="store_true")
    impact.add_argument("--review-saturation-root")
    impact.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "profile":
        inventory = build_inventory(
            args.root, external_bindings=_bindings(args.external),
            atlas_root=args.atlas_root,
            ucm_source_manifest_root=args.ucm_source_manifest_root)
        if args.inventory_out is not None:
            require(not args.inventory_out.exists(), "MMC_EVIDENCE_SCOPE_OUTPUT_EXISTS")
            require(not args.inventory_out.resolve().is_relative_to(args.root.resolve())
                    and not args.inventory_out.resolve().is_relative_to(args.ucm_source.resolve()),
                    "MMC_EVIDENCE_SCOPE_OUTPUT_INSIDE_SOURCE")
            args.inventory_out.parent.mkdir(parents=True, exist_ok=True)
            args.inventory_out.write_bytes(canonical(inventory) + b"\n")
        result = run_ucm_builder(
            ucm_source=args.ucm_source, operation="scope-profile",
            request=scope_request(inventory, jurisdiction_root=args.jurisdiction_root),
            output=args.out,
            expected_ucm_source_manifest_root=args.ucm_source_manifest_root,
            expected_atlas_root=args.atlas_root)
    elif args.operation == "claim-map":
        result = run_ucm_builder(
            ucm_source=args.ucm_source, operation="claim-map",
            request=claim_map_request(
                _load(args.profile), effect_raw_evidence_roots=args.effect_evidence_root,
                validator_raw_evidence_roots=args.validator_evidence_root),
            output=args.out,
            expected_ucm_source_manifest_root=args.ucm_source_manifest_root,
            expected_atlas_root=args.atlas_root)
    else:
        result = run_ucm_builder(
            ucm_source=args.ucm_source, operation="impact",
            request=impact_request(
                before_profile=_load(args.before_profile),
                after_profile=_load(args.after_profile),
                claim_map=_load(args.claim_map),
                effect_freshness_root=args.effect_freshness_root,
                portability_freshness_root=args.portability_freshness_root,
                release_candidate=args.release_candidate,
                candidate_frozen=args.candidate_frozen,
                review_saturation_root=args.review_saturation_root),
            output=args.out,
            expected_ucm_source_manifest_root=args.ucm_source_manifest_root,
            expected_atlas_root=args.atlas_root)
    print(canonical(result).decode("utf-8"))
    return 0


__all__ = [
    "ATLAS_RULE", "REQUIRED_EXTERNAL_BINDINGS", "build_inventory", "scope_request",
    "claim_map_request", "impact_request", "run_ucm_builder", "verify_ucm_source",
]


if __name__ == "__main__":
    raise SystemExit(main())
