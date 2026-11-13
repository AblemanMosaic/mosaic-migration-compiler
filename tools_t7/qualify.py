"""Release Convergence qualification with exact outcomes and bounded exception admission."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical
from mosaic_mmc.errors import require
from mosaic_mmc_product import capabilities, integration_status
from mosaic_mmc_product.disposable import run_disposable_migration
from mosaic_mmc_product.target_qualification import run_target_qualification
from mosaic_mmc_product.integrations import probe_cmba_agent, probe_semcrys, probe_ucm
from tools.common import source_snapshot
from tools.qualify import flattened
from tools.check_vectors import check as check_t1
from tools_t2.check_vectors import check as check_t2
from tools_t3.check_vectors import check as check_t3
from tools_t4.check_vectors import check as check_t4
from tools_t5.check_vectors import check as check_t5
from tools_t7.qualification_index import build_index as build_qualification_index, summary as qualification_summary
from tools_t7.evidence_scope_adapter import (
    build_inventory as build_evidence_scope_inventory,
    claim_map_request,
    run_ucm_builder,
    scope_request,
    verify_ucm_source,
)
from tools_t7.test_system import groups as canonical_groups, validate_discovery_profile


GROUPS = canonical_groups()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rooted(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _ucm_constitution(ucm_source: Path) -> tuple[str, str]:
    """Verify the exact declared UCM source denominator and pin its atlas."""
    manifest_path = ucm_source / "release/SOURCE-MANIFEST.json"
    atlas_path = ucm_source / "spec/PIPPI-CONSTITUTIONAL-STANDARDS-ATLAS.json"
    require(manifest_path.is_file() and atlas_path.is_file(),
            "MMC_T7_UCM_REQUALIFICATION_SURFACE_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
    verify_ucm_source(
        ucm_source, expected_source_manifest_root=manifest.get("root"),
        expected_atlas_root=atlas.get("atlas_root"))
    return manifest["root"], atlas["atlas_root"]


def _source(expected: str) -> dict:
    actual = source_snapshot(ROOT)
    require(actual["root"] == expected, "MMC_T7_SOURCE_PIN_MISMATCH")
    return actual


WINDOWS_HOST_LIMITATION_IDS = {
    "tests.test_boundaries.IOBoundaryTests.test_fifo_refused_before_block",
    "tests.test_boundaries.IOBoundaryTests.test_symlink_parent_refused",
    "tests.test_boundaries.IOBoundaryTests.test_symlink_refused",
    "tests.test_boundaries.QualificationBoundaryTests.test_source_builder_rejects_link",
    "tests_t3.test_faults.FaultTests.test_file_symlink_refused",
    "tests_t3.test_review.ReviewTests.test_cli_symlink",
    "tests_t4.test_collectors.CollectorTests.test_fifo_refused",
    "tests_t4.test_collectors.CollectorTests.test_symlink_refused",
    "tests_t4.test_collectors.HTTPTests.test_actual_loopback_get",
    "tests_t4.test_collectors.HTTPTests.test_ambient_proxy_disabled",
    "tests_t4.test_exports.ExportTests.test_directory_symlink_refused",
    "tests_t4.test_exports.ExportTests.test_display_plan_mutation_cannot_change_bytes",
    "tests_t4.test_exports.ExportTests.test_one_use_host_token",
    "tests_t4.test_exports.ExportTests.test_postcommit_readback_uncertainty",
    "tests_t4.test_native_gui.GUIQualificationTests.test_actual_tk_interaction",
    "tests_t7.test_native_aliases.NativeAliasTests.test_collector_parent_alias_refused",
    "tests_t7.test_native_aliases.NativeAliasTests.test_export_directory_alias_refused",
    "tests_t7.test_native_aliases.NativeAliasTests.test_input_parent_alias_refused",
    "tests_t7.test_native_aliases.NativeAliasTests.test_source_builder_alias_refused",
    "tests_t7.test_native_aliases.NativeAliasTests.test_store_parent_alias_refused",
    "tests_t7.test_native_aliases.NativeAliasTests.test_t3_cli_parent_alias_refused",
    "tests_t7.test_native_aliases.NativeAliasTests.test_worker_implementation_alias_refused",
}


def _host_limitation(test_id: str, detail: str, status: str, *, host_system: str | None = None) -> bool:
    host_system = platform.system() if host_system is None else host_system
    if test_id not in WINDOWS_HOST_LIMITATION_IDS:
        return False
    if host_system == "Windows" and status == "ERROR" and "WinError 1314" in detail:
        return "symlink" in test_id.lower() or "link" in test_id.lower()
    if host_system == "Windows" and status == "SKIP":
        return ("fifo" in test_id.lower() and "posix" in detail.lower()) or (
            test_id == "tests_t4.test_native_gui.GUIQualificationTests.test_actual_tk_interaction"
            and detail == "HOST_FIXTURE_HARDLINK_DENIED:5")
    if host_system == "Windows" and status == "ERROR":
        if "PermissionError: [WinError 5] Access is denied" in detail and "test_native_aliases" in test_id:
            return True
        if "module 'os' has no attribute 'mkfifo'" in detail:
            return True
        if "WinError 10013" in detail and test_id.startswith("tests_t4.test_collectors.HTTPTests"):
            return True
        if ("PermissionError: [WinError 5]" in detail and "os.link(temporary,final)" in detail
                and "MMC_T4_EXPORT_INSTALL_UNSUPPORTED" in detail
                and test_id.startswith("tests_t4.test_exports")):
            return True
    return False


SUCCESSOR_SUPERSEDED_ASSERTIONS = {
    "tests_t2.test_integration.IntegrationTests.test_t1_runtime_exact_preservation": "MMC_T2_PREDECESSOR_CHANGED at constitution/AMENDMENT-POLICY.md:",
    "tests_t3.test_qualification.QualificationTests.test_predecessor_runtime_preserved": "MMC_T3_PREDECESSOR_CHANGED at constitution/AMENDMENT-POLICY.md:",
    "tests_t4.test_release.ReleaseTests.test_original_runtime_exact": "MMC_T4_PREDECESSOR_CHANGED at constitution/AMENDMENT-POLICY.md:",
    "tests_t5.test_qualification.QualificationTests.test_all_predecessor_runtime_semantics_exact": "MMC_T5_PREDECESSOR_CHANGED at constitution/AMENDMENT-POLICY.md:",
    "tests_t6.test_release.ReleaseTests.test_runtime_preserved": "MMC_T6_PREDECESSOR_CHANGED at constitution/AMENDMENT-POLICY.md:",
}

SUCCESSOR_SUPERSEDED_FAILURES = {
    "tests_t2.test_integration.IntegrationTests.test_t1_compilation_exact_against_predecessor": (
        "c521579584b4f6c7a53146c9e6006e65654ec09f69671ecaf7f4895de157598b",
        "b8387cf06a06e26b290b8c3827c644068defd4ce8484167de98186d87452ee64",
    ),
}


def _superseded(test_id: str, detail: str, status: str) -> bool:
    expected = SUCCESSOR_SUPERSEDED_ASSERTIONS.get(test_id)
    if (status == "ERROR" and expected is not None
            and detail.rstrip().endswith("mosaic_mmc.errors.MMCError: " + expected)):
        return True
    identities = SUCCESSOR_SUPERSEDED_FAILURES.get(test_id)
    if status != "FAIL" or identities is None:
        return False
    actual, predecessor = identities
    return (f"AssertionError: '{actual}' != '{predecessor}'" in detail
            and detail.rstrip().endswith("+ " + predecessor))


def _outcomes(ids: list[str], result: unittest.TestResult) -> tuple[dict, dict]:
    status = {identifier: "PASS" for identifier in ids}
    detail = {}
    for kind, rows in (("FAIL", result.failures), ("ERROR", result.errors),
                       ("SKIP", result.skipped), ("EXPECTED_FAILURE", result.expectedFailures),
                       ("UNEXPECTED_SUCCESS", [(case, "Unexpected success") for case in result.unexpectedSuccesses])):
        for case, trace in rows:
            # unittest reports a subtest object; its parent is the admitted test.
            identifier = getattr(case, "test_case", case).id()
            require(identifier in status, "MMC_T7_UNADMITTED_TEST_RESULT", identifier)
            priority = {"PASS": 0, "SKIP": 1, "EXPECTED_FAILURE": 2,
                        "UNEXPECTED_SUCCESS": 3, "FAIL": 4, "ERROR": 5}
            if priority[kind] > priority[status[identifier]]:
                status[identifier] = kind
            detail[identifier] = detail.get(identifier, "") + trace
    require(result.testsRun == len(ids) and bool(ids), "MMC_T7_TEST_EXECUTION_COUNT")
    return status, detail


def run_group(name: str, directory: str, evidence: Path) -> dict:
    suite = unittest.defaultTestLoader.discover(str(ROOT / directory), top_level_dir=str(ROOT))
    ids = [case.id() for case in flattened(suite)]
    require(len(ids) == len(set(ids)), "MMC_T7_DUPLICATE_TEST_ID", name)
    admitted = json.loads((ROOT / "provenance/turn7/TEST-REGISTRY.json").read_text(encoding="utf-8"))
    require(sorted(ids) == admitted["groups"][name], "MMC_T7_TEST_REGISTRY_DRIFT", name)
    stream = io.StringIO()
    started = time.perf_counter_ns()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter_ns() - started
    status, detail = _outcomes(ids, result)
    limitations = [identifier for identifier in ids
                   if status[identifier] != "PASS"
                   and _host_limitation(identifier, detail[identifier], status[identifier])]
    superseded = [identifier for identifier in ids
                  if _superseded(identifier, detail.get(identifier, ""), status[identifier])]
    unexpected = [identifier for identifier in ids
                  if status[identifier] != "PASS"
                  and identifier not in limitations and identifier not in superseded]
    log_path = evidence / f"{name}-tests.txt"
    log_path.write_text(stream.getvalue(), encoding="utf-8")
    record = {
        "schema": "mmc.test-group.t7", "group": name, "test_ids": ids,
        "test_outcomes": status,
        "test_details": detail,
        "counts": {kind: sum(value == kind for value in status.values())
                   for kind in ("PASS", "FAIL", "ERROR", "SKIP", "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS")},
        "host_limitations": limitations, "successor_superseded_assertions": superseded,
        "unexpected": unexpected,
        "elapsed_ns": elapsed, "log": {"path": log_path.name, "bytes": log_path.stat().st_size,
                                          "sha256": sha(log_path)},
    }
    (evidence / f"{name}-tests.json").write_bytes(canonical(record))
    if unexpected:
        raise RuntimeError("MMC_T7_TEST_GROUP_FAILED:" + name + ":" + ",".join(unexpected))
    return record


def qualify(ucm_source: Path, pippi_source: Path, semcrys_source: Path, subject: Path,
            cmba_a4_wheel: Path, cmba_a7_wheel: Path, dkn_rc5_wheel: Path,
            dependency_bundle: Path, dependency_lock_root: str,
            expected_source: str, evidence: Path) -> dict:
    started = time.perf_counter_ns()
    evidence.mkdir(parents=True, exist_ok=True)
    runtime_temp = evidence / "runtime-temp"
    runtime_temp.mkdir(parents=True, exist_ok=True)
    os.environ["MMC_DISPOSABLE_TEMP_ROOT"] = str(runtime_temp)
    for variable in ("TEMP", "TMP", "TMPDIR"):
        os.environ[variable] = str(runtime_temp)
    os.environ.update({
        "MMC_QUALIFICATION_CMBA_A4_WHEEL": str(cmba_a4_wheel.absolute()),
        "MMC_QUALIFICATION_CMBA_A7_WHEEL": str(cmba_a7_wheel.absolute()),
        "MMC_QUALIFICATION_DKN_RC5_WHEEL": str(dkn_rc5_wheel.absolute()),
        "MMC_QUALIFICATION_DEPENDENCY_BUNDLE": str(dependency_bundle.absolute()),
        "MMC_QUALIFICATION_DEPENDENCY_LOCK_ROOT": dependency_lock_root,
        "MMC_UCM_R038_SOURCE": str(pippi_source.absolute()),
    })
    test_profile = validate_discovery_profile()
    pippi_source_manifest_root, pippi_atlas_root = _ucm_constitution(pippi_source)
    before = _source(expected_source)
    tests = {}
    for name, directory in GROUPS.items():
        tests[name] = run_group(name, directory, evidence)
        _source(expected_source)

    cmba_path = cmba_a7_wheel
    checkpoints = []
    def bound_call(name, function):
        _source(expected_source)
        result = function()
        _source(expected_source)
        checkpoints.append(name)
        return result
    from tools_t7.preservation import check_preservation
    executed = {identifier: status for group in tests.values()
                for identifier, status in group["test_outcomes"].items()}
    preservation = bound_call("successor-preservation", lambda: check_preservation(executed=executed))
    cmba = bound_call("cmba", lambda: probe_cmba_agent(cmba_path))
    ucm = bound_call("ucm", lambda: probe_ucm(ucm_source, ROOT / "interop/ucm/MMC-AMCAS-CONTRACT.json"))
    semcrys = bound_call("semcrys", lambda: probe_semcrys(semcrys_source))
    vectors = {
        "t1": len(check_t1()["cases"]), "t2": len(check_t2()["cases"]),
        "t3": len(check_t3()["cases"]), "t4": len(check_t4()["cases"]),
        "t5": len(check_t5()["cases"]),
    }
    disposable = bound_call("disposable", run_disposable_migration)
    (evidence / "DISPOSABLE-MIGRATION.json").write_bytes(canonical(disposable))
    target = bound_call("authenticated-sqlite-target", run_target_qualification)
    (evidence / "TARGET-MIGRATION.json").write_bytes(canonical(target))
    _source(expected_source)

    # Import the exact pinned UCM implementation only for the executed Stage-I1 run.
    sys.path.insert(0, str(ucm_source / "src"))
    from tools_t7.build_stage1 import build as build_stage1
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    stage = bound_call("stage-i1", lambda: build_stage1(
        load(ROOT / "interop/ucm/SUBJECT-BINDING.json"),
        load(ROOT / "interop/ucm/MMC-AMCAS-CONTRACT.json"),
        load(ROOT / "interop/ucm/CONTROL-PLANE-DISPOSITION.json"),
        subject=subject, ucm_source=ucm_source, cmba_wheel=cmba_path,
        semcrys_source=semcrys_source,
    ))
    stage_path = evidence / "MMC-APPLICATION-STAGE-I1.zip"
    stage_path.write_bytes(stage)
    _source(expected_source)

    predecessor = json.loads((ROOT / "provenance/turn7/PREDECESSOR.json").read_text(encoding="utf-8"))
    require(sha(ROOT / "provenance/turn7/PREDECESSOR-T2-KNOWN-ANSWERS.json") ==
            predecessor["predecessor_t2_vectors_sha256"], "MMC_T7_PREDECESSOR_T2_DRIFT")
    require(sha(ROOT / "provenance/turn7/PREDECESSOR-T3-KNOWN-ANSWERS.json") ==
            predecessor["predecessor_t3_vectors_sha256"], "MMC_T7_PREDECESSOR_T3_DRIFT")
    after = _source(expected_source)
    require(before == after, "MMC_T7_SOURCE_CHANGED_DURING_QUALIFICATION")
    external_bindings = {
        "dependency.lock": dependency_lock_root,
        "cmba.a4.wheel": sha(cmba_a4_wheel),
        "cmba.a7.wheel": sha(cmba_a7_wheel),
        "dkn.rc5.wheel": sha(dkn_rc5_wheel),
        "ucm.git.identity": hashlib.sha256(canonical({
            "commit": ucm["git_commit"], "tree": ucm["git_tree"]})).hexdigest(),
        "pippi.source.manifest": pippi_source_manifest_root,
        "semcrys.git.identity": hashlib.sha256(canonical({
            "commit": semcrys["git_commit"], "tree": semcrys["git_tree"]})).hexdigest(),
        "subject.source": source_snapshot(subject)["root"],
    }
    component_index = build_qualification_index(
        ROOT, external_bindings=external_bindings)
    component_path = evidence / "QUALIFICATION-INDEX.json"
    component_path.write_bytes(canonical(component_index) + b"\n")
    component_summary = {
        **qualification_summary(component_index),
        "path": component_path.name,
        "bytes": component_path.stat().st_size,
        "sha256": sha(component_path),
    }
    jurisdiction_root = rooted({
        "schema": "mosaic.mmc.qualification-jurisdiction.v0.1",
        "status": "UNBOUND",
        "authority_effect": "NONE",
    })
    scope_inventory = build_evidence_scope_inventory(
        ROOT, external_bindings=external_bindings, atlas_root=pippi_atlas_root,
        ucm_source_manifest_root=pippi_source_manifest_root)
    inventory_path = evidence / "MMC-EVIDENCE-SCOPE-INVENTORY.json"
    inventory_path.write_bytes(canonical(scope_inventory) + b"\n")
    scope_profile = run_ucm_builder(
        ucm_source=pippi_source, operation="scope-profile",
        request=scope_request(scope_inventory, jurisdiction_root=jurisdiction_root),
        output=evidence / "MMC-EVIDENCE-SCOPE-PROFILE.json",
        expected_ucm_source_manifest_root=pippi_source_manifest_root,
        expected_atlas_root=pippi_atlas_root)
    validator_raw_root = rooted({
        "schema": "mosaic.mmc.validator-raw-evidence.v0.1",
        "test_groups": {name: group["log"] for name, group in sorted(tests.items())},
        "source_root": expected_source,
    })
    claim_map = run_ucm_builder(
        ucm_source=pippi_source, operation="claim-map",
        request=claim_map_request(
            scope_profile,
            effect_raw_evidence_roots=[disposable["receipt_root"], target["receipt_root"]],
            validator_raw_evidence_roots=[validator_raw_root]),
        output=evidence / "MMC-CLAIM-DEPENDENCY-MAP.json",
        expected_ucm_source_manifest_root=pippi_source_manifest_root,
        expected_atlas_root=pippi_atlas_root)
    all_limitations = sorted(identifier for group in tests.values()
                             for identifier in group["host_limitations"])
    all_superseded = sorted(identifier for group in tests.values()
                            for identifier in group["successor_superseded_assertions"])
    body = {
        "schema": "mmc.qualification.t7",
        "status": "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS",
        "version": "0.1.0a9", "revision": "RELEASE-CONVERGENCE-r013",
        "source_root": expected_source, "source_files": len(before["body"]["files"]),
        "source_binding": "VERIFIED_BEFORE_AFTER_EACH_TEST_GROUP_AND_INTEGRATION",
        "qualification_index": component_summary,
        "evidence_scope": {
            "standard": "EVIDENCE_SCOPE_AND_REQUALIFICATION_DISCIPLINE",
            "pippi_source_manifest_root": pippi_source_manifest_root,
            "pippi_atlas_root": pippi_atlas_root,
            "inventory_root": rooted(scope_inventory),
            "profile_root": scope_profile["profile_root"],
            "claim_map_root": claim_map["claim_map_root"],
            "external_closure": scope_inventory["external_closure"],
            "impact_authority": "UCM_EVALUATE_REQUALIFICATION_IMPACT",
            "authority_effect": "NONE",
        },
        "integration_checkpoints": checkpoints, "preservation": preservation,
        "environment": {"platform": platform.system(), "release": platform.release(),
                        "python": platform.python_version(), "test_discovery_profile": test_profile},
        "tests": {name: {key: value for key, value in group.items() if key not in {"test_ids"}}
                  for name, group in tests.items()},
        "test_identity_files": [f"{name}-tests.json" for name in GROUPS],
        "host_limitations": all_limitations,
        "successor_superseded_assertions": all_superseded,
        "vectors": vectors,
        "product_root": hashlib.sha256(canonical(capabilities())).hexdigest(),
        "integration_status_root": hashlib.sha256(canonical(integration_status())).hexdigest(),
        "cmba": cmba, "ucm": ucm, "semcrys": semcrys,
        "stage_i1": {"sha256": sha(stage_path), "bytes": stage_path.stat().st_size,
                     "evidence": "EXECUTED_NATIVE_UCM_CMBA_PATHS_AND_HASH_CHAINED_JOURNAL"},
        "disposable_migration": {"receipt_root": disposable["receipt_root"],
                                 "status": disposable["status"],
                                 "dormant_worker_resume": disposable["dormant_worker_resume"]["status"],
                                 "retirement_status": disposable["retirement_status"]},
        "target_migration": {"receipt_root": target["receipt_root"], "status": target["status"],
                             "adapter": "SQLITE_TABLE_MIGRATION", "transport": "mmc.adapter-transport.v1"},
        "production_effect_adapter": "NOT_SHIPPED", "identity_binding": "UNBOUND",
        "jurisdiction_binding": "UNBOUND", "independent_review": "NOT_PERFORMED",
        "independent_study": "NOT_PERFORMED",
        "public_release": "APACHE_2_0_SOURCE_AUTHORIZED_DKN_ASSET_SIGNATURE_PENDING_OWNER",
        "authority_effect": "NONE", "elapsed_ns": time.perf_counter_ns() - started,
    }
    return {**body, "receipt_root": hashlib.sha256(canonical(body)).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True); parser.add_argument("--ucm-source", required=True)
    parser.add_argument("--pippi-source", required=True)
    parser.add_argument("--semcrys-source", required=True); parser.add_argument("--subject", required=True)
    parser.add_argument("--cmba-a4-wheel", required=True); parser.add_argument("--cmba-a7-wheel", required=True)
    parser.add_argument("--dkn-rc5-wheel", required=True); parser.add_argument("--dependency-bundle", required=True)
    parser.add_argument("--dependency-lock-root", required=True)
    parser.add_argument("--expected-source", required=True)
    args = parser.parse_args()
    output = Path(args.out).absolute()
    require(not output.is_relative_to(ROOT), "MMC_T7_EVIDENCE_INSIDE_SOURCE")
    receipt = qualify(Path(args.ucm_source), Path(args.pippi_source),
                      Path(args.semcrys_source), Path(args.subject),
                      Path(args.cmba_a4_wheel), Path(args.cmba_a7_wheel), Path(args.dkn_rc5_wheel),
                      Path(args.dependency_bundle), args.dependency_lock_root, args.expected_source, output)
    (output / "T7-QUALIFICATION.json").write_bytes(canonical(receipt))
    (output / "T7-QUALIFICATION.txt").write_text(
        "PASS\n" + json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(canonical(receipt).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
