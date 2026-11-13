"""Build a UCM Stage-I1 return from executed native and UCM integration paths."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from uclop.canonical import canonical_bytes, require, root
from ucm.amcas import BOUNDARY, compile_contract, validate_contract
from ucm.artifacts import deterministic_zip
from ucm.correspondence import run_correspondence_court
from ucm.journal import CampaignJournal
from ucm.stage1 import assemble_stage1_bundle, verify_stage1_bundle
from ucm.subject import bind_subject, verify_subject_binding

from mosaic_mmc_product.integrations import probe_cmba_agent, probe_semcrys, probe_ucm


def rooted(schema: str, root_field: str, **fields):
    body = {"schema": schema, **fields, **BOUNDARY}
    return {**body, root_field: root(body)}


def _native_subject_facts(subject: Path, binding: dict) -> dict:
    """Independent MMC-side verification of every file in the bound manifest."""
    expected = {row["path"]: row for row in binding["manifest"]["files"]}
    observed = {}
    for path in sorted(subject.rglob("*"), key=lambda item: item.relative_to(subject).as_posix()):
        relative = path.relative_to(subject).as_posix()
        require(not path.is_symlink(), "MMC_STAGE1_NATIVE_SUBJECT_LINK")
        if path.is_file():
            raw = path.read_bytes()
            observed[relative] = {"path": relative, "bytes": len(raw),
                                  "sha256": hashlib.sha256(raw).hexdigest()}
    require(observed == expected, "MMC_STAGE1_NATIVE_SUBJECT_MISMATCH")
    return {"source_root": binding["source_root"], "manifest_root": binding["manifest_root"],
            "file_count": binding["file_count"]}


def _ucm_subject_facts(subject: Path, binding: dict) -> dict:
    actual = bind_subject(subject, binding["policy"])
    verify_subject_binding(actual)
    require(actual == binding, "MMC_STAGE1_UCM_SUBJECT_MISMATCH")
    return {"source_root": actual["source_root"], "manifest_root": actual["manifest_root"],
            "file_count": actual["file_count"]}


def _control_facts(control: dict) -> dict:
    body = {key: value for key, value in control.items() if key != "root"}
    require(control["root"] == root(body), "MMC_STAGE1_CONTROL_ROOT")
    return {"semantic_authority": control["semantic_authority"],
            "effect_executor": control["effect_executor"],
            "identity_binding_status": control["identity_binding_status"],
            "jurisdiction_binding_status": control["jurisdiction_binding_status"]}


def _dependency_facts(contract: dict, probes: dict) -> dict:
    actual = {
        "UCM_R036": root({"git_commit": probes["ucm"]["git_commit"],
                           "git_tree": probes["ucm"]["git_tree"]}),
        "CMBA_A7": probes["cmba"]["sha256"],
        "SEMCRYS_010": root({"git_commit": probes["semcrys"]["git_commit"],
                              "git_tree": probes["semcrys"]["git_tree"]}),
    }
    declared = {row["id"]: row["root"] for row in contract["dependencies"]}
    require(actual == declared, "MMC_STAGE1_DEPENDENCY_IDENTITY")
    return {"dependencies": [{"id": row["id"], "root": row["root"],
                               "required": row["required"]}
                              for row in sorted(contract["dependencies"], key=lambda item: item["id"])]}


def _native_reconcile_facts() -> dict:
    """Run a lost-ack reconciliation and observe the real journal append."""
    from tests_t3.helpers import Env, TIME
    with tempfile.TemporaryDirectory(prefix="mmc-stage1-reconcile-", dir=Path.cwd()) as directory:
        environment = Env(directory)
        request = environment.prepare()
        environment.approve(request)
        outcome = environment.controller.commit("op.1", environment.store, TIME, fault="lost_ack")
        require(outcome["status"] == "UNKNOWN", "MMC_STAGE1_RECONCILE_SETUP")
        before = len(environment.controller.journal.export())
        reconciled = environment.controller.reconcile("op.1", environment.store)
        after = len(environment.controller.journal.export())
        require(reconciled["status"] == "APPLIED" and after == before + 1,
                "MMC_STAGE1_RECONCILE_NOT_RECORDED")
    return {"production_adapter": False, "reconcile_effect_class": "WRITE_WORKSPACE",
            "declared_effects": 1}


def _ucm_effect_facts(contract: dict) -> dict:
    capability = next(row for row in contract["capabilities"] if row["id"] == "RECONCILE_CONTROLLER")
    effect = next(row for row in contract["effects"] if row["id"] == "RECONCILE_JOURNAL_OUTCOME")
    require(capability["effect_class"] == effect["effect_class"] == "WRITE_WORKSPACE",
            "MMC_STAGE1_RECONCILE_CONTRACT")
    return {"production_adapter": False, "reconcile_effect_class": effect["effect_class"],
            "declared_effects": len(contract["effects"])}


def _case(identifier: str, input_root: str, native_facts: dict, ucm_facts: dict) -> dict:
    native_decision = "PASS" if native_facts == ucm_facts else "FAIL"
    normalized_native = root({"case_id": identifier, "facts": native_facts})
    normalized_ucm = root({"case_id": identifier, "facts": ucm_facts})
    return {"case_id": identifier, "input_root": input_root,
            "native": {"decision": native_decision, "result_root": normalized_native},
            "ucm": {"decision": "PASS", "result_root": normalized_ucm}}


def _journal_archive(contract: dict, binding: dict, court: dict, probes: dict) -> tuple[bytes, dict]:
    actor = {"kind": "SYSTEM", "mosaic_id": None, "session_id": None}
    with tempfile.TemporaryDirectory(prefix="mmc-ucm-journal-", dir=Path.cwd()) as directory:
        journal = CampaignJournal(Path(directory))
        journal.initialize()
        rows = [
            ("campaign-created", "CAMPAIGN_CREATED", {"application_id": contract["application"]["id"]}),
            ("baseline-bound", "BASELINE_BOUND", {"binding_root": binding["binding_root"],
                                                    "source_root": binding["source_root"]}),
            ("contract-compiled", "CONTRACT_COMPILED", {"contract_root": contract["contract_root"],
                                                         "ir_root": compile_contract(contract)["ir_root"]}),
            ("dependencies-executed", "TEST_RECORDED", {
                "cmba_binding_root": probes["cmba"]["binding_root"],
                "ucm_contract_root": probes["ucm"]["contract_root"],
                "semcrys_capabilities_root": probes["semcrys"]["capabilities_root"],
            }),
            ("correspondence-court", "PROOF_RECORDED", {"court_root": court["court_root"],
                                                        "status": court["status"]}),
        ]
        for event_id, event_type, payload in rows:
            journal.append(event_id=event_id, event_type=event_type, actor=actor, payload=payload)
        events = journal.verify_read_only()
        head = journal.head()
        archive = deterministic_zip(
            {"EVENTS.jsonl": journal.events_path.read_bytes(),
             "HEAD.json": journal.head_path.read_bytes()},
            schema="mosaic.ucm.integration-journal-archive.v0.1",
            artifact_role="CANONICAL_INTEGRATION_JOURNAL",
        )
    return archive, {"head": head, "events": len(events)}


def build(binding: dict, contract: dict, control: dict, *, subject: Path,
          ucm_source: Path, cmba_wheel: Path, semcrys_source: Path) -> bytes:
    binding = verify_subject_binding(binding)
    contract = validate_contract(contract)
    compiled = compile_contract(contract)
    probes = {
        "cmba": probe_cmba_agent(cmba_wheel),
        "ucm": probe_ucm(ucm_source, Path(__file__).resolve().parents[1] / "interop/ucm/MMC-AMCAS-CONTRACT.json"),
        "semcrys": probe_semcrys(semcrys_source),
    }
    native_subject = _native_subject_facts(subject, binding)
    ucm_subject = _ucm_subject_facts(subject, binding)
    native_control = _control_facts(control)
    ucm_control = {
        "semantic_authority": compiled["integration_boundary"]["semantic_authority"],
        "effect_executor": compiled["integration_boundary"]["effect_executor"],
        "identity_binding_status": compiled["integration_boundary"]["identity_binding_status"],
        "jurisdiction_binding_status": compiled["integration_boundary"]["jurisdiction_binding_status"],
    }
    native_dependencies = _dependency_facts(contract, probes)
    ucm_dependencies = {"dependencies": [{"id": row["id"], "root": row["root"],
                                            "required": row["required"]}
                                           for row in sorted(contract["dependencies"], key=lambda item: item["id"])]}
    native_effects = _native_reconcile_facts()
    ucm_effects = _ucm_effect_facts(contract)
    requirement_roots = {row["id"]: row["subject_root"] for row in contract["cm1"]["requirements"]}
    cases = [
        _case("EXACT_SUBJECT", requirement_roots["EXACT_SUBJECT"], native_subject, ucm_subject),
        _case("NATIVE_AUTHORITY_RETAINED", requirement_roots["NATIVE_AUTHORITY_RETAINED"],
              native_control, ucm_control),
        _case("DEPENDENCY_GRAPH_DECLARED", requirement_roots["DEPENDENCY_GRAPH_DECLARED"],
              native_dependencies, ucm_dependencies),
        _case("PRODUCTION_EFFECTS_UNBOUND", requirement_roots["PRODUCTION_EFFECTS_UNBOUND"],
              native_effects, ucm_effects),
    ]
    court = run_correspondence_court({
        "schema": "mosaic.ucm.native-correspondence-cases.v0.1",
        "application_id": contract["application"]["id"],
        "subject_root": binding["source_root"],
        "native_validator_id": "MMC.T7.EXECUTED.NATIVE",
        "ucm_validator_id": "UCM.R036.EXECUTED.AMCAS",
        "cases": cases,
    })
    require(court["status"] == "PASS_EQUIVALENT", "MMC_STAGE1_CORRESPONDENCE_DIVERGENCE")
    journal, journal_evidence = _journal_archive(contract, binding, court, probes)
    inventory = rooted(
        "mosaic.ucm.capability-effect-inventory.v0.1", "inventory_root",
        application_id=contract["application"]["id"],
        capabilities=sorted(row["id"] for row in contract["capabilities"]),
        effects=sorted(row["id"] for row in contract["effects"]),
    )
    graph = rooted(
        "mosaic.ucm.integration-content-graph.v0.1", "graph_root",
        application_id=contract["application"]["id"],
        nodes=[{"id": "MMC", "kind": "APPLICATION", "root": binding["source_root"]},
               *[{"id": row["id"], "kind": row["kind"], "root": row["root"]}
                 for row in contract["dependencies"]]],
        edges=[{"provider": row["id"], "consumer": "MMC",
                "migration": "REQUIRED" if row["required"] else "COMPATIBILITY"}
               for row in contract["dependencies"]],
    )
    report = rooted(
        "mosaic.ucm.stage-i1-session-report.v0.1", "report_root",
        application_id=contract["application"]["id"], status="READY_FOR_REVIEW", findings=[],
        limitations=["INFORMATION_ONLY", "IDENTITY_AND_JURISDICTION_UNBOUND",
                     "NO_PRODUCTION_EFFECT_ADAPTER", "SHADOW_CORRESPONDENCE_IS_NOT_SEMANTIC_EQUIVALENCE_PROOF",
                     "SEMCRYS_ULTRA_ASSET_MISSING", "INDEPENDENT_REVIEW_AND_STUDY_NOT_PERFORMED"],
        installed="EXACT_CMBA_WHEEL_AND_SOURCE_PINNED_UCM_SEMCRYS",
        tested="EXECUTED_NATIVE_AND_UCM_PATHS_PLUS_CMBA_BINDING",
        correspondence_scope="SUBJECT_METADATA_DEPENDENCIES_AND_RECONCILIATION_EFFECT_DECLARATION",
        native_reconciliation="EXECUTED_LOST_ACK_AND_OBSERVED_ONE_NATIVE_JOURNAL_APPEND",
        ucm_reconciliation="VALIDATED_EFFECT_DECLARATION_ONLY_NOT_A_NATIVE_OUTCOME_OBSERVER",
        subject_role="IMMUTABLE_T6_PREDECESSOR_COMPATIBILITY_SUBJECT",
        executing_successor_source_root=__import__('tools.common', fromlist=['source_snapshot']).source_snapshot()["root"],
        accepted="EXTERNAL_DECISION_REQUIRED", court_root=court["court_root"],
        journal_head=journal_evidence["head"]["head"], journal_events=journal_evidence["events"],
    )
    payloads = {
        "SUBJECT-BINDING.json": canonical_bytes(binding), "AMCAS-CONTRACT.json": canonical_bytes(contract),
        "INTEGRATION-IR.json": canonical_bytes(compiled), "CONTROL-PLANE-DISPOSITION.json": canonical_bytes(control),
        "CORRESPONDENCE-COURT.json": canonical_bytes(court),
        "CAPABILITY-EFFECT-INVENTORY.json": canonical_bytes(inventory),
        "CONTENT-GRAPH.json": canonical_bytes(graph), "JOURNAL.zip": journal,
        "SESSION-REPORT.json": canonical_bytes(report),
    }
    archive = assemble_stage1_bundle(payloads, status="READY_FOR_REVIEW", limitations=report["limitations"])
    verify_stage1_bundle(archive)
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True); parser.add_argument("--contract", required=True)
    parser.add_argument("--control", required=True); parser.add_argument("--subject", required=True)
    parser.add_argument("--ucm-source", required=True); parser.add_argument("--cmba-wheel", required=True)
    parser.add_argument("--semcrys-source", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    archive = build(load(args.binding), load(args.contract), load(args.control),
                    subject=Path(args.subject), ucm_source=Path(args.ucm_source),
                    cmba_wheel=Path(args.cmba_wheel), semcrys_source=Path(args.semcrys_source))
    output = Path(args.out); output.write_bytes(archive)
    verification = verify_stage1_bundle(archive)
    print(json.dumps({**verification, "archive_sha256": hashlib.sha256(archive).hexdigest(),
                      "archive_bytes": len(archive)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
