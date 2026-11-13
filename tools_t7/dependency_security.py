"""Explicit, dated OSV package-version observations and pure offline verification.

Only audit() performs network IO. A snapshot is unsigned observation evidence:
its integrity needs an independently accepted enclosing lock root. No result
claims vulnerability absence, exploitability, native execution or approval.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.request


SERVICE_URL = "https://api.osv.dev/v1/querybatch"
SCHEMA = "mmc.dependency-security-snapshot.v1"
PACKAGE_NAMES = frozenset({"pip", "cryptography", "cffi", "pycparser", "jsonschema", "attrs",
    "jsonschema-specifications", "referencing", "rpds-py", "typing-extensions", "blake3", "pyyaml", "pillow"})
SCOPE = "CURRENT_OSV_PACKAGE_VERSION_MATCHES_AT_SCAN_TIME_NOT_ABSOLUTE_SAFETY_OR_EXECUTION_APPROVAL"
TRUST = "UNSIGNED_OBSERVATION_REQUIRES_OWNER_ACCEPTED_OUTER_LOCK_ROOT"
MAX_REQUEST = 32 * 1024
MAX_RESPONSE = 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]


class DependencySecurityError(ValueError):
    def __init__(self, code, detail="", *, snapshot=None):
        self.code, self.snapshot = code, snapshot
        super().__init__(code + (":" + str(detail) if detail else ""))


def require(condition, code, detail=""):
    if not condition:
        raise DependencySecurityError(code, detail)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rooted(body):
    return {**body, "receipt_root": sha(canonical(body))}


def _decode(raw, limit):
    require(type(raw) is bytes and len(raw) <= limit, "MMC_DEPENDENCY_SECURITY_BYTE_LIMIT")
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "MMC_DEPENDENCY_SECURITY_DUPLICATE_JSON")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except DependencySecurityError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise DependencySecurityError("MMC_DEPENDENCY_SECURITY_JSON", type(error).__name__) from error


def _pins(pins):
    require(type(pins) is dict and set(pins) == PACKAGE_NAMES, "MMC_DEPENDENCY_SECURITY_PIN_SET")
    require(all(type(version) is str and re.fullmatch(r"[A-Za-z0-9_.!+-]{1,64}", version)
                for version in pins.values()), "MMC_DEPENDENCY_SECURITY_PIN_VERSION")
    return {name: pins[name] for name in sorted(pins)}


def _request(pins):
    return canonical({"queries": [{"package": {"ecosystem": "PyPI", "name": name}, "version": version}
                                   for name, version in pins.items()]})


def _results(response_raw, pins):
    response = _decode(response_raw, MAX_RESPONSE)
    require(type(response) is dict and set(response) == {"results"} and type(response["results"]) is list
            and len(response["results"]) == len(pins), "MMC_DEPENDENCY_SECURITY_RESPONSE_COUNT")
    rows = []
    for index, ((name, version), result) in enumerate(zip(pins.items(), response["results"])):
        require(type(result) is dict and set(result) <= {"vulns", "next_page_token"}, "MMC_DEPENDENCY_SECURITY_RESPONSE_SHAPE")
        require(result.get("next_page_token", "") == "", "MMC_DEPENDENCY_SECURITY_INCOMPLETE_RESPONSE")
        vulns = result.get("vulns", [])
        require(type(vulns) is list and len(vulns) <= 10000, "MMC_DEPENDENCY_SECURITY_RESPONSE_SHAPE")
        identifiers = []
        for vuln in vulns:
            require(type(vuln) is dict and {"id"} <= set(vuln) <= {"id", "modified"}
                    and type(vuln["id"]) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", vuln["id"])
                    and ("modified" not in vuln or type(vuln["modified"]) is str), "MMC_DEPENDENCY_SECURITY_ADVISORY_SHAPE")
            identifiers.append(vuln["id"])
        require(len(identifiers) == len(set(identifiers)), "MMC_DEPENDENCY_SECURITY_DUPLICATE_ADVISORY")
        rows.append({"query_index": index, "package": name, "version": version, "advisory_ids": sorted(identifiers)})
    return rows


def _snapshot(pins, request_raw, response_raw, timestamp):
    rows = _results(response_raw, pins)
    count = sum(len(row["advisory_ids"]) for row in rows)
    return rooted({"schema": SCHEMA, "service_url": SERVICE_URL, "scan_timestamp_utc": timestamp,
        "pins": pins, "query_count": len(pins), "result_count": len(rows), "http_status": 200,
        "request_base64": base64.b64encode(request_raw).decode("ascii"),
        "response_base64": base64.b64encode(response_raw).decode("ascii"),
        "request_sha256": sha(request_raw), "response_sha256": sha(response_raw),
        "results": rows, "advisory_record_count": count,
        "status": "NO_MATCHES_AS_OF_SCAN" if count == 0 else "KNOWN_VULNERABILITIES_FOUND",
        "scope": SCOPE, "trust_boundary": TRUST, "authority_effect": "NONE"})


def verify_snapshot(snapshot, pins):
    """Pure offline checks; no wall-clock age policy and no network requests.

    The caller must accept the enclosing lock root independently. Rehashing an
    attacker-authored snapshot does not establish that OSV supplied its bytes.
    """
    pins = _pins(pins)
    keys = {"schema", "service_url", "scan_timestamp_utc", "pins", "query_count", "result_count", "http_status",
        "request_base64", "response_base64", "request_sha256", "response_sha256", "results", "advisory_record_count",
        "status", "scope", "trust_boundary", "authority_effect", "receipt_root"}
    require(type(snapshot) is dict and set(snapshot) == keys, "MMC_DEPENDENCY_SECURITY_SNAPSHOT_SHAPE")
    timestamp = snapshot["scan_timestamp_utc"]
    require(type(timestamp) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", timestamp),
            "MMC_DEPENDENCY_SECURITY_TIMESTAMP")
    try:
        datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise DependencySecurityError("MMC_DEPENDENCY_SECURITY_TIMESTAMP") from error
    for key, limit in (("request_base64", MAX_REQUEST), ("response_base64", MAX_RESPONSE)):
        require(type(snapshot[key]) is str and len(snapshot[key]) <= 4 * ((limit + 2) // 3), "MMC_DEPENDENCY_SECURITY_BYTE_LIMIT")
    try:
        request_raw = base64.b64decode(snapshot["request_base64"], validate=True)
        response_raw = base64.b64decode(snapshot["response_base64"], validate=True)
    except (ValueError, UnicodeError) as error:
        raise DependencySecurityError("MMC_DEPENDENCY_SECURITY_BASE64") from error
    require(len(request_raw) <= MAX_REQUEST and request_raw == _request(pins), "MMC_DEPENDENCY_SECURITY_QUERY_BINDING")
    expected = _snapshot(pins, request_raw, response_raw, timestamp)
    # Exact serialization also prevents bool/int aliases in count fields.
    try:
        matches = canonical(snapshot) == canonical(expected)
    except (ValueError, TypeError, RecursionError) as error:
        raise DependencySecurityError("MMC_DEPENDENCY_SECURITY_SNAPSHOT_SHAPE", type(error).__name__) from error
    require(matches, "MMC_DEPENDENCY_SECURITY_SNAPSHOT_BINDING")
    if expected["advisory_record_count"]:
        raise DependencySecurityError("MMC_DEPENDENCY_SECURITY_KNOWN_VULNERABILITIES",
                                      expected["advisory_record_count"], snapshot=expected)
    return snapshot


def _fresh_output(output):
    output = Path(output).absolute()
    require(not output.exists() and not output.resolve().is_relative_to(ROOT), "MMC_DEPENDENCY_SECURITY_CUSTODY_EXISTS_OR_INSIDE_SOURCE")
    for parent in output.parents:
        require(not parent.is_symlink() and not (hasattr(parent, "is_junction") and parent.is_junction()), "MMC_DEPENDENCY_SECURITY_OUTPUT_LINK")
    output.mkdir(parents=True)
    return output


def audit(pins, *, output=None, timeout=60):
    """Explicit network action, using only stdlib and the fixed official OSV URL.

    output, when supplied, must be a fresh directory outside the source tree.
    A rejection carries the observed snapshot on DependencySecurityError.snapshot.
    """
    pins = _pins(pins)
    request_raw = _request(pins)
    output = None if output is None else _fresh_output(output)
    terminal = {"schema": "mmc.dependency-security-audit.v1", "status": "RUNNING", "service_url": SERVICE_URL,
                "pins": pins, "request_sha256": sha(request_raw), "authority_effect": "NONE"}
    if output is not None:
        (output / "request.json").write_bytes(request_raw)
        (output / "AUDIT-TERMINAL.json").write_bytes(canonical(rooted(terminal)))
    snapshot = None
    try:
        request = urllib.request.Request(SERVICE_URL, data=request_raw,
            headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            require(response.status == 200 and response.geturl() == SERVICE_URL, "MMC_DEPENDENCY_SECURITY_HTTP_ORIGIN")
            response_raw = response.read(MAX_RESPONSE + 1)
        terminal["response_sha256"] = sha(response_raw)
        if output is not None:
            (output / "response.json").write_bytes(response_raw)
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        snapshot = _snapshot(pins, request_raw, response_raw, timestamp)
        if output is not None:
            (output / "SNAPSHOT.json").write_bytes(canonical(snapshot))
        verify_snapshot(snapshot, pins)
        terminal.update(status="NO_MATCHES_AS_OF_SCAN", snapshot_root=snapshot["receipt_root"], scan_timestamp_utc=timestamp)
    except BaseException as error:
        terminal.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        if snapshot is not None:
            terminal.update(snapshot_root=snapshot["receipt_root"], scan_timestamp_utc=snapshot["scan_timestamp_utc"])
        if isinstance(error, (OSError, urllib.error.URLError)):
            raise DependencySecurityError("MMC_DEPENDENCY_SECURITY_NETWORK", type(error).__name__) from error
        raise
    finally:
        if output is not None:
            (output / "AUDIT-TERMINAL.json").write_bytes(canonical(rooted(terminal)))
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pins-json", "--pinsjson", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="fresh custody directory; required for network audit")
    parser.add_argument("--verify-snapshot", type=Path, help="pure offline verification; never contacts OSV")
    args = parser.parse_args()
    pins = _decode(args.pins_json.read_bytes(), MAX_REQUEST)
    if args.verify_snapshot is not None:
        snapshot = verify_snapshot(_decode(args.verify_snapshot.read_bytes(), 4 * MAX_RESPONSE), pins)
        if args.out is not None:
            directory = _fresh_output(args.out)
            (directory / "VERIFIED-SNAPSHOT.json").write_bytes(canonical(snapshot))
    else:
        if args.out is None:
            parser.error("--out is required for a network audit")
        snapshot = audit(pins, output=args.out)
    print(canonical({key: snapshot[key] for key in ("schema", "receipt_root", "scan_timestamp_utc", "status", "scope", "authority_effect")}).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
