"""Uniform versioned JSON protocol over the installed MMC agent surface."""
from __future__ import annotations

import re
import hashlib
from pathlib import Path

from mosaic_mmc import canonical, MMCError
from mosaic_mmc.errors import require


PROTOCOL = "mmc.agent.v1"
REQUEST_SCHEMA = "mmc.agent-request.v1"
RESPONSE_SCHEMA = "mmc.agent-response.v1"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
FEATURES = ["closed-arguments.v1", "effect-declarations.v1", "local-schema-graph.v1",
            "python-effect-adapter.v1", "uniform-refusals.v1", "authenticated-adapter-stdio.v1",
            "enrolled-sqlite-target.v1"]

PRODUCT_ARGUMENTS = {
    "protocol.describe": set(),
    "protocol.schemas": set(),
    "protocol.negotiate": {"protocols", "required_operations", "required_features"},
    "product.capabilities": set(),
    "product.operations": set(),
    "product.integrations": set(),
    "integration.verify-cmba-wheel": {"wheel"},
    "integration.probe-cmba": {"wheel"},
    "integration.probe-ucm": {"source", "contract"},
    "integration.probe-semcrys": {"source"},
    "migration.verify-disposable": set(),
    "migration.verify-target": set(),
    "transport.describe": set(),
}

PRODUCT_EFFECTS = {
    "protocol.describe": "NO_EXTERNAL_MUTATION",
    "protocol.schemas": "NO_EXTERNAL_MUTATION",
    "protocol.negotiate": "NO_EXTERNAL_MUTATION",
    "product.capabilities": "NO_EXTERNAL_MUTATION",
    "product.operations": "NO_EXTERNAL_MUTATION",
    "product.integrations": "NO_EXTERNAL_MUTATION",
    "integration.verify-cmba-wheel": "HOST_SELECTED_FILE_READ",
    "integration.probe-cmba": "HOST_SELECTED_WHEEL_SUBPROCESS_READ",
    "integration.probe-ucm": "HOST_SELECTED_SOURCE_AND_CONTRACT_READ",
    "integration.probe-semcrys": "HOST_SELECTED_SOURCE_READ",
    "migration.verify-disposable": "TEMPORARY_LOCAL_SQLITE_AND_CHILD_PROCESS",
    "migration.verify-target": "TEMPORARY_ENROLLED_SQLITE_AND_AUTHENTICATED_CHILD_PROCESSES",
    "transport.describe": "NO_EXTERNAL_MUTATION",
}


def _operation_rows():
    from .surface import layer_operation_catalogue
    rows = []
    for source in layer_operation_catalogue()["operations"]:
        row = dict(source)
        row["native_response_envelope"] = row["response_envelope"]
        row["request_schema"] = REQUEST_SCHEMA
        row["response_envelope"] = RESPONSE_SCHEMA
        row["cli"] = "mmc-product request REQUEST.json"
        rows.append(row)
    for operation, arguments in PRODUCT_ARGUMENTS.items():
        rows.append({
            "id": operation, "layer": operation.split(".", 1)[0],
            "operation": operation, "request_schema": REQUEST_SCHEMA,
            "argument_keys": sorted(arguments),
            "argument_policy": "EXACT_CLOSED_KEY_SET",
            "python_dispatch": "mosaic_mmc_product.protocol.dispatch",
            "cli": "mmc-product request REQUEST.json",
            "response_envelope": RESPONSE_SCHEMA,
            "effects": PRODUCT_EFFECTS[operation],
        })
    for row in rows:
        row["introduced_in"] = PROTOCOL
        row["deprecated"] = False
    return sorted(rows, key=lambda row: row["id"])


