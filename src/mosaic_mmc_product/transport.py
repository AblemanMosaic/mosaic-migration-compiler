"""Authenticated, bounded, one-call process transport for enrolled adapters."""
from __future__ import annotations

import hashlib
import base64
import io
import math
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import sysconfig
import threading
import time
import uuid

from mosaic_mmc import canonical, MMCError
from mosaic_mmc.codec import clone
from mosaic_mmc.errors import require
from mosaic_mmc_t3.storage import EffectAdapter
from mosaic_mmc_t3.common import safe_database
from .transport_wire import (PROTOCOL, BACKENDS, MAX_FRAME, MAX_BOOTSTRAP, MAX_STDERR, MAX_STDOUT,
                             TRANSCRIPT_RESERVATION,
                             authenticate, closed, execution_pin, frame, hex256,
                             parse_frame, sign, session_id, transport_manifest, safe_host_path)


class _IO:
    def __init__(self, process):
        self.process = process
        self.frames = queue.Queue(maxsize=3)
        self.error = None
        self.stdout = bytearray(); self.stderr = bytearray()
        self.public_request = b""; self.request_bytes_written = 0
        self.stdout_truncated = False; self.stderr_truncated = False
        self.threads = []
        self._start(self._stdout)
        self._start(self._stderr)

    def _start(self, function):
        thread = threading.Thread(target=function, name="mmc-transport-io", daemon=True)
        self.threads.append(thread); thread.start()
        return thread

    def _stdout(self):
        try:
            with io.BufferedReader(self.process.stdout, buffer_size=64*1024) as reader:
                for index in range(3):
                    raw = reader.readline(min(MAX_FRAME + 2, MAX_STDOUT-len(self.stdout)))
                    if not raw:
                        self.frames.put(None); return
                    self.stdout.extend(raw)
                    if index >= 2 or len(raw) > MAX_FRAME + 1 or not raw.endswith(b"\n"):
                        self.stdout_truncated = True
                        raise MMCError("MMC_TRANSPORT_FRAME_LIMIT")
                    self.frames.put(raw)
        except Exception as error:
            self.error = error

    def _stderr(self):
        try:
            while True:
                chunk = self.process.stderr.read(4096)
                if not chunk:
                    return
                remaining = MAX_STDERR-len(self.stderr)
                self.stderr.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.stderr_truncated = True
                    raise MMCError("MMC_TRANSPORT_STDERR_LIMIT")
        except Exception as error:
            self.error = error

    def send(self, raw, *, close=False, public=False):
        done = threading.Event()
        if public:
            self.public_request = raw
        def write():
            try:
                offset = 0
                while offset < len(raw):
                    written = self.process.stdin.write(memoryview(raw)[offset:])
                    require(type(written) is int and written > 0, "MMC_TRANSPORT_PIPE_ERROR")
                    offset += written
                    if public:
                        self.request_bytes_written = offset
                self.process.stdin.flush()
                if close:
                    self.process.stdin.close()
            except Exception as error:
                self.error = error
            finally:
                done.set()
        self._start(write)
        return done


