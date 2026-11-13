"""Reusable, effect-free installed protocol conformance checks.

This runner tests framing and explicit negotiation only. Layer vectors and the
disposable migration remain separate qualification legs.
"""
from __future__ import annotations

from mosaic_mmc.errors import require
from .protocol import PROTOCOL, REQUEST_SCHEMA, RESPONSE_SCHEMA, dispatch, protocol_manifest


def run_conformance():
    manifest = protocol_manifest()
    cases = []

    def request(operation="protocol.describe", arguments=None):
        return {"schema": REQUEST_SCHEMA, "protocol": PROTOCOL, "request_id": "conformance.1",
                "operation": operation, "arguments": {} if arguments is None else arguments}

    def check(name, value, expected_ok=False, expected_status=None):
        response = dispatch(value)
        require(response["schema"] == RESPONSE_SCHEMA and response["protocol"] == PROTOCOL and
                response["authority_effect"] == "NONE" and response["ok"] is expected_ok,
                "MMC_T7_CONFORMANCE_FAILED", detail=name)
        if expected_status is not None:
            require(response["result"]["status"] == expected_status,
                    "MMC_T7_CONFORMANCE_FAILED", detail=name)
        cases.append({"id": name, "status": "PASS", "response_ok": response["ok"]})

    for row in manifest["operations"]:
        arguments = {key: None for key in row["argument_keys"]}
        arguments["unexpected"] = True
        check("closed-arguments:" + row["id"], request(row["id"], arguments))
    for field in ("schema", "protocol", "request_id", "operation", "arguments"):
        value = request()
        del value[field]
        check("missing-envelope-field:" + field, value)
    for index, value in enumerate((None, True, 0, "request", [], [request()])):
        check("non-object-request:" + str(index), value)
    for index, value in enumerate((None, True, 0, [], {}, "", "a\n", "x" * 129)):
        malformed = request()
        malformed["request_id"] = value
        check("invalid-request-id:" + str(index), malformed)
    check("unknown-operation", request("protocol.unknown"))
    for operation in ("protocol.describe", "product.operations", "transport.describe", "t1.capabilities", "t2.profiles", "t4.profiles"):
        check("read-only-operation:" + operation, request(operation), True)
    negotiation = {"protocols": [PROTOCOL], "required_operations": ["t1.compile"],
                   "required_features": ["local-schema-graph.v1"]}
    check("negotiation-compatible", request("protocol.negotiate", negotiation), True, "COMPATIBLE")
    for field, unsupported in (("protocols", "mmc.agent.v999"),
                               ("required_operations", "unknown.operation"),
                               ("required_features", "production.adapter")):
        arguments = {**negotiation, field: [unsupported]}
        check("negotiation-unsupported:" + field, request("protocol.negotiate", arguments), True, "INCOMPATIBLE")
    check("negotiation-duplicates", request("protocol.negotiate", {**negotiation, "protocols": [PROTOCOL, PROTOCOL]}))
    return {"schema": "mmc.agent-conformance.v1", "status": "PASS_PROTOCOL_CONFORMANCE",
            "protocol": PROTOCOL, "schema_sha256": manifest["schema_sha256"],
            "operation_count": manifest["operation_count"], "case_count": len(cases), "cases": cases,
            "scope": "UNIFORM_FRAMING_CLOSED_ARGUMENTS_AND_NEGOTIATION",
            "effects": "NO_EXTERNAL_MUTATION", "authority_effect": "NONE"}
