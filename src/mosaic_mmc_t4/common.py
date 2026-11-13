"""Explicit T4 limits and typed commitments; no ambient effects."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from mosaic_mmc import MMCError, canonical, decode
from mosaic_mmc.codec import clone
from mosaic_mmc.errors import require
from ._pins import CONTRACT_ROOT

MAX_INPUT = 2 * 1024 * 1024
MAX_ORDER = 256 * 1024
BOUNDARY = {"profile": "T4-I1", "authority_effect": "NONE", "native_pippi": "NOT_BOUND",
            "production_authorization": "NOT_ESTABLISHED", "signature": "NOT_SIGNED"}
DOMAINS = {"contract", "snapshot", "view", "work", "submission", "review", "context", "capture",
           "descriptor", "qualification", "profile", "handoff", "export", "realization"}


def digest(domain: str, value: object) -> str:
    require(domain in DOMAINS, "MMC_T4_DOMAIN")
    return hashlib.sha256(b"MMC/T4/" + domain.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def closed(value, keys, where="$" ):
    require(type(value) is dict and set(value) == set(keys), "MMC_T4_FIELDS", where)


def integer(value, low=0, high=2**63-1):
    require(type(value) is int and low <= value <= high, "MMC_T4_INTEGER")
    return value


def token(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", value) is not None,
            "MMC_T4_TOKEN")
    return value


def hashhex(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "MMC_T4_DIGEST")
    return value


def text(value, limit=4096):
    require(type(value) is str and len(value) <= limit, "MMC_T4_TEXT_LIMIT")
    canonical(value)
    return value


def envelope(domain, body):
    raw = canonical(body, limit=MAX_INPUT)
    return {"body": decode(raw, limit=MAX_INPUT), "root": digest(domain, body)}


def unwrap(domain, value):
    closed(value, {"body", "root"})
    hashhex(value["root"])
    require(value["root"] == digest(domain, value["body"]), "MMC_T4_ROOT_MISMATCH")
    return clone(value["body"])


def identity():
    root = Path(__file__).resolve().parent
    rows = []
    for p in sorted(root.rglob("*"), key=lambda x: x.relative_to(root).as_posix()):
        if p.is_file() and "__pycache__" not in p.parts:
            require(not p.is_symlink(), "MMC_T4_RUNTIME_LINK")
            if p.suffix in (".py", ".json", ".md"):
                rows.append({"path": p.relative_to(root).as_posix(),
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    return digest("realization", {"contract": CONTRACT_ROOT, "files": rows})


def typed(fn):
    """Normalize malformed data errors, never catch interrupts or claim failed work succeeded."""
    from functools import wraps
    @wraps(fn)
    def call(*args,**kwargs):
        try:return fn(*args,**kwargs)
        except MMCError:raise
        except (KeyError,TypeError,ValueError,IndexError,AttributeError,RecursionError) as exc:
            raise MMCError('MMC_T4_INPUT_INVALID',detail=type(exc).__name__) from exc
    return call
