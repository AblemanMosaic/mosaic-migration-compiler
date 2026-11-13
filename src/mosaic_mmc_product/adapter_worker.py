"""Fixed worker for one authenticated, host-enrolled adapter RPC.

There are no command-line target/import arguments, network listeners or worker
creation/enrollment operations. Bootstrap secrets arrive only through stdin.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets
import sys
import time

from mosaic_mmc import canonical, MMCError
from mosaic_mmc.errors import require
from .transport_wire import (PROTOCOL, BACKENDS, MAX_FRAME, MAX_BOOTSTRAP, authenticate,
                             closed, execution_pin, frame, hex256, parse_frame, sign, session_id,
                             workload_summary)


def _backend(identifier, path):
    # Deliberately fixed registrations, never importlib or data-selected imports.
    require(identifier in BACKENDS, "MMC_TRANSPORT_BACKEND")
    if identifier == "disposable.sqlite.v1":
        from .adapter import DisposableSQLiteAdapter
        return DisposableSQLiteAdapter(Path(path))
    from .sqlite_target import SQLiteTargetAdapter
    return SQLiteTargetAdapter(Path(path))


def _read(limit=MAX_FRAME):
    return parse_frame(sys.stdin.buffer.readline(limit + 2), limit=limit)


def _send(key, kind, body):
    sys.stdout.buffer.write(frame(sign(key, kind, body)))
    sys.stdout.buffer.flush()


def execute(adapter, operation, arguments, *, allow_test_faults):
    if operation == "describe":
        closed(arguments, set())
        return {"descriptor": adapter.descriptor(), "identity": adapter.identity,
                "model_adapter": adapter.model_adapter}
    if operation == "snapshot":
        closed(arguments, {"targets"})
        return adapter.snapshot(arguments["targets"])
    if operation == "lookup":
        closed(arguments, {"operation_id", "request_root"})
        return adapter.lookup(arguments["operation_id"], arguments["request_root"])
    if operation == "workload_snapshot":
        closed(arguments, set())
        return workload_summary(adapter.workload_snapshot())
    require(operation == "apply", "MMC_TRANSPORT_OPERATION")
    closed(arguments, {"request", "fault"})
    fault = arguments["fault"]
    require(fault is None or allow_test_faults, "MMC_TRANSPORT_TEST_FAULT_DISABLED")
    require(fault in (None, "before", "lost_ack", "crash_after", "transport.delay-before-apply",
                      "transport.delay-after-apply", "transport.crash-after-apply"),
            "MMC_TRANSPORT_FAULT")
    if fault == "transport.delay-before-apply":
        time.sleep(5)
    value = adapter.apply(arguments["request"], fault=None if fault == "crash_after" or
                          type(fault) is str and fault.startswith("transport.") else fault)
    if fault == "transport.delay-after-apply":
        time.sleep(5)
    if fault in ("crash_after", "transport.crash-after-apply"):
        os._exit(73)
    return value


def main():
    boot = _read(MAX_BOOTSTRAP)
    closed(boot, {"protocol", "secret", "host_nonce", "backend", "target_path",
                  "implementation_pin", "expected_descriptor", "allow_test_faults"})
    require(boot["protocol"] == PROTOCOL and type(boot["target_path"]) is str and
            type(boot["allow_test_faults"]) is bool, "MMC_TRANSPORT_BOOTSTRAP")
    key = bytes.fromhex(hex256(boot["secret"]))
    host_nonce = hex256(boot["host_nonce"])
    pin = execution_pin(boot["backend"])
    require(pin == boot["implementation_pin"], "MMC_TRANSPORT_IMPLEMENTATION_PIN")
    worker_nonce = secrets.token_hex(32)
    session = session_id(host_nonce, worker_nonce, pin)
    challenge = {"protocol": PROTOCOL, "session": session, "host_nonce": host_nonce,
                 "worker_nonce": worker_nonce, "implementation_pin": pin,
                 "backend": boot["backend"], "worker_pid": os.getpid()}
    _send(key, "challenge", challenge)
    request = authenticate(key, "request", _read())
    closed(request, {"protocol", "session", "sequence", "operation", "arguments", "challenge_root"})
    require(request["protocol"] == PROTOCOL and request["session"] == session and
            type(request["sequence"]) is int and request["sequence"] == 1 and
            request["challenge_root"] == hashlib.sha256(canonical(challenge)).hexdigest(),
            "MMC_TRANSPORT_REPLAY")
    # Exactly one call, with EOF proving that a repeated second request cannot be
    # appended to this authenticated session and executed later.
    require(sys.stdin.buffer.read(1) == b"", "MMC_TRANSPORT_EXTRA_REQUEST")
    reply = {"protocol": PROTOCOL, "session": session, "sequence": 1,
             "request_root": hashlib.sha256(canonical(request)).hexdigest(), "ok": False}
    try:
        adapter = _backend(boot["backend"], boot["target_path"])
        require(adapter.descriptor() == boot["expected_descriptor"], "MMC_TRANSPORT_ADAPTER_PIN")
        value = execute(adapter, request["operation"], request["arguments"],
                        allow_test_faults=boot["allow_test_faults"])
        reply.update(ok=True, result=value)
    except MMCError as error:
        reply["error"] = error.record()
    except Exception as error:
        # A backend exception never proves the effect was absent. The controller
        # will retain UNKNOWN and reconcile its exact request with the ledger.
        reply["error"] = {"code": "MMC_TRANSPORT_BACKEND_ERROR", "path": "$",
                          "detail": type(error).__name__}
    _send(key, "response", reply)
    return 0


def entrypoint():
    try:
        return main()
    except BaseException as error:
        # Never print bootstrap, secrets, requests or tracebacks.
        sys.stderr.write(getattr(error, "code", type(error).__name__) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(entrypoint())
