"""Installed, self-contained structural schema graph for MMC agent values.

All references are local to the exported document. Recursive predicate and JSON
value definitions deliberately retain local references rather than infinite expansion.
Runtime signature, pin, scope, ordering and exact replay checks remain authoritative.
"""
from __future__ import annotations

import copy
import json
from importlib import resources


HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
TOKEN = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$"}
INTEGER = {"type": "integer", "minimum": 0, "maximum": 2**63 - 1}


def obj(properties):
    return {"type": "object", "required": sorted(properties),
            "properties": properties, "additionalProperties": False}


def ref(name):
    return {"$ref": "#/$defs/" + name}


def array(items, maximum=128, minimum=0):
    return {"type": "array", "items": items, "maxItems": maximum, "minItems": minimum}


def envelope(body):
    return obj({"body": body, "root": HASH})


def _key(path):
    return path.replace(".schema", "").replace(".json", "").replace("/", "_").replace(".", "_")


def graph():
    raw = resources.files("mosaic_mmc_product").joinpath("data", "layer-schemas.json").read_bytes()
    source = json.loads(raw)
    names = {path: _key(path) for path in source}
    ids = {value["$id"]: names[path] for path, value in source.items() if "$id" in value}

    def localize(value, base):
        if type(value) is list:
            return [localize(item, base) for item in value]
        if type(value) is not dict:
            return value
        result = {}
        for key, item in value.items():
            if key in ("$id", "$schema"):
                continue
            if key == "$ref":
                if item.startswith("#"):
                    result[key] = "#/$defs/" + base + item[1:]
                else:
                    uri, _, fragment = item.partition("#")
                    result[key] = "#/$defs/" + ids[uri] + ("/" + fragment.lstrip("/") if fragment else "")
            else:
                result[key] = localize(item, base)
        return result

    definitions = {names[path]: localize(value, names[path]) for path, value in source.items()}
    definitions["json_value"] = {"anyOf": [
        {"type": ["null", "boolean"]},
        {"type": "integer", "minimum": -(2**63), "maximum": 2**63 - 1},
        {"type": "string", "maxLength": 65536},
        {"type": "array", "items": ref("json_value")},
        {"type": "object", "additionalProperties": ref("json_value")},
    ]}
    definitions["profile_ref"] = obj({"id": TOKEN, "version": TOKEN, "sha256": HASH})
    profiles = [ref("t2_" + name) for name in ("identity", "storage", "policy", "workload")]
    definitions["profile_record"] = {"oneOf": profiles}
    definitions["domain_bundle"] = obj({
        "schema": {"const": "mmc.domain-compilation-input.t2"}, "model": ref("model_t1"),
        "planning": ref("t2_planning"), "routes": ref("t2_routes"),
        "assessments": array(obj({"id": {"type": "string", "minLength": 1},
            "profile_ref": ref("profile_ref"), "transition": TOKEN,
            "subject": TOKEN, "record": ref("profile_record")})),
        "retirements": array(obj({"transition": TOKEN, "record": ref("t2_retirement")})),
    })
    definitions["head"] = {"anyOf": [{"type": "null"}, obj({"sequence": {**INTEGER, "minimum": 1}, "root": HASH})]}
    adapter = definitions["t3_adapter"]
    adapter["properties"]["mode"] = {"enum": ["SIMULATED_LOCAL_SQLITE", "DISPOSABLE_LOCAL_SQLITE", "SQLITE_TABLE_MIGRATION"]}
    adapter["properties"]["effect"] = {"enum": ["UPDATE_SIMULATED_ROWS", "MIGRATE_DISPOSABLE_WORKLOAD", "MIGRATE_ENROLLED_SQLITE_TABLES"]}
    adapter["oneOf"] = [{"properties": {"mode": {"const": mode}, "effect": {"const": effect}}}
        for mode, effect in (("SIMULATED_LOCAL_SQLITE", "UPDATE_SIMULATED_ROWS"),
                             ("DISPOSABLE_LOCAL_SQLITE", "MIGRATE_DISPOSABLE_WORKLOAD"),
                             ("SQLITE_TABLE_MIGRATION", "MIGRATE_ENROLLED_SQLITE_TABLES"))]
    definitions["t3_effect-request"]["properties"]["adapter"] = ref("t3_adapter")
    # The retained T3 request copy has an inline simulator descriptor; bind it
    # to the same current adapter definition as the exported authority route.
    for variant in definitions["t3_request"]["oneOf"]:
        if variant["properties"]["operation"]["const"] == "authority":
            variant["properties"]["arguments"]["properties"]["request"] = ref("t3_effect-request")
    definitions["t3_plan"]["properties"]["body"]["properties"]["bundle"] = ref("domain_bundle")
    snap = definitions["t4_snapshot"]["properties"]
    snap.update(plan=ref("t3_plan"), policy=ref("t3_policy"),
                records=array(ref("t3_statement"), 256), revoked=array(TOKEN), head=ref("head"))
    definitions["t4_submission"]["properties"]["record"] = ref("t3_statement")
    definitions["t4_workspace"]["properties"]["snapshot"] = ref("t4_snapshot")
    definitions["t4_workspace"]["properties"]["history"] = array(ref("t4_snapshot"), 64)
    definitions["t4_reader"]["properties"]["time"] = ref("t3_clock")
    court = definitions["t3_evidence-court"]["properties"]["body"]["properties"]
    court["checks"] = array(obj({"code": TOKEN, "outcome": {"enum": ["MISSING", "PASS", "BLOCK"]},
                                "refs": array(TOKEN, 512)}), 4096)
    court["quarantine"] = array(obj({"root": HASH, "reason": TOKEN}), 4096)
    view = definitions["t4_view"]["properties"]["body"]["properties"]
    view.update(court=ref("t3_evidence-court"), head=ref("head"))
    work = definitions["t4_work-order"]["properties"]["body"]["properties"]
    work.update(head=ref("head"), allowed_reads=array(ref("read_descriptor"), 16))
    review = definitions["t4_review"]["properties"]["body"]["properties"]
    review.update(before=ref("t4_view"), after=ref("t4_view"))
    definitions["read_descriptor"] = obj({"id": TOKEN, "root": HASH})
    definitions["residency_input"] = obj({"schema": {"const": "mmc.residency-input.t4"},
        "allowed_regions": {**array({"type": "string"}, 32, 1), "uniqueItems": True},
        "items": array(obj({"id": TOKEN, "region": TOKEN}), 512)})
    definitions["jobs_input"] = obj({"schema": {"const": "mmc.job-input.t4"},
        "jobs": array(obj({"id": TOKEN, "version": {"enum": ["legacy", "new"]},
            "resumable": {"type": "boolean"}, "fenced": {"type": "boolean"},
            "pending_writes": INTEGER}), 512)})
    # Replace legacy open schema leaves by an explicit strict-JSON value grammar.
    # This describes arbitrary supplied testimony without granting it standing.
    def fill(value):
        if type(value) is list:
            return [fill(item) for item in value]
        if type(value) is not dict:
            return value
        if not value:
            return ref("json_value")
        return {key: fill(item) if key not in ("properties", "$defs") else
                {name: fill(spec) for name, spec in item.items()}
                for key, item in value.items()}
    return fill(definitions)


