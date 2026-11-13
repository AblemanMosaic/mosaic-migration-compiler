"""Bounded views over the actual T3 courts. No imports or policy from input code."""
from __future__ import annotations
from .common import *
from mosaic_mmc_t3.common import clock, digest as t3_digest
from mosaic_mmc_t3.courts import validate_plan, evaluate_evidence, scope, compile_domain
from mosaic_mmc_t3.statements import validate_policy

SNAPSHOT_FIELDS = {"schema", "plan", "policy", "migration", "transition", "records", "floor", "revoked", "head"}
READER_FIELDS = {"schema", "expected_plan_root", "expected_policy_root", "expected_snapshot_root", "time"}


@typed
def snapshot(plan, policy, migration, transition, records, *, floor=0, revoked=(), head=None):
    return validate_snapshot({"schema": "mmc.snapshot.t4", "plan": plan, "policy": policy,
        "migration": migration, "transition": transition, "records": records,
        "floor": floor, "revoked": list(revoked), "head": head})


@typed
def validate_snapshot(value):
    canonical(value, limit=MAX_INPUT)
    closed(value, SNAPSHOT_FIELDS)
    require(value["schema"] == "mmc.snapshot.t4", "MMC_T4_SNAPSHOT_SCHEMA")
    p = validate_policy(value["policy"])
    validate_plan(value["plan"], p)
    scope(value["plan"], value["migration"], value["transition"])
    integer(value["floor"])
    require(type(value["records"]) is list and len(value["records"]) <= 256, "MMC_T4_RECORD_LIMIT")
    require(type(value["revoked"]) is list and value["revoked"] == sorted(set(value["revoked"])), "MMC_T4_REVOKED")
    for item in value["revoked"]: token(item)
    if value["head"] is not None:
        closed(value["head"], {"sequence", "root"})
        integer(value["head"]["sequence"], 1); hashhex(value["head"]["root"])
    return clone(value)


@typed
def reader_for_sample(value, now=100):
    """Explicit demo helper; deriving a pin from an object is NOT independent recognition."""
    s = validate_snapshot(value)
    return {"schema": "mmc.reader.t4", "expected_plan_root": s["plan"]["root"],
            "expected_policy_root": t3_digest("policy", s["policy"]),
            "expected_snapshot_root": digest("snapshot", s), "time": {"now": now, "uncertainty": 0}}


@typed
def validate_reader(s, reader):
    closed(reader, READER_FIELDS)
    require(reader["schema"] == "mmc.reader.t4", "MMC_T4_READER_SCHEMA")
    for field in ("expected_plan_root", "expected_policy_root", "expected_snapshot_root"): hashhex(reader[field])
    require(reader["expected_plan_root"] == s["plan"]["root"], "MMC_T4_PLAN_PIN")
    require(reader["expected_policy_root"] == t3_digest("policy", s["policy"]), "MMC_T4_POLICY_PIN")
    require(reader["expected_snapshot_root"] == digest("snapshot", s), "MMC_T4_SNAPSHOT_PIN")
    clock(reader["time"])


@typed
def assess_view(value, reader):
    s = validate_snapshot(value); validate_reader(s, reader)
    court = evaluate_evidence(s["plan"], s["policy"], s["migration"], s["transition"],
        s["records"], reader["time"], floor=s["floor"], revoked=s["revoked"])
    model = s["plan"]["body"]["bundle"]["model"]
    compiled = compile_domain(s["plan"]["body"]["bundle"])
    graph = {"nodes": [{"id": x["id"], "kind": x["kind"]} for x in sorted(model["objects"], key=lambda x:x["id"])],
             "order_edges": compiled["body"]["plan"]["body"]["order_edges"],
             "witness": compiled["body"]["plan"]["body"]["witness"],
             "scope": "DECLARED_FINITE_MODEL_NOT_GLOBAL_DISCOVERY"}
    instructions = compiled["body"]["instructions"]
    obligations = next(x["guards"] for x in instructions if x["id"] == s["transition"])
    body = {"schema": "mmc.view.t4", "snapshot_root": digest("snapshot", s),
            "reader_root": digest("context", reader), "evaluator_root": identity(),
            "status": court["body"]["status"], "court": court, "obligations": obligations,
            "blockers": [c for c in court["body"]["checks"] if c["outcome"] != "PASS"],
            "graph": graph, "head": s["head"], "evidence_label": "RECOMPUTED_WITH_RECOGNIZED_TESTIMONY",
            "eligibility": "EVIDENCE_ONLY_NOT_OPERATIONAL_PERMISSION", "effects": "NOT_EXECUTED", **BOUNDARY}
    return envelope("view", body)


@typed
def replay_view(value, reader, candidate):
    actual = assess_view(value, reader)
    require(canonical(actual) == canonical(candidate), "MMC_T4_REPLAY_MISMATCH")
    return {"status": "MATCH_EXACT_REPLAY", "root": actual["root"], "effects": "NOT_EXECUTED", **BOUNDARY}


@typed
def compare_views(first, second):
    # Structural comparison never authenticates/replays either submitted result.
    a = unwrap("view", first); b = unwrap("view", second)
    require(a.get("schema") == b.get("schema") == "mmc.view.t4", "MMC_T4_VIEW_SCHEMA")
    return {"schema": "mmc.view-comparison.t4", "left": first["root"], "right": second["root"],
            "changed_fields": sorted(k for k in set(a)|set(b) if (k not in a or k not in b) or canonical(a[k]) != canonical(b[k])),
            "evidence_label": "IMPORTED_NOT_REPLAYED", "effects": "NOT_EXECUTED", **BOUNDARY}


@typed
def journal_view(events, expected_policy_root, minimum):
    """Verify the actual T3 journal chain and projection from supplied data, no DB opening."""
    from mosaic_mmc_t3.controller import project
    require(type(events) is list and 0 < len(events) <= 4096, "MMC_T4_JOURNAL_LIMIT")
    canonical(events, limit=MAX_INPUT)
    previous = "0"*64
    for i, e in enumerate(events,1):
        closed(e, {"sequence", "previous", "type", "payload", "root"})
        require(type(e["sequence"]) is int and e["sequence"] == i and e["previous"] == previous,
                "MMC_T4_JOURNAL_CHAIN")
        require(e["root"] == t3_digest("event", {k:e[k] for k in ("sequence","previous","type","payload")}),
                "MMC_T4_JOURNAL_HASH")
        previous = e["root"]
    require(events[0]["type"] == "GENESIS", "MMC_T4_JOURNAL_GENESIS")
    closed(events[0]["payload"], {"policy"})
    hashhex(expected_policy_root)
    require(t3_digest("policy", events[0]["payload"]["policy"]) == expected_policy_root, "MMC_T4_POLICY_PIN")
    if minimum is not None:
        closed(minimum, {"sequence","root"}); integer(minimum["sequence"],1);hashhex(minimum["root"])
        require(len(events)>=minimum["sequence"] and events[minimum["sequence"]-1]["root"]==minimum["root"],"MMC_T4_JOURNAL_FLOOR")
    try: state=project(events)
    except MMCError: raise
    except (KeyError,TypeError,ValueError,IndexError) as exc: raise MMCError("MMC_T4_JOURNAL_PROJECTION") from exc
    return {"schema":"mmc.journal-view.t4","projection":state,"timeline":[{"sequence":e["sequence"],"type":e["type"],"root":e["root"]} for e in events],
            "evidence_label":"REPLAYED_SUPPLIED_JOURNAL","host_custody":"NOT_ESTABLISHED","effects":"NOT_EXECUTED",**BOUNDARY}
