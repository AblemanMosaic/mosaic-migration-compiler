"""Discover implemented versioned interfaces without invoking an operation.

This is an inventory, not an effect dispatcher or a cross-version wire adapter.
The T2-T4 operation sets come from the dispatchers that actually enforce them.
Optional signing backends are loaded only by the operations that need them.
"""
from __future__ import annotations


_T1_ARGUMENTS = {
    "model-validate": {"model"},
    "compile": {"model"},
    "verify-ir": {"model", "compilation", "expected_model_root"},
    "capabilities": set(),
    "program-inspect": set(),
}


def layer_operation_catalogue() -> dict:
    """Return detached descriptors for the four retained native layer ABIs."""
    from mosaic_mmc_t2.abi import OPS as t2_operations
    from mosaic_mmc_t3.abi import OPERATIONS as t3_operations
    from mosaic_mmc_t4.abi import OPERATIONS as t4_operations
    from .product import VERSION, REVISION

    tables = {
        "t1": _T1_ARGUMENTS,
        "t2": {name: arguments for name, (arguments, _) in t2_operations.items()},
        "t3": t3_operations,
        "t4": t4_operations,
    }
    routes = {"t1": "mmc request REQUEST.json", "t2": "mmc-t2 request REQUEST.json",
              "t3": "mmc-t3 request REQUEST.json", "t4": "mmc-agent request REQUEST.json"}
    operations = []
    for layer, table in tables.items():
        for name, arguments in sorted(table.items()):
            operations.append({
                "id": f"{layer}.{name}",
                "layer": layer,
                "operation": name,
                "request_schema": f"mmc.request.{layer}",
                "argument_keys": sorted(arguments),
                "argument_policy": "EXACT_CLOSED_KEY_SET",
                "python_dispatch": f"mosaic_mmc{'_' + layer if layer != 't1' else ''}.abi.dispatch",
                "cli": routes[layer],
                "response_envelope": f"mmc.response.{layer}" if layer in {"t1", "t2"} else "OPERATION_SPECIFIC_RESULT",
                "effects": "HOST_INSTALLED_PACKAGE_READ" if (layer, name) == ("t4", "native-read") else "NO_EXTERNAL_MUTATION",
            })

    return {
        "schema": "mmc.layer-operation-catalogue.v1",
        "version": VERSION,
        "revision": REVISION,
        "status": "IMPLEMENTED_SURFACE_INVENTORY",
        "operations": operations,
        "operation_count": len(operations),
        "request_shape": {"fields": ["schema", "operation", "arguments"], "extra_fields": "REFUSED"},
        "wire_contract": {
            "encoding": "BOUNDED_UTF8_JSON_CANONICAL_OUTPUT",
            "types": "EXACT_JSON_TYPES_SIGNED_64_BIT_INTEGERS_NO_FLOATS",
            "schema_selection": "EXPLICIT_T1_T2_T3_T4_NO_AUTOMATIC_UPGRADE",
            "syntax_errors": "ARGPARSE_STDERR_EXIT_2",
            "operation_errors": "VERSION_SPECIFIC_REFUSAL_STDOUT_EXIT_2",
            "uniform_response_envelope": "AVAILABLE_THROUGH_MMC_AGENT_V1",
            "schema_export_cli": "MMC_PRODUCT_SCHEMA",
            "binary_abi": "NOT_IMPLEMENTED",
            "effect_dispatch_abi": "MMC_EFFECT_ADAPTER_PYTHON_V1_HOST_SELECTED",
        },
        "ir_surface": [
            {"schema": "mmc.ir.t1", "purpose": "STATIC_MODEL_LOWERING", "verification": "EXACT_RECOMPILATION_WITH_EXPECTED_MODEL_ROOT", "execution": "NONE"},
            {"schema": "mmc.domain-compilation.t2", "purpose": "DOMAIN_ASSESSMENTS_PLANNING_GUARDS_AND_INSTRUCTIONS", "verification": "EXACT_RECOMPILATION_WITH_EXPECTED_MODEL_ROOT", "execution": "NONE"},
            {"schema": "mmc.operational-plan.t3", "purpose": "PIN_MODEL_COMPILATION_POLICY_AND_EVALUATOR", "verification": "RECOMPILE_ON_ADMISSION", "execution": "SEQUENTIAL_HOST_SELECTED_EFFECT_ADAPTER"},
            {"schema": "mmc.effect-request.t3", "purpose": "BOUND_PRECONDITIONS_SCOPE_SECURITY_FLOORS_AND_EXPIRY", "verification": "POINT_OF_EFFECT_RECHECK_AND_LOCAL_LEDGER_RECONCILIATION", "execution": "HOST_ENROLLED_LOCAL_SQLITE_DIRECT_OR_AUTHENTICATED_PROCESS"},
        ],
        "host_only": [
            {"python": "mosaic_mmc_t3.Controller", "operations": ["create", "replay", "submit", "observe", "revise", "raise_floor", "pause", "resume", "assess", "prepare", "approve", "cancel", "commit", "reconcile"], "effects": "LOCAL_CONTROLLER_JOURNAL_AND_HOST_SELECTED_ADAPTER", "data_abi": "MMC_EFFECT_REQUEST_T3"},
            {"python": "mosaic_mmc_t3.EffectAdapter", "operations": ["descriptor", "snapshot", "lookup", "apply"], "effects": "IMPLEMENTATION_DECLARED", "data_abi": "MMC_EFFECT_ADAPTER_PYTHON_V1"},
            {"python": "mosaic_mmc_product.transport.AuthenticatedAdapter", "operations": ["open", "snapshot", "lookup", "apply", "cancel", "close", "transport_receipt"], "effects": "HOST_ENROLLED_AUTHENTICATED_WORKER_PROCESSES", "data_abi": "mmc.adapter-transport.v1"},
            {"python": "mosaic_mmc_product.sqlite_target.SQLiteTargetAdapter", "operations": ["enroll", "descriptor", "snapshot", "lookup", "apply", "workload_snapshot"], "effects": "ENROLLED_CUSTOMER_SQLITE_TABLES", "data_abi": "mmc.sqlite-target-enrollment.v1"},
            {"python": "mosaic_mmc_t3.SimulatedStore", "operations": ["create", "descriptor", "snapshot", "lookup", "apply", "raise_security"], "effects": "LOCAL_SIMULATED_SQLITE", "data_abi": "NOT_EXPOSED"},
            {"python": "mosaic_mmc_t4.AgentHost", "operations": ["capture", "admit"], "effects": "EVIDENCE_JOURNAL_ADMISSION_ONLY", "data_abi": "NOT_EXPOSED"},
            {"python": "mosaic_mmc_t4.ReadSession", "operations": ["read"], "effects": "HOST_ENROLLED_RESOURCE_READS", "data_abi": "NOT_EXPOSED"},
            {"python": "mosaic_mmc_t4.collectors", "operations": ["FileCollector.collect", "JsonFileCollector.collect", "SQLiteCollector.collect", "HttpCollector.collect"], "effects": "HOST_SELECTED_FILE_DATABASE_OR_HTTP_READ", "data_abi": "NOT_EXPOSED"},
            {"python": "mosaic_mmc_t4.exports.LocalExport", "operations": ["prepare", "approve", "cancel", "commit"], "effects": "HOST_APPROVED_CREATE_ONLY_LOCAL_EXPORT", "data_abi": "NOT_EXPOSED"},
            {"python": "mosaic_mmc_t4.Registry", "operations": ["qualify", "call", "descriptors"], "effects": "TRUSTED_HOST_PYTHON_NO_SANDBOX", "data_abi": "NOT_EXPOSED"},
        ],
        "other_cli": [
            {"command": "mmc-foundry", "operations": ["list", "run", "inspect", "replay"], "effects": "TEMPORARY_LOCAL_SIMULATION_FOR_RUN_AND_REPLAY", "json_dispatch_abi": "NOT_IMPLEMENTED"},
            {"command": "mmc-product", "operations": ["protocol", "schema", "request", "capabilities", "operations", "integrations", "verify-cmba-wheel", "probe-cmba", "probe-ucm", "probe-semcrys", "verify-disposable-migration", "verify-target-migration", "transport"], "effects": "DECLARED_PER_OPERATION", "json_dispatch_abi": "MMC_AGENT_V1"},
            {"command": "mmc-workbench", "operations": ["GUI"], "effects": "HOST_SELECTED_WORKSPACE_AND_EXPORT", "json_dispatch_abi": "NOT_IMPLEMENTED"},
        ],
        "maturity_gaps": ["REMOTE_NETWORK_ADAPTER_TRANSPORT", "PRODUCTION_DEPLOYMENT_QUALIFICATION", "CROSS_PLATFORM_QUALIFICATION", "INDEPENDENT_REVIEW_AND_COMPARATIVE_STUDY"],
        "authority_effect": "NONE",
    }


def operation_catalogue() -> dict:
    """Return the uniform agent protocol catalogue."""
    from .protocol import protocol_manifest
    return protocol_manifest()
