"""Closed metamodel validation and normalization; no claims of live inventory completeness."""
from __future__ import annotations
import re
from .codec import canonical, clone
from .contracts import contract, profile_reference
from .errors import MMCError, require

ID = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z", re.ASCII)
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,127}\Z", re.ASCII)
HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def closed(value: object, keys: set[str], path: str) -> None:
    require(type(value) is dict, "MMC_OBJECT_REQUIRED", path)
    require(set(value) == keys, "MMC_FIELDS", path,
            "missing=" + ",".join(sorted(keys-set(value))) + "; extra_count=" + str(len(set(value)-keys)) + "; extra_sample=" + ",".join(k[:96] for k in sorted(set(value)-keys)[:8]))


def _pattern(value: object, regex: re.Pattern, path: str) -> str:
    require(type(value) is str and regex.fullmatch(value) is not None, "MMC_TOKEN", path)
    return value


def _predicate(value: object, path: str, refs: list, depth: int = 0, budget: list|None = None) -> dict:
    if budget is None:
        budget = [0]
    budget[0] += 1
    require(depth <= 16 and budget[0] <= 256, "MMC_PREDICATE_LIMIT", path)
    require(type(value) is dict, "MMC_PREDICATE", path)
    op = value.get("op")
    if op == "literal":
        closed(value, {"op","value"}, path)
        require(type(value["value"]) is bool, "MMC_EXACT_TYPE", path+".value")
    elif op == "eq":
        closed(value, {"op","observation","value"}, path)
        _pattern(value["observation"], ID, path+".observation")
        require(type(value["value"]) in (type(None),bool,int,str), "MMC_SCALAR", path+".value")
        refs.append((value["observation"], ["Observation"], path+".observation"))
    elif op in ("all", "any"):
        closed(value, {"op","items"}, path)
        require(type(value["items"]) is list and 1 <= len(value["items"]) <= 16, "MMC_PREDICATE_LIMIT", path)
        for i, item in enumerate(value["items"]):
            _predicate(item, path+f".items[{i}]", refs, depth+1, budget)
    elif op == "not":
        closed(value, {"op","item"}, path)
        _predicate(value["item"], path+".item", refs, depth+1, budget)
    else:
        raise MMCError("MMC_OPERATOR_UNSUPPORTED", path, "Only fixed T1 predicates are admitted")
    return clone(value)


def _shape(value: object, spec: dict, path: str, refs: list) -> object:
    t = spec["type"]
    if t == "nullable":
        return None if value is None else _shape(value, spec["item"], path, refs)
    if t == "ref":
        _pattern(value, ID, path)
        refs.append((value, spec["kinds"], path))
    elif t in ("token", "digest"):
        _pattern(value, TOKEN if t == "token" else HEX, path)
    elif t == "text":
        require(type(value) is str and len(value) > 0, "MMC_TEXT", path)
    elif t == "boolean":
        require(type(value) is bool, "MMC_EXACT_TYPE", path)
    elif t == "integer":
        require(type(value) is int and spec["minimum"] <= value <= spec["maximum"], "MMC_INTEGER_RANGE", path)
    elif t == "enum":
        require(type(value) is str and value in spec["values"], "MMC_ENUM", path)
    elif t == "scalar":
        require(type(value) in (type(None),bool,int,str), "MMC_SCALAR", path)
    elif t == "set":
        require(type(value) is list and spec["minimum"] <= len(value) <= 512, "MMC_SET_LIMIT", path)
        result = [_shape(v,spec["item"],path+f"[{i}]",refs) for i,v in enumerate(value)]
        keys = [canonical(v) for v in result]
        require(len(keys) == len(set(keys)), "MMC_DUPLICATE_MEMBER", path)
        return sorted(result, key=canonical)
    elif t == "states":
        require(type(value) is list and 1 <= len(value) <= 512, "MMC_STATE_LIMIT", path)
        seen = set()
        for i, row in enumerate(value):
            p=path+f"[{i}]"; closed(row,{"target","state"},p)
            _shape(row["target"],{"type":"ref","kinds":["Actor","Asset"]},p+".target",refs)
            _pattern(row["state"],TOKEN,p+".state")
            require(row["target"] not in seen,"MMC_DUPLICATE_TARGET",p)
            seen.add(row["target"])
        return sorted(clone(value),key=lambda r:r["target"])
    elif t == "predicate":
        return _predicate(value,path,refs)
    else:
        raise MMCError("MMC_METAMODEL_UNSUPPORTED", path)
    return value


def observation_refs(rule: dict) -> list[str]:
    if rule["op"] == "eq":
        return [rule["observation"]]
    if rule["op"] in ("all", "any"):
        return [ref for child in rule["items"] for ref in observation_refs(child)]
    if rule["op"] == "not":
        return observation_refs(rule["item"])
    return []


