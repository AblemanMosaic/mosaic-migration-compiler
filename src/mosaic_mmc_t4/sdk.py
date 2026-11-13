"""Host-installed extensions with exact contracts and finite qualification witnesses.

This module does not sandbox Python. The host explicitly supplies callable code; no
input string or descriptor can import code. Data ABIs expose installed handlers only.
"""
from __future__ import annotations
import inspect
from pathlib import Path
from .common import *


@typed
def validate_descriptor(value):
    closed(value,{"schema","id","version","kind","input_schema","output_schema","max_bytes","claim_ceiling","effects"})
    require(value["schema"]=="mmc.extension-descriptor.t4","MMC_T4_DESCRIPTOR_SCHEMA")
    for k in ("id","version","input_schema","output_schema"): token(value[k])
    require(value["kind"] in ("profile","observer"),"MMC_T4_EXTENSION_KIND")
    integer(value["max_bytes"],1,1048576);text(value["claim_ceiling"],1024)
    require(value["effects"]=="NONE_DECLARED_TRUSTED_HOST_CODE", "MMC_T4_EXTENSION_EFFECTS")
    return clone(value)


def handler_identity(handler):
    require(inspect.isfunction(handler) and handler.__module__ not in ("__main__",),"MMC_T4_HANDLER_TYPE")
    source=inspect.getsourcefile(handler)
    require(source is not None and Path(source).is_file() and not Path(source).is_symlink(),"MMC_T4_HANDLER_SOURCE")
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


@typed
def invoke(handler,descriptor,value):
    canonical(value,limit=descriptor["max_bytes"])
    require(type(value) is dict and value.get("schema")==descriptor["input_schema"],"MMC_T4_EXTENSION_INPUT")
    result=handler(clone(value))
    canonical(result,limit=descriptor["max_bytes"])
    require(type(result) is dict and result.get("schema")==descriptor["output_schema"],"MMC_T4_EXTENSION_OUTPUT")
    require(result.get("authority_effect")=="NONE", "MMC_T4_EXTENSION_AUTHORITY")
    return clone(result)


class Registry:
    def __init__(self): self._handlers={}

    def qualify(self,descriptor,handler,cases,*,expected_descriptor_root,expected_handler_hash):
        d=validate_descriptor(descriptor);hashhex(expected_descriptor_root);hashhex(expected_handler_hash)
        require(digest("descriptor",d)==expected_descriptor_root,"MMC_T4_DESCRIPTOR_PIN")
        require(handler_identity(handler)==expected_handler_hash,"MMC_T4_HANDLER_PIN")
        require(type(cases) is list and 2<=len(cases)<=64,"MMC_T4_QUALIFICATION_CASES")
        ids=set();results=[];positive=False;negative=False
        for case in cases:
            closed(case,{"id","input","expected"});token(case["id"])
            require(case["id"] not in ids,"MMC_T4_QUALIFICATION_DUPLICATE");ids.add(case["id"])
            expected=case["expected"]
            require(type(expected) is dict and ((set(expected)=={"ok","result"} and expected["ok"] is True) or
                  (set(expected)=={"ok","error"} and expected["ok"] is False)),"MMC_T4_QUALIFICATION_EXPECTED")
            try: actual={"ok":True,"result":invoke(handler,d,case["input"])}
            except MMCError as exc: actual={"ok":False,"error":exc.code}
            require(canonical(actual)==canonical(expected),"MMC_T4_QUALIFICATION_MISMATCH",case["id"])
            positive|=actual["ok"];negative|=not actual["ok"]
            results.append({"id":case["id"],"status":"PASS"})
        require(positive and negative,"MMC_T4_QUALIFICATION_PAIR")
        require(handler_identity(handler)==expected_handler_hash,"MMC_T4_HANDLER_CHANGED")
        ref={"id":d["id"],"version":d["version"],"descriptor_root":expected_descriptor_root,"handler_hash":expected_handler_hash}
        require(d["id"] not in self._handlers,"MMC_T4_EXTENSION_EXISTS")
        self._handlers[d["id"]]=(d,handler,clone(ref))
        return envelope("qualification",{"schema":"mmc.extension-qualification.t4","reference":ref,
                  "cases":results,"cases_root":digest("qualification",cases),"status":"PASS_SCOPED_FIXTURES",
                  "independent_review":"NOT_PERFORMED","sandbox":"NOT_PROVIDED",**BOUNDARY})

    def call(self,reference,value):
        closed(reference,{"id","version","descriptor_root","handler_hash"})
        token(reference["id"])
        require(reference["id"] in self._handlers,"MMC_T4_EXTENSION_NOT_INSTALLED")
        d,h,ref=self._handlers[reference["id"]]
        require(canonical(reference)==canonical(ref),"MMC_T4_EXTENSION_REFERENCE")
        require(handler_identity(h)==ref["handler_hash"],"MMC_T4_HANDLER_CHANGED")
        return invoke(h,d,value)

    def descriptors(self):
        return [{"descriptor":clone(d),"reference":clone(ref)} for _,(d,h,ref) in sorted(self._handlers.items())]
