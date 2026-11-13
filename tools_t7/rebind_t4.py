"""Mechanically rebind T4 fixtures after a realization-identity change.

The case intentions are retained explicitly; expected results are then frozen
and checked by tools_t4.check_vectors.  This is regression-fixture maintenance,
not independent semantic evidence.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import MMCError, canonical, decode
from mosaic_mmc_t3 import make_plan, seal
from mosaic_mmc_t3.statements import backend
from mosaic_mmc_t4.abi import dispatch
from mosaic_mmc_t4.views import assess_view, reader_for_sample
from mosaic_mmc_t4.work import make_work_order


def invoke(request: dict) -> dict:
    try:
        return {"result": dispatch(request)}
    except MMCError as error:
        return {"refusal": error.code}


def _fixture_key():
    ec, *_ = backend()
    return ec.derive_private_key(1, ec.SECP256R1())


def _record(record: dict, plan: dict) -> dict:
    body = deepcopy(record["body"])
    body["plan_root"] = plan["root"]
    body["policy_root"] = plan["body"]["policy_root"]
    return seal(body, _fixture_key())


def _snapshot(value: dict, plan: dict) -> dict:
    result = deepcopy(value)
    result["plan"] = plan
    result["records"] = [_record(row, plan) for row in value["records"]]
    return result


def rebind() -> dict:
    demo_path = ROOT / "src/mosaic_mmc_t4/data/demo.json"
    old_demo = decode(demo_path.read_bytes())
    old_snapshot = old_demo["workspace"]["snapshot"]
    plan = make_plan(old_snapshot["plan"]["body"]["bundle"], old_snapshot["policy"])
    snapshot = _snapshot(old_snapshot, plan)
    reader = reader_for_sample(snapshot)
    demo = {"label": old_demo["label"], "reader": reader,
            "workspace": {**old_demo["workspace"], "snapshot": snapshot}}
    demo_path.write_bytes(canonical(demo))
    (ROOT / "examples/t4/public-demo.json").write_bytes(canonical(demo))

    corpus_path = ROOT / "interop/t4-known-answers.json"
    corpus = decode(corpus_path.read_bytes())
    rebuilt = []
    for old_case in corpus["cases"]:
        case = deepcopy(old_case)
        identifier = case["id"]
        request = case["request"]
        arguments = request["arguments"]
        if "snapshot" in arguments:
            arguments["snapshot"] = _snapshot(arguments["snapshot"], plan)
            arguments["reader"] = reader_for_sample(arguments["snapshot"])
        if identifier in {"expected_plan_root", "expected_policy_root", "expected_snapshot_root"}:
            arguments["reader"][identifier] = "0" * 64
        if identifier in {"replay", "forged-pass"}:
            candidate = assess_view(arguments["snapshot"], arguments["reader"])
            if identifier == "forged-pass":
                candidate = deepcopy(candidate)
                candidate["body"]["status"] = "EVIDENCE_SATISFIES_SELECTED_POLICY"
            arguments["candidate"] = candidate
        if identifier == "compare-identical":
            value = assess_view(_snapshot(old_snapshot, plan), reader_for_sample(_snapshot(old_snapshot, plan)))
            arguments["first"] = value; arguments["second"] = value
        if request["operation"] == "review-submission":
            old_work = arguments["work_order"]["body"]
            work = make_work_order(arguments["snapshot"], arguments["reader"], old_work["claim"],
                                   old_work["allowed_reads"], old_work["ttl"])
            arguments["work_order"] = work
            arguments["submission"]["record"] = _record(arguments["submission"]["record"], plan)
            arguments["submission"]["work_order_root"] = work["root"]
            arguments["expected_work_root"] = "0" * 64 if identifier == "work-pin" else work["root"]
        case["expected"] = invoke(request)
        rebuilt.append(case)
    result = {"schema": corpus["schema"], "cases": rebuilt}
    corpus_path.write_bytes(canonical(result))
    digest = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    lock_path = ROOT / "provenance/turn4/VECTOR-LOCK.json"
    lock = decode(lock_path.read_bytes())
    lock["sha256"] = digest
    lock["cases"] = len(rebuilt)
    lock_path.write_bytes(canonical(lock))
    return {"schema": "mmc.t4-rebind.t7", "status": "PASS", "cases": len(rebuilt),
            "vector_sha256": digest, "fixture_scope": "REALIZATION_IDENTITY_REGRESSION_ONLY",
            "independent_semantic_evidence": False, "authority_effect": "NONE"}


if __name__ == "__main__":
    print(canonical(rebind()).decode("utf-8"))
