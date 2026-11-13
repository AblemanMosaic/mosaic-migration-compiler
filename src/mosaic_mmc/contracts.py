"""Installed, pinned, data-only contracts. No document-driven handler registration."""
from __future__ import annotations
import hashlib
import importlib.resources as resources
from pathlib import Path
from functools import lru_cache
from .codec import canonical, decode, digest, clone
from .errors import require
from ._pins import PROGRAM_ROOT, PROFILE_ROOT, VERSION, ENGINEERING_REVISION


def _raw(name: str) -> bytes:
    return resources.files("mosaic_mmc").joinpath("data", name).read_bytes()


def _json(name: str) -> dict:
    value = decode(_raw(name))
    require(type(value) is dict, "MMC_CONTRACT_INVALID")
    return value


@lru_cache(maxsize=1)
def _checked() -> dict:
    envelope = _json("program-freeze.json")
    require(set(envelope) == {"body", "root"}, "MMC_CONTRACT_INVALID")
    require(digest("program-freeze", envelope["body"]) == envelope["root"] == PROGRAM_ROOT,
            "MMC_PROGRAM_PIN_MISMATCH")
    for row in envelope["body"]["files"]:
        data = _raw(Path(row["path"]).name)
        require(type(row["bytes"]) is int and len(data) == row["bytes"] and
                hashlib.sha256(data).hexdigest() == row["sha256"], "MMC_CONTRACT_HASH", row["path"])
    profile = _json("profile.json")
    require(digest("foundation-profile", profile["body"]) == profile["sha256"] == PROFILE_ROOT,
            "MMC_PROFILE_PIN_MISMATCH")
    names = {"constitution/FOUNDATION-CONTRACT.json":"FOUNDATION-CONTRACT.json",
             "src/mosaic_mmc/data/metamodel.json":"metamodel.json",
             "schemas/model.t1.schema.json":"model.schema.json",
             "docs/architecture/PROTOCOL-T1.md":"PROTOCOL-T1.md"}
    require({r["path"] for r in profile["body"]["references"]} == set(names), "MMC_CONTRACT_INVALID")
    for row in profile["body"]["references"]:
        require(hashlib.sha256(_raw(names[row["path"]])).hexdigest() == row["sha256"],
                "MMC_CONTRACT_HASH", row["path"])
    return {"profile":profile["body"], "metamodel":_json("metamodel.json"),
            "foundation":_json("FOUNDATION-CONTRACT.json"),
            "program":_json("PROGRAM.json"), "cases":_json("ACCEPTANCE.json"),
            "requirements":_json("REQUIREMENTS.json")}


def contract(name: str) -> dict:
    require(name in _checked(), "MMC_CONTRACT_UNKNOWN")
    return clone(_checked()[name])


def profile_reference() -> dict:
    _checked()
    return {"id":"mmc.foundation", "version":"1", "sha256":PROFILE_ROOT}


def realization_identity() -> str:
    # The package tree is trusted host code. Hashes identify it; they do not sandbox it.
    root = Path(__file__).resolve().parent
    rows = []
    for p in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        rel = p.relative_to(root).as_posix()
        if "__pycache__" in p.parts or not p.is_file():
            continue
        if p.suffix != ".py" and not rel.startswith("data/"):
            continue
        require(not p.is_symlink(), "MMC_RUNTIME_SYMLINK", rel)
        content = p.read_bytes()
        rows.append({"path":rel, "bytes":len(content), "sha256":hashlib.sha256(content).hexdigest()})
    return digest("compiler-realization", {"package":"mosaic_mmc", "version":VERSION,
                  "revision":ENGINEERING_REVISION, "files":rows})


def capabilities() -> dict:
    return {"schema":"mmc.capabilities.t1", "distribution":"mosaic-migration-compiler",
            "version":VERSION, "revision":ENGINEERING_REVISION,
            "profile":profile_reference(), "program_root":PROGRAM_ROOT,
            "operations":["model-validate","compile","verify-ir","capabilities","program-inspect"],
            "effects":"NONE", "controller":"NOT_IMPLEMENTED", "native_pippi":"NOT_BOUND",
            "domain_profiles":"REPRESENTATION_EXAMPLES_NOT_EXECUTABLE_DOMAIN_EVALUATORS"}


def program_inspect() -> dict:
    return {"schema":"mmc.program-inspection.t1", "program_root":PROGRAM_ROOT,
            "requirement_count":len(contract("requirements")["requirements"]),
            "acceptance_count":len(contract("cases")["cases"]),
            "turn1_cases":[c["id"] for c in contract("cases")["cases"] if c["gate"] == "T1"],
            "native_pippi":"NOT_BOUND", "authority_effect":"NONE",
            "public_release":"NOT_CLEARED", "product_acceptance":"NOT_ESTABLISHED_BY_INSPECTION"}