def validate_model(value: object) -> dict:
    # Admit exact JSON types before Python equality, set construction or key interpolation.
    canonical(value, limit=2*1024*1024)
    closed(value, {"schema","model_id","revision","domain","profile_ref","objects","initial_states"}, "$")
    require(value["schema"] == "mmc.model.t1", "MMC_SCHEMA_UNSUPPORTED", "$.schema")
    _pattern(value["model_id"],ID,"$.model_id")
    require(type(value["revision"]) is int and 1 <= value["revision"] < 2**63, "MMC_REVISION", "$.revision")
    require(value["domain"] in ("identity","storage","policy","workload"), "MMC_DOMAIN_MODEL", "$.domain")
    require(canonical(value["profile_ref"]) == canonical(profile_reference()), "MMC_PROFILE_PIN_MISMATCH", "$.profile_ref")
    require(type(value["objects"]) is list and 1 <= len(value["objects"]) <= 512, "MMC_OBJECT_LIMIT", "$.objects")
    result=clone(value); refs=[]; objects={}; definitions=contract("metamodel")["kinds"]
    for i, item in enumerate(result["objects"]):
        p=f"$.objects[{i}]"
        closed(item,{"id","kind","provenance","attributes"},p)
        _pattern(item["id"],ID,p+".id")
        require(item["id"] not in objects,"MMC_DUPLICATE_ID",p)
        require(type(item["kind"]) is str and item["kind"] in definitions,"MMC_KIND_UNSUPPORTED",p)
        prov=item["provenance"]
        closed(prov,{"source_ref","source_digest","observed_at","epistemic","note"},p+".provenance")
        require(type(prov["source_ref"]) is str and 1<=len(prov["source_ref"].encode('utf-8'))<=4096,"MMC_PROVENANCE",p)
        _pattern(prov["source_digest"],HEX,p+".source_digest")
        require(type(prov["observed_at"]) is int and 0<=prov["observed_at"]<2**63,"MMC_PROVENANCE",p)
        require(prov["epistemic"] in ("ASSERTED","UNKNOWN") and type(prov["note"]) is str,"MMC_PROVENANCE",p)
        defs=definitions[item["kind"]]
        closed(item["attributes"],set(defs),p+".attributes")
        item["attributes"]={k:_shape(item["attributes"][k],s,p+".attributes."+k,refs) for k,s in defs.items()}
        objects[item["id"]]=item
    transitions=[x for x in objects.values() if x["kind"]=='Transition']
    require(1 <= len(transitions) <=128,"MMC_TRANSITION_LIMIT")
    result["initial_states"]=_shape(result["initial_states"],{"type":"states"},"$.initial_states",refs)
    for ident,kinds,path in refs:
        require(ident in objects,"MMC_REFERENCE_MISSING",path,ident)
        require(objects[ident]["kind"] in kinds,"MMC_REFERENCE_KIND",path,ident)
    used_effects=[]; used_obligations=set(); pairs=set()
    for item in objects.values():
        a=item["attributes"]; p=item["id"]; kind=item["kind"]
        if kind=='Observation':
            require(a['status']!='UNKNOWN' or a['value'] is None,"MMC_UNKNOWN_VALUE",p)
            require((a['measured_at'] is None)==(a['valid_until'] is None),"MMC_INTERVAL",p)
            require(a['measured_at'] is None or a['measured_at']<=a['valid_until'],"MMC_INTERVAL",p)
            for e in a['evidence_refs']:
                require(objects[e]['attributes']['subject']==a['subject'],"MMC_EVIDENCE_SCOPE",p,e)
        elif kind=='Obligation':
            for obs in observation_refs(a['rule']):
                require(objects[obs]['attributes']['subject']==a['subject'],"MMC_OBSERVATION_SCOPE",p,obs)
        elif kind=='Dependency':
            require(a['before']!=a['after'],"MMC_ORDER_SELF",p)
            pair=(a['before'],a['after'])
            require(pair not in pairs,"MMC_DUPLICATE_DEPENDENCY",p)
            pairs.add(pair)
        elif kind=='Flow':
            members=set(objects[a['cohort']]['attributes']['members'])
            require({a['source'],a['target'],a['asset']} <= members,"MMC_FLOW_SCOPE",p)
        elif kind=='Effect':
            auth=objects[a['authority']]['attributes']
            require(a['operation'] in auth['operations'],"MMC_DECLARED_OPERATION_SCOPE",p)
    for item in transitions:
        a=item['attributes'];p=item['id']; cohort=objects[a['cohort']]['attributes']
        before={r['target']:r['state'] for r in a['from_states']}; after={r['target']:r['state'] for r in a['to_states']}
        require(set(before)==set(after),"MMC_STATE_TARGETS",p)
        require(set(before)<=set(cohort['members']),"MMC_COHORT_SCOPE",p)
        require(any(before[k]!=after[k] for k in before),"MMC_NOOP_TRANSITION",p)
        flow_ids={f['id'] for f in objects.values() if f['kind']=='Flow' and f['attributes']['cohort']==a['cohort']}
        scope=set(cohort['members'])|flow_ids|{a['cohort']}|set(a['effects'])|set(a['policies'])|set(cohort['policy_refs'])
        needs=set(a['requires'])
        for eid in a['effects']:
            ef=objects[eid]['attributes'];used_effects.append(eid);needs.update(ef['requires'])
            require(ef['target'] in before,"MMC_EFFECT_SCOPE",p,eid)
            require(ef['expected_before']==before[ef['target']] and ef['expected_after']==after[ef['target']],"MMC_EFFECT_STATES",p,eid)
        for oid in needs:
            require(objects[oid]['attributes']['subject'] in scope,"MMC_OBLIGATION_SCOPE",p,oid)
            used_obligations.add(oid)
    effect_ids={o['id'] for o in objects.values() if o['kind']=='Effect'}
    require(len(used_effects)==len(set(used_effects)) and set(used_effects)==effect_ids,"MMC_EFFECT_OWNERSHIP")
    obligation_ids={o['id'] for o in objects.values() if o['kind']=='Obligation'}
    require(used_obligations==obligation_ids,"MMC_ORPHAN_OBLIGATION")
    result['objects']=sorted(objects.values(),key=lambda o:o['id'])
    return result