def exported_schemas():
    from .schema_graph import graph, argument_schema
    rows = _operation_rows()
    definitions = graph()
    request = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:mosaic:mmc:agent-request:v1", "title": REQUEST_SCHEMA,
        "oneOf": [{
            "type": "object", "required": ["schema", "protocol", "request_id", "operation", "arguments"],
            "properties": {
                "schema": {"const": REQUEST_SCHEMA},
                "protocol": {"const": PROTOCOL},
                "request_id": {"type": "string", "pattern": _TOKEN.pattern},
                "operation": {"const": row["id"]},
                "arguments": argument_schema(row["id"], row["argument_keys"]),
            },
            "additionalProperties": False,
        } for row in rows],
        "$defs": definitions,
        "allOf": [{"$ref": "#/$defs/json_value"}],
        "x-mmc-runtime-limits": {"max_bytes": 8 * 1024 * 1024, "max_depth": 32,
                                 "max_nodes": 50000, "max_string_utf8_bytes": 65536},
    }
    response = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:mosaic:mmc:agent-response:v1", "title": RESPONSE_SCHEMA,
        "type": "object",
        "required": ["schema", "protocol", "request_id", "operation", "ok", "authority_effect"],
        "properties": {
            "schema": {"const": RESPONSE_SCHEMA}, "protocol": {"const": PROTOCOL},
            "request_id": {"type": "string", "pattern": _TOKEN.pattern},
            "operation": {"type": "string", "pattern": _TOKEN.pattern},
            "ok": {"type": "boolean"}, "result": {"$ref": "#/$defs/json_value"},
            "error": {"type": "object", "required": ["code", "path", "detail"],
                      "properties": {"code": {"type": "string"},
                                     "path": {"type": "string"},
                                     "detail": {"type": "string"}},
                      "additionalProperties": False},
            "effects": {"type": "string"}, "authority_effect": {"const": "NONE"},
        },
        "oneOf": [
            {"properties": {"ok": {"const": True}}, "required": ["result", "effects"],
             "not": {"required": ["error"]}},
            {"properties": {"ok": {"const": False}}, "required": ["error"],
             "not": {"anyOf": [{"required": ["result"]}, {"required": ["effects"]}]}},
        ],
        "$defs": {"json_value": definitions["json_value"]},
        "additionalProperties": False,
    }
    root = hashlib.sha256(canonical({"request": request, "response": response})).hexdigest()
    return {"schema": "mmc.agent-schemas.v1", "protocol": PROTOCOL,
            "request": request, "response": response, "schema_sha256": root,
            "reference_policy": "ALL_REFERENCES_LOCAL_RECURSION_RETAINS_LOCAL_REFS",
            "result_schema_policy": "KNOWN_LAYER_STRUCTURES_IN_DEFS_OTHER_RESULTS_STRICT_JSON_VALUES",
            "semantic_checks": "NATIVE_PIN_SIGNATURE_SCOPE_AND_REPLAY_VALIDATORS",
            "authority_effect": "NONE"}


def protocol_manifest():
    from .product import VERSION, REVISION
    operations = _operation_rows()
    return {
        "schema": "mmc.agent-protocol-manifest.v1", "protocol": PROTOCOL,
        "version": VERSION, "revision": REVISION, "status": "IMPLEMENTED",
        "transport": {
            "encoding": "BOUNDED_UTF8_JSON", "canonical_output": True,
            "request": REQUEST_SCHEMA, "response": RESPONSE_SCHEMA,
            "success_exit": 0, "refusal_exit": 2,
        },
        "operations": operations, "operation_count": len(operations),
        "features": list(FEATURES),
        "compatibility": {
            "selection": "EXPLICIT_NEGOTIATION_NO_AUTOMATIC_UPGRADE",
            "supported_protocols": [PROTOCOL], "operation": "protocol.negotiate",
            "within_protocol": "EXISTING_OPERATIONS_ARGUMENTS_RESULTS_AND_EFFECT_CLASSES_STABLE",
            "additions": "CLIENTS_REQUIRE_ONLY_NEEDED_OPERATION_AND_FEATURE_IDS",
            "breaking_changes": "NEW_PROTOCOL_MAJOR_REQUIRED",
            "deprecation": "ANNOUNCE_REPLACEMENT_AND_REMOVAL_MAJOR_KEEP_CURRENT_MAJOR_AVAILABLE",
            "negotiation_grants_authority": False,
        },
        "schema_sha256": exported_schemas()["schema_sha256"],
        "effect_adapter_abi": {
            "id": "mmc.effect-adapter.python.v1", "selection": "TRUSTED_HOST_OBJECT_ONLY",
            "methods": ["descriptor", "snapshot", "lookup", "apply"],
            "request": "mmc.effect-request.t3", "descriptor": "mmc.adapter.t3",
            "reconciliation": "ATOMIC_LOCAL_LEDGER_LOOKUP_BY_OPERATION_AND_REQUEST_ROOT",
            "profiles": ["SIMULATED_LOCAL_SQLITE", "DISPOSABLE_LOCAL_SQLITE", "SQLITE_TABLE_MIGRATION"],
            "production_profile": "NOT_SHIPPED",
            "process_transport": "mmc.adapter-transport.v1",
        },
        "schema_export": "mmc-product schema request|response|all",
        "conformance": "mosaic_mmc_product.conformance.run_conformance",
        "nested_value_schemas": "INSTALLED_SELF_CONTAINED_LOCAL_REFERENCE_GRAPH",
        "schema_checks": "STRUCTURAL_ONLY_RUNTIME_PIN_SIGNATURE_SCOPE_REPLAY_CHECKS_REQUIRED",
        "authority_effect": "NONE",
    }


def _validate(request):
    canonical(request, limit=8 * 1024 * 1024)
    require(type(request) is dict and set(request) == {
        "schema", "protocol", "request_id", "operation", "arguments",
    }, "MMC_T7_AGENT_REQUEST_SHAPE")
    require(request["schema"] == REQUEST_SCHEMA and request["protocol"] == PROTOCOL,
            "MMC_T7_AGENT_PROTOCOL")
    require(type(request["request_id"]) is str and _TOKEN.fullmatch(request["request_id"]) is not None,
            "MMC_T7_AGENT_REQUEST_ID")
    operation = request["operation"]
    rows = {row["id"]: row for row in _operation_rows()}
    require(type(operation) is str and operation in rows, "MMC_T7_AGENT_OPERATION")
    arguments = request["arguments"]
    require(type(arguments) is dict and set(arguments) == set(rows[operation]["argument_keys"]),
            "MMC_T7_AGENT_ARGUMENTS")
    if operation.startswith("integration."):
        for value in arguments.values():
            require(type(value) is str and 0 < len(value) <= 32767 and "\x00" not in value,
                    "MMC_T7_AGENT_PATH")
    return rows[operation]


