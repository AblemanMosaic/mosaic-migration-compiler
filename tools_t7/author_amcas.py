"""Author the exact MMC AMCAS contract through the selected UCM implementation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from uclop.canonical import canonical_bytes, root
from ucm.amcas import compile_contract, make_contract
from ucm.realization import validate_contract as validate_realization


def build(binding: dict, control: dict, sample: dict) -> dict:
    realization = sample["realization_contract"]
    realization.update({
        "contract_id": "MMC.RUNTIME.REALIZATION",
        "contract_version": "0.1.0a9",
        "description": "Bounded MMC runtime selection; no production adapter or authority is selected.",
        "subject": {
            "subject_id": "MOSAIC.MMC.RUNTIME",
            "subject_schema": "mmc.product-capabilities.v1",
            "authority_owner": "UNBOUND",
            "source_roots": ["sha256:" + binding["source_root"]],
            "preserved_identity": ["MMC_MODEL", "MMC_COMPILER", "MMC_CONTROLLER", "MMC_EVIDENCE_RULES"],
            "forbidden_overrides": ["SEMANTIC_AUTHORITY", "EFFECT_AUTHORITY", "PRODUCTION_ADMISSION", "SECURITY_FLOORS"],
        },
        "possibility": {
            "intended_variation": ["host operating system", "bounded storage implementation", "shadow governance adapter"],
            "excluded_claims": ["production readiness", "global discovery completeness", "native identity binding", "effect authority"],
        },
        "axes": [
            {"id": "TARGET_OS", "label": "Qualified host family", "value_type": "ENUM", "domain": {"values": ["POSIX", "WINDOWS"]}, "default": "WINDOWS", "ownership": "AUTHORIAL", "mutability": "INSTANCE", "continuity": "DISCRETE", "authority_effect": "NONE"},
            {"id": "CONTROLLER_MODE", "label": "Controller effect mode", "value_type": "ENUM", "domain": {"values": ["SIMULATED_SQLITE"]}, "default": "SIMULATED_SQLITE", "ownership": "AUTHORIAL", "mutability": "INSTANCE", "continuity": "DISCRETE", "authority_effect": "NONE"},
            {"id": "PRODUCTION_ADAPTER", "label": "Production adapter selected", "value_type": "BOOLEAN", "domain": {}, "default": False, "ownership": "AUTHORIAL", "mutability": "INSTANCE", "continuity": "DISCRETE", "authority_effect": "NONE"},
            {"id": "UCM_MODE", "label": "UCM integration mode", "value_type": "ENUM", "domain": {"values": ["SHADOW"]}, "default": "SHADOW", "ownership": "AUTHORIAL", "mutability": "INSTANCE", "continuity": "DISCRETE", "authority_effect": "NONE"},
        ],
        "constraints": [
            {"id": "NO_PRODUCTION_ADAPTER", "kind": "CLAIM_BOUNDARY", "severity": "HARD", "operator": "EQUALS", "terms": {"axis": "PRODUCTION_ADAPTER", "value": False}, "explanation": "This package contains no production effect adapter.", "refusal_code": "MMC_PRODUCTION_ADAPTER_UNBOUND"},
            {"id": "UCM_SHADOW_ONLY", "kind": "CLAIM_BOUNDARY", "severity": "HARD", "operator": "EQUALS", "terms": {"axis": "UCM_MODE", "value": "SHADOW"}, "explanation": "UCM checks correspondence without replacing MMC semantics or effects.", "refusal_code": "MMC_UCM_REPLACEMENT_REFUSED"},
        ],
        "objectives": [{"metric_id": "PORTABLE_ARTIFACT_BYTES", "direction": "MINIMIZE", "priority": 100, "scope": "PORTABLE", "unit": "bytes", "measurement": "exact packaged bytes"}],
        "lowering": {"targets": [{"target_id": "MMC_PYTHON_312", "runtime_family": "CPYTHON", "adapter_version": "0.1.0a9", "required_capabilities": ["PYTHON_3_12"], "optional_capabilities": ["CRYPTOGRAPHY_50"], "preservation_criteria": ["MMC_MODEL", "MMC_COMPILER", "MMC_CONTROLLER", "AUTHORITY_CEILING"], "known_losses": ["NO_PRODUCTION_ADAPTER"], "fallbacks": []}], "allowed_results": ["EXACT", "BOUNDED", "FALLBACK", "LOSSY", "REFUSED"]},
        "evidence": {"required_roots": ["CONTRACT", "SUBJECT", "CONFIGURATION", "IMPLEMENTATION", "OUTPUT"], "required_fields": ["standing", "authority_effect"], "non_claims": ["NO_PRODUCTION_AUTHORITY", "NO_GLOBAL_DISCOVERY_PROOF", "NO_INDEPENDENT_STUDY_RESULT"]},
        "authority": {"standing": "INFORMATION_ONLY", "authority_effect": "NONE", "self_admission": False, "release_gate": False, "track_a_dependency": "NONE", "claim_boundary": "UNBOUND_CONFIGURATION_ONLY"},
    })
    realization["root"] = root({key: value for key, value in realization.items() if key != "root"})
    realization = validate_realization(realization)

    dependency_graph_root = root({
        "ucm": "9877d745129fa31f9141d74e245fa90fc3c51d8b",
        "cmba": "fad457fd7a8fe4598da1280fbca90881cfc5e48a5dd410ab9c784ffcb19c70ca",
        "semcrys": "eced61b6fea3e36ad90a9303fe4f8c138a5914b6",
    })
    requirements = [
        ("EXACT_SUBJECT", "EVIDENCE", "The exact Capability Layer T6 subject is bound before successor integration.", "AMCAS_SOURCE_BINDING_V1", binding["source_root"]),
        ("NATIVE_AUTHORITY_RETAINED", "SEMANTIC", "MMC remains the semantic authority and UCM remains a shadow governor.", "AMCAS_NATIVE_AUTHORITY_V1", control["root"]),
        ("DEPENDENCY_GRAPH_DECLARED", "DEPENDENCY", "UCM, CMBA, and optional SemCrys dependencies are exact and explicitly classified.", "AMCAS_DEPENDENCY_EVIDENCE_GRAPH_V1", dependency_graph_root),
        ("PRODUCTION_EFFECTS_UNBOUND", "ACCEPTANCE", "No contract or passing check grants production effect authority.", "AMCAS_AUTHORITY_CEILING_V1", root({"production_adapter": "NOT_SHIPPED", "authority_effect": "NONE"})),
    ]
    cm1 = {"membership_policy": "ALL_APPLICABLE_REQUIREMENTS_PASS", "requirements": [
        {"id": identifier, "kind": kind, "statement": statement, "subject_root": subject_root,
         "verifier": verifier, "evidence_required": True, "applicability": "REQUIRED"}
        for identifier, kind, statement, verifier, subject_root in requirements
    ]}
    capabilities = [
        {"id": "COMPILE_MIGRATION", "route": "mmc.compile", "effect_class": "PURE_COMPUTATION", "required": True, "request_schema": "mmc.request.t1", "result_schema": "mmc.compilation.t1"},
        {"id": "ASSESS_MIGRATION", "route": "mmc.assess", "effect_class": "PURE_COMPUTATION", "required": True, "request_schema": "mmc.request.t4", "result_schema": "mmc.assessment.t3"},
        {"id": "RECONCILE_CONTROLLER", "route": "mmc.controller.reconcile", "effect_class": "WRITE_WORKSPACE", "required": True, "request_schema": "mmc.operation.t3", "result_schema": "mmc.reconciliation.t3"},
        {"id": "INSPECT_INTEGRATIONS", "route": "mmc-product.integrations", "effect_class": "READ_ONLY", "required": True, "request_schema": "mmc.empty.v1", "result_schema": "mmc.integration-status.v1"},
    ]
    dependencies = [
        {"id": "UCM_R036", "kind": "TOOL", "root": root({"git_commit": "9877d745129fa31f9141d74e245fa90fc3c51d8b", "git_tree": "1c026e58816c31a0e46b6a73673ec0887b1174a0"}), "required": True},
        {"id": "CMBA_A7", "kind": "ARTIFACT", "root": "fad457fd7a8fe4598da1280fbca90881cfc5e48a5dd410ab9c784ffcb19c70ca", "required": True},
        {"id": "SEMCRYS_010", "kind": "TOOL", "root": root({"git_commit": "eced61b6fea3e36ad90a9303fe4f8c138a5914b6", "git_tree": "45e057c1da8da8899b84b7969b005b449268030b"}), "required": False},
    ]
    acceptance = [
        {"id": identifier, "obligation": "CM1:" + identifier,
         "evidence_schema": "mosaic.source-binding.v0.1" if identifier == "EXACT_SUBJECT" else "mosaic.ucm.integration-evidence.v0.1",
         "required": True}
        for identifier, *_ in requirements
    ]
    contract = make_contract(
        integration_id="MOSAIC.MMC.UCM.INTEGRATION",
        application={"id": "MOSAIC.MMC", "name": "Mosaic Migration Compiler", "version": "0.1.0a9"},
        subject={"source_root": binding["source_root"], "manifest_root": binding["manifest_root"], "path_policy": "PORTABLE_POSIX_RELATIVE_V1"},
        identities={"user_required": False, "agent_required": False, "jurisdiction": {"namespace_id": "MOSAIC.MMC", "universe_root": None, "epoch_id": None, "semantic_namespace": None}, "session_distinct": True, "possession_required": False, "delegation_required": False},
        cm1=cm1,
        cm2={"selection_policy": "CM1_THEN_CM2_LEXICOGRAPHIC", "preferences": [{"id": "MINIMIZE_SUPERVISION", "objective": "Prefer plans requiring fewer unresolved manual decisions among otherwise admissible plans.", "priority": 1, "metric": "UNRESOLVED_MANUAL_DECISIONS", "direction": "MINIMIZE"}]},
        capabilities=capabilities,
        effects=[{
            "id": "RECONCILE_JOURNAL_OUTCOME",
            "capability_id": "RECONCILE_CONTROLLER",
            "effect_class": "WRITE_WORKSPACE",
            "operation": "mmc.controller.reconcile.outcome",
            "ceiling": "NONE",
        }],
        dependencies=dependencies,
        acceptance=acceptance,
        portability={"profiles": ["JOURNAL", "SESSION_KIT"], "journal_export_required": True, "offline_closure_required": True},
        reporting={"required_sections": ["requirements", "capabilities", "operations", "findings", "limitations", "portable_artifacts"], "progress_channel": "NONSEMANTIC_JSONL_V1"},
        realization_contract=realization,
        integration_boundary={"semantic_authority": control["semantic_authority"], "effect_executor": control["effect_executor"], "identity_binding_status": control["identity_binding_status"], "jurisdiction_binding_status": control["jurisdiction_binding_status"], "gate_namespace": "UCM.INTEGRATION", "control_plane_root": control["root"]},
    )
    compile_contract(contract)
    return contract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True)
    parser.add_argument("--control", required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument(
        "--out",
        help="Write canonical contract bytes to this path instead of stdout.",
    )
    parser.add_argument(
        "--pin-module",
        help="Update the unique AMCAS_CONTRACT_ROOT assignment in this module.",
    )
    args = parser.parse_args()
    binding = json.loads(Path(args.binding).read_text(encoding="utf-8"))
    control = json.loads(Path(args.control).read_text(encoding="utf-8"))
    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    contract = build(binding, control, sample)
    encoded = canonical_bytes(contract)
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded + b"\n")
    else:
        print(encoded.decode("utf-8"))
    if args.pin_module:
        pin_module = Path(args.pin_module)
        source = pin_module.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(?m)^AMCAS_CONTRACT_ROOT = "[0-9a-f]{64}"$',
            f'AMCAS_CONTRACT_ROOT = "{contract["contract_root"]}"',
            source,
        )
        if count != 1:
            raise SystemExit("expected one AMCAS_CONTRACT_ROOT assignment")
        pin_module.write_text(updated, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
