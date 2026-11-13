"""MMC-JSON-I64-UTF8-T1; deliberately NOT a claim of RFC 8785 JCS compatibility."""
from __future__ import annotations
import hashlib
import json
from .errors import MMCError, require

MAX_INPUT = 2 * 1024 * 1024
MAX_OUTPUT = 8 * 1024 * 1024
DOMAINS = frozenset({"program-freeze", "foundation-profile", "canonical-model",
    "compiler-realization", "workflow-ir", "compilation-receipt", "source-inventory",
    "evidence-run", "package-inventory"})


def _admit(value: object) -> None:
    count = 0
    active: set[int] = set()
    def walk(v: object, depth: int, path: str) -> None:
        nonlocal count
        count += 1
        require(count <= 50000, "MMC_NODE_LIMIT", path)
        require(depth <= 32, "MMC_DEPTH_LIMIT", path)
        t = type(v)
        if v is None or t is bool:
            return
        if t is int:
            require(-(2**63) <= v < 2**63, "MMC_INTEGER_RANGE", path)
            return
        if t is str:
            try:
                encoded = v.encode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise MMCError("MMC_UNICODE", path, "Unicode scalar strings required") from exc
            require(len(encoded) <= 65536, "MMC_STRING_LIMIT", path)
            return
        require(t in (dict, list), "MMC_VALUE_TYPE", path, "Only exact JSON types are admitted")
        require(id(v) not in active, "MMC_VALUE_CYCLE", path)
        active.add(id(v))
        try:
            if t is list:
                for i, item in enumerate(v):
                    walk(item, depth+1, f"{path}[{i}]")
            else:
                for key, item in v.items():
                    require(type(key) is str, "MMC_KEY_TYPE", path)
                    walk(key, depth+1, path + ".<key>")
                    # Diagnostic paths do not echo potentially huge or control-bearing keys.
                    walk(item, depth+1, path + ".<value>")
        finally:
            active.remove(id(v))
    walk(value, 0, "$")


def canonical(value: object, *, limit: int = MAX_OUTPUT) -> bytes:
    _admit(value)
    result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                        allow_nan=False).encode("utf-8")
    require(len(result) <= limit, "MMC_BYTE_LIMIT", "$", "Canonical value exceeds budget")
    return result


def decode(raw: bytes, *, canonical_only: bool = False, limit: int = MAX_INPUT) -> object:
    require(type(raw) is bytes, "MMC_BYTES_REQUIRED")
    require(len(raw) <= limit, "MMC_BYTE_LIMIT")
    def pairs(items: list[tuple[str, object]]) -> dict:
        result = {}
        for key, val in items:
            require(key not in result, "MMC_DUPLICATE_KEY")
            result[key] = val
        return result
    def invalid_number(value: str) -> object:
        raise MMCError("MMC_NUMBER_TYPE", "$", "Fractional, exponent and nonfinite forms refused")
    try:
        text = raw.decode("utf-8", errors="strict")
        require(not text.startswith("\ufeff"), "MMC_BOM_REFUSED")
        value = json.loads(text, object_pairs_hook=pairs, parse_float=invalid_number,
                           parse_constant=invalid_number)
    except MMCError:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise MMCError("MMC_JSON_INVALID", "$", type(exc).__name__) from exc
    encoded = canonical(value, limit=limit)
    if canonical_only:
        require(encoded == raw, "MMC_NOT_CANONICAL")
    return value


def clone(value: object) -> object:
    return decode(canonical(value), limit=MAX_OUTPUT)


def digest(domain: str, body: object) -> str:
    require(type(domain) is str and domain in DOMAINS, "MMC_DOMAIN_UNSUPPORTED")
    return hashlib.sha256(b"MMC/T1/" + domain.encode("ascii") + b"\0" + canonical(body)).hexdigest()
