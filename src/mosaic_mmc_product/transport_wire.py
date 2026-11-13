"""Closed local adapter wire primitives; no process or effect selection."""
from __future__ import annotations

import hashlib
import hmac
import re
import os
import stat
from pathlib import Path

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require

PROTOCOL = "mmc.adapter-transport.v1"
MAX_FRAME = 2 * 1024 * 1024
MAX_BOOTSTRAP = 16 * 1024
MAX_STDERR = 64 * 1024
MAX_STDOUT = 2 * (MAX_FRAME + 1) + 1
TRANSCRIPT_RESERVATION = MAX_STDOUT + MAX_STDERR + MAX_FRAME + 1
BACKENDS = {"disposable.sqlite.v1": ("adapter.py", "DisposableSQLiteAdapter"),
            "sqlite.table-migration.v1": ("sqlite_target.py", "SQLiteTargetAdapter")}


def hex256(value):
    require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
            "MMC_TRANSPORT_DIGEST")
    return value


def closed(value, fields):
    require(type(value) is dict and set(value) == set(fields), "MMC_TRANSPORT_FIELDS")


def frame(value, *, limit=MAX_FRAME):
    raw = canonical(value)
    require(len(raw) <= limit, "MMC_TRANSPORT_FRAME_LIMIT")
    return raw + b"\n"


def parse_frame(raw, *, limit=MAX_FRAME):
    require(type(raw) is bytes and 0 < len(raw) <= limit + 1 and raw.endswith(b"\n"),
            "MMC_TRANSPORT_FRAME_LIMIT")
    return decode(raw[:-1], canonical_only=True, limit=limit)


def sign(key, label, body):
    require(type(key) is bytes and len(key) == 32 and label in {"challenge", "request", "response"},
            "MMC_TRANSPORT_KEY")
    mac = hmac.new(key, PROTOCOL.encode() + b"\0" + label.encode() + b"\0" + canonical(body),
                   hashlib.sha256).hexdigest()
    return {"body": body, "mac": mac}


def authenticate(key, label, packet):
    closed(packet, {"body", "mac"})
    hex256(packet["mac"])
    expected = sign(key, label, packet["body"])["mac"]
    require(hmac.compare_digest(packet["mac"], expected), "MMC_TRANSPORT_AUTHENTICATION")
    return packet["body"]


def safe_host_path(path, *, directory=False):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()),
                "MMC_TRANSPORT_IMPLEMENTATION_PATH")
    require(path.is_dir() if directory else path.is_file(), "MMC_TRANSPORT_IMPLEMENTATION_PATH")
    return path


def execution_pin(backend):
    """Hash the shipped Python/data closure, independently on both sides.

    The CPython executable/stdlib and optional installed dependencies are host
    prerequisites; the release verifier binds their offline installation separately.
    """
    require(backend in BACKENDS, "MMC_TRANSPORT_BACKEND")
    root = safe_host_path(Path(__file__).absolute().parent.parent, directory=True)
    rows = []
    def walk(directory):
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda value: value.name):
                path = Path(entry.path)
                require(not entry.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                        "MMC_TRANSPORT_IMPLEMENTATION_PATH")
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    if entry.name != "__pycache__":
                        walk(path)
                else:
                    require(stat.S_ISREG(mode), "MMC_TRANSPORT_IMPLEMENTATION_PATH")
                    rows.append({"path": path.relative_to(root).as_posix(),
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for package in ("mosaic_mmc", "mosaic_mmc_t2", "mosaic_mmc_t3", "mosaic_mmc_product"):
        walk(safe_host_path(root / package, directory=True))
    return hashlib.sha256(canonical({"backend": backend, "files": sorted(rows, key=lambda row: row["path"])})).hexdigest()


def session_id(host_nonce, worker_nonce, implementation_pin):
    return hashlib.sha256(canonical({"protocol": PROTOCOL, "host_nonce": hex256(host_nonce),
                                     "worker_nonce": hex256(worker_nonce),
                                     "implementation_pin": hex256(implementation_pin)})).hexdigest()


def workload_summary(value):
    """Bounded wire projection; never canonicalize the entire row inventory.

    Local adapters retain their full snapshot API. Rows arrive in adapter order;
    each canonical row is framed with an unsigned 64-bit big-endian byte length.
    The collection name and domain separate inventories and future encodings.
    """
    require(type(value) is dict and set(value) in (
        {"control", "legacy", "new", "effect_count"},
        {"enrollment_root", "control", "legacy", "new", "effect_count"}),
        "MMC_TRANSPORT_WORKLOAD_SHAPE")
    inventories = {}
    for name in ("legacy", "new"):
        rows = value[name]
        require(type(rows) is list, "MMC_TRANSPORT_WORKLOAD_SHAPE")
        digest = hashlib.sha256(b"MMC/ADAPTER/ROWS/v1\0" + name.encode("ascii") + b"\0")
        for row in rows:
            raw = canonical(row)
            digest.update(len(raw).to_bytes(8, "big")); digest.update(raw)
        inventories[name] = {"row_count": len(rows), "rows_sha256": digest.hexdigest()}
    return {"schema": "mmc.adapter-workload-summary.v1", "control": value["control"],
            "effect_count": value["effect_count"], "enrollment_root": value.get("enrollment_root"),
            "inventories": inventories,
            "digest_algorithm": "SHA256_DOMAIN_AND_U64_BE_LENGTH_PREFIXED_CANONICAL_ROWS_V1",
            "row_data": "OMITTED_BOUNDED_WIRE_SUMMARY", "authority_effect": "NONE"}


def transport_manifest():
    return {"schema": "mmc.adapter-transport-manifest.v1", "protocol": PROTOCOL,
            "authentication": "FRESH_ANONYMOUS_PIPE_SECRET_HMAC_SHA256_MUTUAL_CHALLENGE",
            "channel": "ONE_RPC_PER_OWNED_STDIO_PROCESS", "max_frame_bytes": MAX_FRAME,
            "max_stderr_bytes": MAX_STDERR, "backends": sorted(BACKENDS),
            "optional_transcript_custody": "OPT_IN_BOUNDED_RAW_REQUEST_STDOUT_STDERR_NO_BOOTSTRAP_NO_DECLASSIFICATION",
            "operations": ["describe", "snapshot", "lookup", "apply", "workload_snapshot"],
            "workload_snapshot_result": "mmc.adapter-workload-summary.v1",
            "workload_inventory": "ROW_COUNTS_AND_STREAMED_LENGTH_PREFIXED_CANONICAL_ROW_DIGESTS_NO_PAYLOAD",
            "automatic_apply_retry": False, "uncertain_apply": "CONTROLLER_UNKNOWN_RECONCILE_BACKEND_LEDGER",
            "process_selection": "FIXED_SHIPPED_WORKER_HOST_ENROLLED_BACKEND",
            "isolation": "ISOLATED_CPYTHON_STARTUP_EXPLICIT_IMPORT_ROOTS_NOT_OS_SANDBOX",
            "host_assumption": "COOPERATIVE_LOCAL_HOST_SAME_USER_PRIVATE_PIPE",
            "authority_effect": "NONE"}