class AuthenticatedAdapter(EffectAdapter):
    """Host-constructed adapter wrapper. Data cannot choose an executable/import.

    Every RPC gets fresh credentials, challenge and process; apply is never retried.
    Authentication binds a cooperative local child to its exact enrolled code and
    target descriptor. This does not create OS sandboxing or production authority.
    """
    def __init__(self, target_path, *, backend, expected_descriptor, deadline_seconds=30,
                 implementation_pin=None, allow_test_faults=False, retain_transcripts=False,
                 transcript_byte_limit=8*1024*1024):
        require(backend in BACKENDS, "MMC_TRANSPORT_BACKEND")
        require(type(expected_descriptor) is dict and type(allow_test_faults) is bool and
                type(retain_transcripts) is bool,
                "MMC_TRANSPORT_ENROLLMENT")
        require(type(transcript_byte_limit) is int and TRANSCRIPT_RESERVATION <= transcript_byte_limit <= 64*1024*1024,
                "MMC_TRANSPORT_TRANSCRIPT_LIMIT")
        require(type(deadline_seconds) in (int, float) and math.isfinite(deadline_seconds) and
                0.05 <= deadline_seconds <= 60, "MMC_TRANSPORT_DEADLINE")
        self.path = safe_database(target_path)
        self.backend = backend
        self.expected_descriptor = clone(expected_descriptor)
        self.deadline_ms = int(deadline_seconds * 1000)
        self.implementation_pin = execution_pin(backend) if implementation_pin is None else hex256(implementation_pin)
        self.allow_test_faults = allow_test_faults
        self._call_lock = threading.Lock(); self._state_lock = threading.Lock()
        self._active_cancel = None; self._active_pid = None; self._closed = False
        self._history = []; self._transport = None
        self._retain_transcripts = retain_transcripts; self._transcript_limit = transcript_byte_limit
        self._transcript_bytes = 0; self._transcripts = []
        described = self._call("describe", {})
        closed(described, {"descriptor", "identity", "model_adapter"})
        require(described["descriptor"] == self.expected_descriptor and
                described["identity"].get("id") == self.expected_descriptor.get("id"),
                "MMC_TRANSPORT_ADAPTER_PIN")
        self.identity = clone(described["identity"])
        self.model_adapter = described["model_adapter"]

    @classmethod
    def open(cls, target_path, *, backend="disposable.sqlite.v1", expected_descriptor,
             deadline_seconds=30, implementation_pin=None, allow_test_faults=False,
             retain_transcripts=False, transcript_byte_limit=8*1024*1024):
        return cls(target_path, backend=backend, expected_descriptor=expected_descriptor,
                   deadline_seconds=deadline_seconds, implementation_pin=implementation_pin,
                   allow_test_faults=allow_test_faults, retain_transcripts=retain_transcripts,
                   transcript_byte_limit=transcript_byte_limit)

    def descriptor(self):
        return clone(self.expected_descriptor)

    def snapshot(self, targets):
        return self._call("snapshot", {"targets": targets})

    def lookup(self, op_id, request_root):
        return self._call("lookup", {"operation_id": op_id, "request_root": request_root})

    def apply(self, request, *, fault=None):
        require(fault is None or self.allow_test_faults, "MMC_TRANSPORT_TEST_FAULT_DISABLED")
        return self._call("apply", {"request": request, "fault": fault})

    def workload_snapshot(self):
        return self._call("workload_snapshot", {})

    @property
    def active_worker_pid(self):
        with self._state_lock:
            return self._active_pid

    def cancel(self):
        with self._state_lock:
            if self._active_cancel is None:
                return False
            self._active_cancel.set()
            return True

    def close(self):
        with self._state_lock:
            self._closed = True
            if self._active_cancel is not None:
                self._active_cancel.set()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

    def export_transcripts(self):
        """Return bounded raw bytes for host-selected custody, without declassification."""
        require(self._retain_transcripts, "MMC_TRANSPORT_TRANSCRIPTS_NOT_RETAINED")
        with self._state_lock:
            return [dict(value) for value in self._transcripts]

    def transport_receipt(self, *, include_transcripts=False):
        with self._state_lock:
            calls = clone(self._history)
        body = {"schema": "mmc.adapter-transport-receipt.v1", "protocol": PROTOCOL,
                "backend": self.backend, "implementation_pin": self.implementation_pin,
                "automatic_apply_retry": False, "calls": calls,
                "transcript_custody": "RETAINED_RAW_BYTES" if self._retain_transcripts else "DIGEST_ONLY",
                "authority_effect": "NONE"}
        if include_transcripts:
            values = []
            for row in self.export_transcripts():
                value = {key: item for key, item in row.items() if key not in {"request", "stdout", "stderr"}}
                for name in ("request", "stdout", "stderr"):
                    raw = row[name]
                    value[name + "_base64_chunks"] = [base64.b64encode(raw[offset:offset+24*1024]).decode("ascii")
                                                       for offset in range(0, len(raw), 24*1024)]
                values.append(value)
            body["raw_transcripts"] = values
        return {**body, "receipt_root": hashlib.sha256(canonical(body)).hexdigest()}

    def _launch(self):
        # Use the real interpreter, bypassing Windows venv redirectors, and add
        # only explicit host runtime roots. -S disables site/.pth startup code.
        executable = safe_host_path(getattr(sys, "_base_executable", sys.executable))
        package_root = str(safe_host_path(Path(__file__).absolute().parent.parent, directory=True))
        roots = list(dict.fromkeys((package_root, sysconfig.get_path("purelib"), sysconfig.get_path("platlib"))))
        roots = [str(safe_host_path(path, directory=True)) for path in roots]
        program = "import sys; sys.path[:0]=" + repr(roots) + "; from mosaic_mmc_product.adapter_worker import entrypoint; raise SystemExit(entrypoint())"
        command = [str(executable), "-I", "-S", "-B", "-X",
                   "pycache_prefix=" + str(self.path.parent / (".mmc-worker-cache-" + uuid.uuid4().hex)),
                   "-c", program]
        environment = {key: value for key, value in os.environ.items()
                       if not key.upper().startswith("PYTHON")}
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=self.path.parent, env=environment,
                                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    @staticmethod
    def _check(deadline, cancelled, channel):
        require(not cancelled.is_set(), "MMC_TRANSPORT_CANCELLED")
        require(time.monotonic() < deadline, "MMC_TRANSPORT_DEADLINE_EXCEEDED")
        if channel.error is not None:
            if isinstance(channel.error, MMCError):
                raise channel.error
            raise MMCError("MMC_TRANSPORT_PIPE_ERROR", detail=type(channel.error).__name__)

    def _receive(self, channel, deadline, cancelled):
        while True:
            self._check(deadline, cancelled, channel)
            try:
                raw = channel.frames.get(timeout=min(0.02, max(0.001, deadline-time.monotonic())))
                require(raw is not None, "MMC_TRANSPORT_WORKER_EXITED")
                return parse_frame(raw)
            except queue.Empty:
                continue

    def _send(self, channel, packet, deadline, cancelled, *, bootstrap=False, close=False):
        raw = frame(packet, limit=MAX_BOOTSTRAP if bootstrap else MAX_FRAME)
        done = channel.send(raw, close=close, public=not bootstrap)
        while not done.wait(0.01):
            self._check(deadline, cancelled, channel)
        self._check(deadline, cancelled, channel)

    def _call(self, operation, arguments):
        with self._call_lock:
            return self._exchange(operation, arguments)

    def _exchange(self, operation, arguments):
        cancelled = threading.Event()
        with self._state_lock:
            require(not self._closed and len(self._history) < 1024, "MMC_TRANSPORT_CLOSED_OR_BUDGET")
            require(not self._retain_transcripts or self._transcript_bytes + TRANSCRIPT_RESERVATION <= self._transcript_limit,
                    "MMC_TRANSPORT_TRANSCRIPT_BUDGET")
            self._active_cancel = cancelled
        key = secrets.token_bytes(32); host_nonce = secrets.token_hex(32)
        started = time.monotonic_ns()
        deadline = time.monotonic() + self.deadline_ms / 1000
        process = None; channel = None
        record = {"operation": operation, "status": "UNKNOWN", "mutual_authentication": False,
                  "worker_authentication_verified": False, "request_authenticator_sent": False,
                  "response_authentication_verified": False,
                  "implementation_pin": self.implementation_pin, "automatic_retry": False,
                  "exit_code": None, "io_threads_reaped": True,
                  "stdout_sha256": hashlib.sha256(b"").hexdigest(),
                  "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                  "stdout_bytes": 0, "stderr_bytes": 0, "request_bytes_written": 0,
                  "stdout_capture_truncated": False, "stderr_capture_truncated": False}
        try:
            require(execution_pin(self.backend) == self.implementation_pin, "MMC_TRANSPORT_IMPLEMENTATION_PIN")
            safe_database(self.path)
            require(not cancelled.is_set(), "MMC_TRANSPORT_CANCELLED")
            process = self._launch(); channel = _IO(process)
            record["launcher_pid"] = process.pid
            with self._state_lock:
                self._active_pid = process.pid
                if self._closed:
                    cancelled.set()
            self._check(deadline, cancelled, channel)
            boot = {"protocol": PROTOCOL, "secret": key.hex(), "host_nonce": host_nonce,
                    "backend": self.backend, "target_path": str(self.path),
                    "implementation_pin": self.implementation_pin,
                    "expected_descriptor": self.expected_descriptor,
                    "allow_test_faults": self.allow_test_faults}
            self._send(channel, boot, deadline, cancelled, bootstrap=True)
            challenge = authenticate(key, "challenge", self._receive(channel, deadline, cancelled))
            closed(challenge, {"protocol", "session", "host_nonce", "worker_nonce",
                               "implementation_pin", "backend", "worker_pid"})
            require(challenge["protocol"] == PROTOCOL and challenge["backend"] == self.backend and
                    challenge["implementation_pin"] == self.implementation_pin and
                    challenge["host_nonce"] == host_nonce and type(challenge["worker_pid"]) is int and
                    challenge["worker_pid"] == process.pid, "MMC_TRANSPORT_WORKER_IDENTITY")
            session = session_id(host_nonce, challenge["worker_nonce"], self.implementation_pin)
            require(challenge["session"] == session, "MMC_TRANSPORT_REPLAY")
            record.update(worker_pid=challenge["worker_pid"], session=session)
            record["worker_authentication_verified"] = True
            request = {"protocol": PROTOCOL, "session": session, "sequence": 1,
                       "operation": operation, "arguments": arguments,
                       "challenge_root": hashlib.sha256(canonical(challenge)).hexdigest()}
            request_root = hashlib.sha256(canonical(request)).hexdigest()
            record["request_root"] = request_root
            self._send(channel, sign(key, "request", request), deadline, cancelled, close=True)
            record["request_authenticator_sent"] = True
            reply = authenticate(key, "response", self._receive(channel, deadline, cancelled))
            require(type(reply) is dict and type(reply.get("ok")) is bool, "MMC_TRANSPORT_RESPONSE")
            closed(reply, {"protocol", "session", "sequence", "request_root", "ok",
                           "result" if reply["ok"] else "error"})
            require(reply["protocol"] == PROTOCOL and reply["session"] == session and
                    type(reply["sequence"]) is int and reply["sequence"] == 1 and
                    reply["request_root"] == request_root, "MMC_TRANSPORT_REPLAY")
            record["mutual_authentication"] = True
            record["response_authentication_verified"] = True
            while process.poll() is None:
                self._check(deadline, cancelled, channel); time.sleep(0.005)
            require(process.returncode == 0, "MMC_TRANSPORT_WORKER_EXITED")
            for thread in channel.threads:
                thread.join(timeout=max(0.001, min(0.2, deadline-time.monotonic())))
            self._check(deadline, cancelled, channel)
            require(all(not thread.is_alive() for thread in channel.threads), "MMC_TRANSPORT_CLEANUP_FAILED")
            if not reply["ok"]:
                closed(reply["error"], {"code", "path", "detail"})
                raise MMCError("MMC_TRANSPORT_REMOTE_REFUSAL", detail=reply["error"]["code"])
            record.update(status="AUTHENTICATED_RESPONSE", result_sha256=hashlib.sha256(canonical(reply["result"])).hexdigest())
            return clone(reply["result"])
        except Exception as error:
            record["refusal_code"] = getattr(error, "code", "MMC_TRANSPORT_FAILURE")
            if isinstance(error, MMCError):
                raise
            raise MMCError("MMC_TRANSPORT_FAILURE", detail=type(error).__name__) from error
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=2)
                record["exit_code"] = process.returncode
                if channel is not None:
                    for thread in channel.threads:
                        thread.join(timeout=1)
                    record["io_threads_reaped"] = all(not thread.is_alive() for thread in channel.threads)
                    record["stdout_sha256"] = hashlib.sha256(channel.stdout).hexdigest()
                    record["stderr_sha256"] = hashlib.sha256(channel.stderr).hexdigest()
                    record["stderr_bytes"] = len(channel.stderr)
                    record["stdout_bytes"] = len(channel.stdout)
                    record["request_bytes_written"] = channel.request_bytes_written
                    record["stdout_capture_truncated"] = channel.stdout_truncated
                    record["stderr_capture_truncated"] = channel.stderr_truncated
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe and not pipe.closed:
                        pipe.close()
            with self._state_lock:
                self._active_cancel = None; self._active_pid = None
                record["elapsed_ns"] = time.monotonic_ns() - started
                if self._retain_transcripts:
                    values = {"call": len(self._history)+1, "bootstrap": "OMITTED_EPHEMERAL_SECRET",
                              "request": b"" if channel is None else bytes(channel.public_request),
                              "stdout": b"" if channel is None else bytes(channel.stdout),
                              "stderr": b"" if channel is None else bytes(channel.stderr),
                              "exit_code": record["exit_code"],
                              "request_bytes_written": record.get("request_bytes_written", 0),
                              "stdout_capture_truncated": record.get("stdout_capture_truncated", False),
                              "stderr_capture_truncated": record.get("stderr_capture_truncated", False)}
                    self._transcript_bytes += sum(len(values[name]) for name in ("request", "stdout", "stderr"))
                    self._transcripts.append(values)
                self._transport = clone(record); self._history.append(clone(record))
