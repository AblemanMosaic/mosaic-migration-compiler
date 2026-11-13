from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import copy
from unittest.mock import patch

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc_product.protocol import (
    PROTOCOL, REQUEST_SCHEMA, RESPONSE_SCHEMA, dispatch, exported_schemas,
    protocol_manifest,
)
from mosaic_mmc_product.conformance import run_conformance
from mosaic_mmc_t3.courts import validate_adapter_descriptor
from mosaic_mmc import MMCError


class AgentProtocolTests(unittest.TestCase):
    def request(self, operation, arguments=None, request_id="request.1"):
        return {"schema": REQUEST_SCHEMA, "protocol": PROTOCOL,
                "request_id": request_id, "operation": operation,
                "arguments": {} if arguments is None else arguments}

    def test_manifest_covers_every_retained_layer_and_product_operation(self):
        manifest = protocol_manifest()
        self.assertEqual(manifest["operation_count"], 47)
        self.assertEqual(len({row["id"] for row in manifest["operations"]}), 47)
        self.assertTrue({"t1.compile", "t2.compile", "t3.evidence", "t4.work-order",
                         "migration.verify-disposable", "protocol.schemas"} <=
                        {row["id"] for row in manifest["operations"]})
        self.assertTrue(all(row["response_envelope"] == RESPONSE_SCHEMA
                            for row in manifest["operations"]))

    def test_exported_request_and_response_schemas_validate_live_messages(self):
        schemas = exported_schemas()
        jsonschema.Draft202012Validator.check_schema(schemas["request"])
        jsonschema.Draft202012Validator.check_schema(schemas["response"])
        request = self.request("t1.capabilities")
        response = dispatch(request)
        jsonschema.validate(request, schemas["request"])
        jsonschema.validate(response, schemas["response"])
        self.assertTrue(response["ok"])
        self.assertEqual(response["request_id"], request["request_id"])

    def test_refusals_use_same_envelope_and_exact_argument_keys(self):
        response = dispatch(self.request("t1.capabilities", {"extra": True}))
        self.assertFalse(response["ok"])
        self.assertEqual(response["schema"], RESPONSE_SCHEMA)
        self.assertEqual(response["error"]["code"], "MMC_T7_AGENT_ARGUMENTS")
        jsonschema.validate(response, exported_schemas()["response"])

    def test_all_schema_references_are_local_and_resolvable(self):
        schemas = exported_schemas()
        def walk(value, document):
            if type(value) is dict:
                if "$ref" in value:
                    self.assertTrue(value["$ref"].startswith("#/"), value["$ref"])
                    target = document
                    for part in value["$ref"][2:].split("/"):
                        target = target[part.replace("~1", "/").replace("~0", "~")]
                    self.assertIsInstance(target, dict)
                for item in value.values():
                    walk(item, document)
            elif type(value) is list:
                for item in value:
                    walk(item, document)
        walk(schemas["request"], schemas["request"])
        walk(schemas["response"], schemas["response"])
        self.assertEqual(schemas["schema_sha256"], protocol_manifest()["schema_sha256"])

    def test_layer_schema_bundle_and_adapter_generator_match_current_contract(self):
        from tools_t7.export_agent_schemas import bundle_bytes
        from mosaic_mmc import canonical, decode
        from tools_t3.export_schemas import schemas as native_schemas
        shipped = decode((ROOT / "src/mosaic_mmc_product/data/layer-schemas.json").read_bytes())
        self.assertEqual(canonical(shipped), bundle_bytes())
        for name, schema in native_schemas().items():
            self.assertEqual(schema, shipped["t3/" + name + ".schema.json"])
        validator = jsonschema.Draft202012Validator(exported_schemas()["request"]["$defs"]["t3_adapter"])
        descriptor = {"schema": "mmc.adapter.t3", "id": "adapter.disposable", "mode": "DISPOSABLE_LOCAL_SQLITE",
            "atomic_preconditions": True, "idempotency": "ATOMIC_LOCAL_LEDGER", "production": False,
            "max_targets": 64, "effect": "MIGRATE_DISPOSABLE_WORKLOAD", "power_loss_qualification": "NOT_PERFORMED"}
        validator.validate(descriptor)
        self.assertEqual(validate_adapter_descriptor(descriptor), descriptor)
        descriptor["effect"] = "UPDATE_SIMULATED_ROWS"
        self.assertFalse(validator.is_valid(descriptor))

    def test_nested_model_and_operational_schemas_accept_real_fixture(self):
        from tests_t3.helpers import bundle, policy, make_plan
        from mosaic_mmc_t4.views import snapshot, reader_for_sample
        b = bundle()
        p = policy(b)
        plan = make_plan(b, p)
        s = snapshot(plan, p, "migration.blue", "step.prepare", [])
        schema = exported_schemas()["request"]
        validator = jsonschema.Draft202012Validator(schema)
        for request in (self.request("t1.compile", {"model": b["model"]}),
                        self.request("t2.compile", {"bundle": b}),
                        self.request("t3.plan", {"bundle": b, "policy": p}),
                        self.request("t4.assess", {"snapshot": s, "reader": reader_for_sample(s)})):
            with self.subTest(operation=request["operation"]):
                validator.validate(request)
        invalid = self.request("t3.plan", {"bundle": copy.deepcopy(b), "policy": p})
        invalid["arguments"]["bundle"]["model"]["revision"] = "wrong"
        self.assertFalse(validator.is_valid(invalid))

    def test_malformed_identifiers_and_operation_type_are_framed(self):
        response_schema = exported_schemas()["response"]
        for field in ("request_id", "operation"):
            for value in ([], {}, None, True, 7, "x\n", "x" * 129):
                request = self.request("protocol.describe")
                request[field] = value
                response = dispatch(request)
                self.assertFalse(response["ok"])
                self.assertEqual(response[field], "invalid")
                jsonschema.Draft202012Validator(response_schema).validate(response)

    def test_product_path_arguments_refuse_non_strings_before_conversion(self):
        schemas = exported_schemas()
        validator = jsonschema.Draft202012Validator(schemas["request"])
        for value in (None, 3, [], {}, "", "invalid\x00path"):
            request = self.request("integration.verify-cmba-wheel", {"wheel": value})
            self.assertFalse(validator.is_valid(request))
            response = dispatch(request)
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "MMC_T7_AGENT_PATH")

    def test_native_argument_exceptions_and_unencodable_outputs_are_framed(self):
        for failure in (TypeError("invalid input"), KeyError("missing input"), ValueError("bad path")):
            with patch("mosaic_mmc_product.protocol._invoke", side_effect=failure):
                response = dispatch(self.request("product.capabilities"))
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"]["code"], "MMC_T7_AGENT_OPERATION_FAILED")
        with patch("mosaic_mmc_product.protocol._invoke", return_value=1.5):
            response = dispatch(self.request("product.capabilities"))
            self.assertFalse(response["ok"])
            self.assertEqual(response["error"]["code"], "MMC_VALUE_TYPE")

    def test_success_and_refusal_response_branches_are_exclusive(self):
        schema = exported_schemas()["response"]
        validator = jsonschema.Draft202012Validator(schema)
        success = dispatch(self.request("t1.capabilities"))
        success["error"] = {"code": "INVALID", "path": "$", "detail": ""}
        self.assertFalse(validator.is_valid(success))
        failure = dispatch(self.request("t1.capabilities", {"extra": 1}))
        failure["result"] = None
        self.assertFalse(validator.is_valid(failure))

    def test_negotiation_requires_requested_operations_and_features(self):
        args = {"protocols": [PROTOCOL], "required_operations": ["t1.compile"],
                "required_features": ["local-schema-graph.v1"]}
        result = dispatch(self.request("protocol.negotiate", args))
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["status"], "COMPATIBLE")
        jsonschema.Draft202012Validator(exported_schemas()["request"]).validate(
            self.request("protocol.negotiate", args))
        missing = dispatch(self.request("protocol.negotiate", {**args,
            "required_features": ["production.adapter"]}))
        self.assertTrue(missing["ok"])
        self.assertEqual(missing["result"]["status"], "INCOMPATIBLE")
        self.assertIsNone(missing["result"]["selected_protocol"])
        self.assertEqual(missing["result"]["missing_features"], ["production.adapter"])

    def test_installed_conformance_runner_covers_every_operation(self):
        report = run_conformance()
        self.assertEqual(report["status"], "PASS_PROTOCOL_CONFORMANCE")
        self.assertGreater(report["case_count"], 70)
        self.assertEqual(sum(row["id"].startswith("closed-arguments:") for row in report["cases"]), 47)

    def test_cli_request_success_refusal_and_malformed_json_are_framed(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        with tempfile.TemporaryDirectory() as directory:
            request = Path(directory) / "request.json"
            request.write_text(json.dumps(self.request("product.capabilities")), encoding="utf-8")
            success = subprocess.run([sys.executable, "-B", "-m", "mosaic_mmc_product",
                                      "request", str(request)], cwd=ROOT, env=environment,
                                     capture_output=True, timeout=30)
            self.assertEqual(success.returncode, 0, success.stderr.decode())
            self.assertTrue(json.loads(success.stdout)["ok"])
            request.write_text("{", encoding="utf-8")
            refused = subprocess.run([sys.executable, "-B", "-m", "mosaic_mmc_product",
                                      "request", str(request)], cwd=ROOT, env=environment,
                                     capture_output=True, timeout=30)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(json.loads(refused.stdout)["schema"], RESPONSE_SCHEMA)

    def test_adapter_profiles_are_closed_nonproduction_pairs(self):
        descriptor = {"schema": "mmc.adapter.t3", "id": "adapter.test",
                      "mode": "DISPOSABLE_LOCAL_SQLITE", "atomic_preconditions": True,
                      "idempotency": "ATOMIC_LOCAL_LEDGER", "production": False,
                      "max_targets": 64, "effect": "MIGRATE_DISPOSABLE_WORKLOAD",
                      "power_loss_qualification": "NOT_PERFORMED"}
        self.assertEqual(validate_adapter_descriptor(descriptor), descriptor)
        descriptor["effect"] = "UPDATE_SIMULATED_ROWS"
        with self.assertRaisesRegex(MMCError, "ADAPTER_PROFILE"):
            validate_adapter_descriptor(descriptor)


if __name__ == "__main__":
    unittest.main()