def negotiate(arguments):
    """Select a mutually supported wire surface; this never enrolls an adapter."""
    require(type(arguments) is dict and set(arguments) == {
        "protocols", "required_operations", "required_features"}, "MMC_T7_AGENT_NEGOTIATION")
    for key, maximum, minimum in (("protocols", 16, 1), ("required_operations", 128, 0),
                                  ("required_features", 32, 0)):
        values = arguments[key]
        require(type(values) is list and minimum <= len(values) <= maximum and
                all(type(value) is str and 0 < len(value) <= 128 for value in values),
                "MMC_T7_AGENT_NEGOTIATION")
        require(len(set(values)) == len(values), "MMC_T7_AGENT_NEGOTIATION")
    known = {row["id"] for row in _operation_rows()}
    missing_operations = sorted(set(arguments["required_operations"]) - known)
    missing_features = sorted(set(arguments["required_features"]) - set(FEATURES))
    compatible = PROTOCOL in arguments["protocols"] and not missing_operations and not missing_features
    return {"schema": "mmc.agent-negotiation.v1", "status": "COMPATIBLE" if compatible else "INCOMPATIBLE",
            "selected_protocol": PROTOCOL if compatible else None,
            "supported_protocols": [PROTOCOL], "missing_operations": missing_operations,
            "missing_features": missing_features, "schema_sha256": exported_schemas()["schema_sha256"],
            "authority_effect": "NONE"}


def _invoke(operation, arguments):
    if operation.startswith(("t1.", "t2.", "t3.", "t4.")):
        layer, name = operation.split(".", 1)
        if layer == "t1":
            from mosaic_mmc.abi import dispatch as implementation
        elif layer == "t2":
            from mosaic_mmc_t2.abi import dispatch as implementation
        elif layer == "t3":
            from mosaic_mmc_t3.abi import dispatch as implementation
        else:
            from mosaic_mmc_t4.abi import dispatch as implementation
        return implementation({"schema": f"mmc.request.{layer}",
                               "operation": name, "arguments": arguments})
    if operation == "protocol.describe":
        return protocol_manifest()
    if operation == "protocol.schemas":
        return exported_schemas()
    if operation == "protocol.negotiate":
        return negotiate(arguments)
    if operation == "product.capabilities":
        from .product import capabilities
        return capabilities()
    if operation == "product.operations":
        return protocol_manifest()
    if operation == "product.integrations":
        from .product import integration_status
        return integration_status()
    if operation == "migration.verify-disposable":
        from .disposable import run_disposable_migration
        return run_disposable_migration()
    if operation == "migration.verify-target":
        from .target_qualification import run_target_qualification
        return run_target_qualification()
    if operation == "transport.describe":
        from .transport import transport_manifest
        return transport_manifest()
    from .integrations import probe_cmba_agent, probe_semcrys, probe_ucm, verify_cmba_wheel
    if operation == "integration.verify-cmba-wheel":
        return verify_cmba_wheel(Path(arguments["wheel"]))
    if operation == "integration.probe-cmba":
        return probe_cmba_agent(Path(arguments["wheel"]))
    if operation == "integration.probe-ucm":
        return probe_ucm(Path(arguments["source"]), Path(arguments["contract"]))
    return probe_semcrys(Path(arguments["source"]))


def refusal(error, *, request_id="invalid", operation="invalid"):
    request_id = request_id if type(request_id) is str and _TOKEN.fullmatch(request_id) else "invalid"
    operation = operation if type(operation) is str and _TOKEN.fullmatch(operation) else "invalid"
    response = {
        "schema": RESPONSE_SCHEMA, "protocol": PROTOCOL,
        "request_id": request_id, "operation": operation, "ok": False,
        "error": error.record(), "authority_effect": "NONE",
    }
    canonical(response)
    return response


def dispatch(request):
    request_id = request.get("request_id", "invalid") if type(request) is dict else "invalid"
    operation = request.get("operation", "invalid") if type(request) is dict else "invalid"
    try:
        row = _validate(request)
        result = _invoke(operation, request["arguments"])
        response = {
            "schema": RESPONSE_SCHEMA, "protocol": PROTOCOL,
            "request_id": request_id, "operation": operation, "ok": True,
            "result": result, "effects": row["effects"], "authority_effect": "NONE",
        }
        canonical(response, limit=16 * 1024 * 1024)
    except MMCError as error:
        response = refusal(error, request_id=request_id, operation=operation)
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
        failure = MMCError("MMC_T7_AGENT_OPERATION_FAILED", detail=type(error).__name__)
        response = refusal(failure, request_id=request_id, operation=operation)
    canonical(response, limit=16 * 1024 * 1024)
    return response

