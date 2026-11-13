"""Two finite example extensions; not new migration-kernel primitives."""
from .common import *


@typed
def residency_profile(value):
    closed(value,{"schema","allowed_regions","items"})
    require(value["schema"]=="mmc.residency-input.t4","MMC_T4_RESIDENCY_SCHEMA")
    regions=value["allowed_regions"]
    require(type(regions) is list and 0<len(regions)<=32 and all(type(x) is str for x in regions),"MMC_T4_REGIONS")
    require(len(regions)==len(set(regions)),"MMC_T4_REGIONS")
    require(type(value["items"]) is list and len(value["items"])<=512,"MMC_T4_ITEMS")
    seen=set();blocked=[]
    for x in value["items"]:
        closed(x,{"id","region"});token(x["id"]);token(x["region"])
        require(x["id"] not in seen,"MMC_T4_ITEM_DUPLICATE");seen.add(x["id"])
        if x["region"] not in regions:blocked.append(x["id"])
    return {"schema":"mmc.residency-result.t4","status":"MATCH_FOR_SUPPLIED_RECORDS" if not blocked else "CONTRADICTED",
            "blocked":sorted(blocked),"physical_residency":"NOT_ESTABLISHED","authority_effect":"NONE"}


@typed
def job_observer(value):
    closed(value,{"schema","jobs"})
    require(value["schema"]=="mmc.job-input.t4","MMC_T4_JOB_SCHEMA")
    require(type(value["jobs"]) is list and len(value["jobs"])<=512,"MMC_T4_JOBS")
    risky=[];seen=set()
    for x in value["jobs"]:
        closed(x,{"id","version","resumable","fenced","pending_writes"});token(x["id"])
        require(x["id"] not in seen,"MMC_T4_ITEM_DUPLICATE");seen.add(x["id"])
        require(x["version"] in ("legacy","new") and type(x["resumable"]) is bool and type(x["fenced"]) is bool,"MMC_T4_JOB_TYPE")
        integer(x["pending_writes"])
        if x["version"]=="legacy" and not x["fenced"] and (x["resumable"] or x["pending_writes"]>0):risky.append(x["id"])
    return {"schema":"mmc.job-result.t4","status":"LEGACY_WRITERS_POSSIBLE" if risky else "NONE_IN_SUPPLIED_SNAPSHOT",
            "jobs":sorted(risky),"coverage":"SUPPLIED_SNAPSHOT_ONLY","authority_effect":"NONE"}


@typed
def descriptor(name):
    require(name in ("residency","jobs"),"MMC_T4_EXTENSION_UNKNOWN")
    return {"schema":"mmc.extension-descriptor.t4","id":"mmc.extension."+name,"version":"1",
            "kind":"profile" if name=="residency" else "observer",
            "input_schema":"mmc.residency-input.t4" if name=="residency" else "mmc.job-input.t4",
            "output_schema":"mmc.residency-result.t4" if name=="residency" else "mmc.job-result.t4",
            "max_bytes":262144,"claim_ceiling":"Supplied records only; no authenticated physical coverage or permission.",
            "effects":"NONE_DECLARED_TRUSTED_HOST_CODE"}


@typed
def assess_extension(name,value):
    require(name in ("residency","jobs"),"MMC_T4_EXTENSION_NOT_INSTALLED")
    from .sdk import invoke
    return invoke(residency_profile if name=="residency" else job_observer,descriptor(name),value)