def argument_schema(operation, keys):
    json_value = ref("json_value")
    properties = {key: json_value for key in keys}
    common = {
        "model": ref("model_t1"), "bundle": ref("domain_bundle"),
        "expected_model_root": HASH, "expected_work_root": HASH,
        "expected_policy_root": HASH, "profile_ref": ref("profile_ref"),
        "planning": ref("t2_planning"), "policy": ref("t3_policy"),
        "plan": ref("t3_plan"), "migration": TOKEN, "transition": TOKEN,
        "snapshot": ref("t4_snapshot"), "reader": ref("t4_reader"),
        "records": array(ref("t3_statement"), 256), "time": ref("t3_clock"),
        "floor": INTEGER, "revoked": array(TOKEN), "minimum": ref("head"),
        "work_order": ref("t4_work-order"), "submission": ref("t4_submission"),
        "claim": TOKEN, "ttl": {"type": "integer", "minimum": 1, "maximum": 3600},
        "events": array(ref("t3_journal-event"), 4096, 1),
    }
    properties.update({key: copy.deepcopy(common[key]) for key in keys if key in common})
    if operation == "t1.verify-ir":
        properties["compilation"] = ref("compilation_t1")
    if operation in ("t2.assess", "t2.replay"):
        properties["record"] = ref("profile_record")
        if "receipt" in properties:
            properties["receipt"] = envelope(json_value)
    if operation in ("t2.retirement", "t2.routes", "t2.lifecycle"):
        properties["record"] = ref("t2_" + operation.split(".")[1])
    if operation == "t3.verify-statement":
        properties["record"] = ref("t3_statement")
    if operation == "t3.authority":
        properties["request"] = ref("t3_effect-request")
    if operation == "t4.compare":
        properties.update(first=ref("t4_view"), second=ref("t4_view"))
    if operation == "t4.work-order":
        properties["allowed_reads"] = array(ref("read_descriptor"), 16)
    if operation == "t4.handoff":
        properties.update(target={"enum": ["pippi", "ucm", "cmba", "dkn", "chc"]},
            references=array(obj({"role": TOKEN, "sha256": HASH}), 32, 1))
    if operation == "t4.profile-assess":
        properties.update(name={"enum": ["residency", "jobs"]},
            value={"oneOf": [ref("residency_input"), ref("jobs_input")]})
    if operation == "t4.record-assess":
        properties["kind"] = {"enum": ["repository", "release", "deployment"]}
    if operation == "t4.native-read":
        properties.update(name={"enum": ["cmba", "dkn"]}, arguments={"type": "object", "additionalProperties": json_value})
    if operation.startswith("integration."):
        properties.update({key: {"type": "string", "minLength": 1, "maxLength": 32767,
                                  "pattern": "^[^\\u0000]+$"} for key in keys})
    if operation == "protocol.negotiate":
        properties = {"protocols": {**array({"type": "string", "minLength": 1, "maxLength": 128}, 16, 1), "uniqueItems": True},
            "required_operations": {**array({"type": "string", "minLength": 1, "maxLength": 128}, 128), "uniqueItems": True},
            "required_features": {**array({"type": "string", "minLength": 1, "maxLength": 128}, 32), "uniqueItems": True}}
    return obj(properties)
