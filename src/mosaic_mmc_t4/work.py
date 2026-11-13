"""Narrow agent work orders and non-effectful submission review."""
from .common import *
from .views import validate_snapshot, validate_reader, assess_view
from mosaic_mmc_t3.courts import scope
from mosaic_mmc_t3.common import clock
from mosaic_mmc_t3.statements import verify
from mosaic_mmc.model import observation_refs


@typed
def claim_contracts(s):
    bundle = s["plan"]["body"]["bundle"]
    objects = {o["id"]:o for o in bundle["model"]["objects"]}
    t = objects[s["transition"]]["attributes"]
    cohort = t["cohort"]; roster = sorted(objects[cohort]["attributes"]["members"])
    out = {"coverage":{"subject":cohort,"reference":{"members":roster,"complete":True},"source_refs":[cohort]}}
    from mosaic_mmc_t3.courts import compile_domain
    inst=next(x for x in compile_domain(bundle)["body"]["instructions"] if x["id"]==s["transition"])
    for ob in sorted({r for g in inst["guards"] if g.get("condition") is not None for r in observation_refs(g["condition"])}):
        out["fact:"+ob]={"subject":objects[ob]["attributes"]["subject"],"reference":objects[ob],"source_refs":[ob]}
    for a in bundle["assessments"]:
        if a["transition"]==s["transition"]:
            out["domain:"+a["id"]]={"subject":a["subject"],"reference":a["record"],"source_refs":[a["id"],a["subject"]]}
    for a in bundle["retirements"]:
        if a["transition"]==s["transition"]:
            out["retirement:"+s["transition"]]={"subject":cohort,"reference":a["record"],"source_refs":[s["transition"],cohort]}
    return out


def _resources(values):
    require(type(values) is list and len(values)<=16,"MMC_T4_RESOURCE_LIMIT")
    ids=[]
    for r in values:
        closed(r,{"id","root"});token(r["id"]);hashhex(r["root"]);ids.append(r["id"])
    require(len(ids)==len(set(ids)),"MMC_T4_RESOURCE_DUPLICATE")
    return sorted(clone(values),key=lambda x:x["id"])


@typed
def make_work_order(value, reader, claim, allowed_reads, ttl=30):
    s=validate_snapshot(value);validate_reader(s,reader);token(claim);integer(ttl,1,3600)
    view=assess_view(s,reader);contracts=claim_contracts(s)
    require(claim in contracts,"MMC_T4_CLAIM_UNKNOWN")
    relevant={"EVIDENCE:"+claim,"COVERAGE:"+claim,"CONTRADICTORY:"+claim}
    if claim.startswith("domain:"):relevant.add("DOMAIN:"+claim[7:])
    if claim=="coverage":relevant.add("SOURCE_COVERAGE")
    if claim.startswith("retirement:"):relevant|={"RETIREMENT_MODEL","RETIREMENT_FLOOR"}
    if claim.startswith("fact:"):
        ob=claim[5:]
        for g in view["body"]["obligations"]:
            if ob in observation_refs(g["condition"]) if g.get("condition") is not None else False:
                relevant.add("GUARD:"+g["id"])
    blockers=[x for x in view["body"]["blockers"] if x["code"] in relevant]
    require(blockers,"MMC_T4_NO_UNRESOLVED_OBLIGATION")
    c=contracts[claim]
    observers=[o for o in s["policy"]["observers"] if claim in o["claims"] and c["subject"] in o["subjects"] and scope(s["plan"],s["migration"],s["transition"])["cohort"] in o["cohorts"]]
    body={"schema":"mmc.work-order.t4","scope":scope(s["plan"],s["migration"],s["transition"]),
          "snapshot_root":digest("snapshot",s),"reader_root":digest("context",reader),"evaluator_root":identity(),
          "head":s["head"],"issued_at":reader["time"]["now"],"expires_at":reader["time"]["now"]+ttl,
          "ttl":ttl,"claim":claim,"subject":c["subject"],"source_refs":c["source_refs"],
          "reference":c["reference"],"blockers":blockers,"allowed_reads":_resources(allowed_reads),
          "recognized_observers":observers,"return_schema":"mmc.agent-submission.t4",
          "instructions":"Investigate this obligation. Return one scoped signed observation plus notes; uncertainty and negative evidence are valid. Do not change deployments, policy, pins or models.",
          "permissions":{"proposal_only":True,"sign":False,"fetch":False,"commit":False,"amend":False},
          "context_scope":"ONE_UNRESOLVED_CLAIM_NOT_FULL_HISTORY","effects":"NOT_EXECUTED",**BOUNDARY}
    canonical(body,limit=MAX_ORDER)
    return envelope("work",body)


@typed
def review_submission(value, reader, work_order, submission, *, expected_work_root):
    s=validate_snapshot(value);validate_reader(s,reader);hashhex(expected_work_root)
    require(work_order.get("root")==expected_work_root,"MMC_T4_WORK_PIN")
    w=unwrap("work",work_order)
    require(w.get("schema")=="mmc.work-order.t4","MMC_T4_WORK_SCHEMA")
    # Recompute rather than trust a self-hashed grant/instructions record.
    original_reader=clone(reader);original_reader["time"]["now"]=w["issued_at"]
    expected=make_work_order(s,original_reader,w["claim"],w["allowed_reads"],w["ttl"])
    require(canonical(expected)==canonical(work_order),"MMC_T4_WORK_MISMATCH")
    lo,hi=clock(reader["time"])
    require(w["issued_at"]<=lo and hi<w["expires_at"],"MMC_T4_WORK_EXPIRED")
    closed(submission,{"schema","work_order_root","record","notes"})
    require(submission["schema"]=="mmc.agent-submission.t4" and submission["work_order_root"]==work_order["root"],"MMC_T4_SUBMISSION_WORK")
    text(submission["notes"])
    b=verify(submission["record"])
    require(b["kind"]=="observation","MMC_T4_SUBMISSION_KIND")
    require(all(canonical(b[k])==canonical(v) for k,v in w["scope"].items()),"MMC_T4_SUBMISSION_SCOPE")
    require(b["payload"]["claim"]==w["claim"] and b["payload"]["subject"]==w["subject"],"MMC_T4_SUBMISSION_CLAIM")
    require(submission["record"]["root"] not in {r["root"] for r in s["records"]},"MMC_T4_SUBMISSION_DUPLICATE")
    before=assess_view(s,reader)
    updated=clone(s);updated["records"].append(clone(submission["record"]))
    from .views import reader_for_sample
    after_reader=clone(reader);after_reader["expected_snapshot_root"]=digest("snapshot",updated)
    after=assess_view(updated,after_reader)
    root=submission["record"]["root"]
    reasons=[q["reason"] for q in after["body"]["court"]["body"]["quarantine"] if q["root"]==root]
    admitted=root in after["body"]["court"]["body"]["accepted_statement_roots"] and not reasons
    return envelope("review",{"schema":"mmc.submission-review.t4","work_order_root":work_order["root"],
        "submission_root":digest("submission",submission),"snapshot_root":digest("snapshot",s),
        "status":"ELIGIBLE_FOR_HOST_EVIDENCE_ADMISSION" if admitted else "SUBMISSION_INELIGIBLE",
        "record_root":root,"reasons":sorted(set(reasons)),"before":before,"after":after,
        "evidence_label":"RECOMPUTED_NOT_STORED","effects":"NOT_EXECUTED",**BOUNDARY})
