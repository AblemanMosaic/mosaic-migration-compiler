"""Real process/channel failure witnesses for the enrolled adapter transport."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import base64
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import MMCError
from mosaic_mmc_t3 import digest
from mosaic_mmc_product.adapter import DisposableSQLiteAdapter
from mosaic_mmc_product.transport import AuthenticatedAdapter
from mosaic_mmc_product import transport as transport_module
from mosaic_mmc_product.transport_wire import (MAX_FRAME, authenticate, frame, parse_frame,
                                               session_id, sign, TRANSCRIPT_RESERVATION, execution_pin,
                                               workload_summary)


class AuthenticatedTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mmc-transport-test-", dir=ROOT.parent)
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "target.sqlite"
        self.local = DisposableSQLiteAdapter.create(self.path, "transport.test", {
            "producer.old": "legacy", "consumer.main": "legacy", "asset.legacy": "legacy"})
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO legacy_records VALUES ('blue.1','blue','payload')")

    def open(self, **options):
        adapter = AuthenticatedAdapter.open(self.path, expected_descriptor=self.local.descriptor(), **options)
        self.addCleanup(adapter.close)
        return adapter

    def request(self, operation_id="transport.op.1"):
        before = self.local.snapshot(["producer.old"])
        return {"schema": "mmc.effect-request.t3", "operation_id": operation_id,
                "scope": {"migration": "migration.transport", "transition": "step.prepare",
                          "cohort": "cohort.blue", "targets": ["producer.old"],
                          "plan_root": "0" * 64, "policy_root": "1" * 64},
                "context_root": "2" * 64, "direction": "FORWARD", "compensates": None,
                "adapter": self.local.descriptor(), "pre_state": before,
                "post_state": {"producer.old": {"state": "prepared", "floor": 5,
                                                "revoked": ["revoked.key"]}},
                "prepared_at": 100, "expires_at": 130, "max_attempts": 2}

    def test_real_worker_authenticates_and_uses_distinct_fresh_sessions(self):
        adapter = self.open()
        self.assertEqual(adapter.snapshot(["producer.old"]), self.local.snapshot(["producer.old"]))
        receipt = adapter.transport_receipt()
        self.assertEqual(len(receipt["calls"]), 2)
        self.assertEqual(len({row["session"] for row in receipt["calls"]}), 2)
        for row in receipt["calls"]:
            self.assertTrue(row["mutual_authentication"])
            self.assertTrue(row["io_threads_reaped"])
            self.assertEqual(row["launcher_pid"], row["worker_pid"])
            self.assertNotEqual(row["worker_pid"], __import__("os").getpid())

    def test_lost_ack_reopens_worker_and_reconciles_without_second_effect(self):
        adapter = self.open(allow_test_faults=True)
        request = self.request()
        with self.assertRaisesRegex(MMCError, "REMOTE_REFUSAL"):
            adapter.apply(request, fault="lost_ack")
        reopened = self.open()
        result = reopened.lookup(request["operation_id"], digest("request", request))
        self.assertEqual(result["status"], "APPLIED")
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 1)
        self.assertEqual(self.local.snapshot(["producer.old"])["producer.old"]["version"], 1)
        self.assertFalse(adapter.transport_receipt()["automatic_apply_retry"])

    def test_worker_death_after_commit_is_reconciled_from_target_ledger(self):
        adapter = self.open(allow_test_faults=True)
        request = self.request()
        with self.assertRaisesRegex(MMCError, "WORKER_EXITED"):
            adapter.apply(request, fault="crash_after")
        self.assertTrue(adapter._transport["worker_authentication_verified"])
        self.assertEqual(adapter._transport["exit_code"], 73)
        self.assertTrue(adapter._transport["io_threads_reaped"])
        self.assertEqual(self.open().lookup(request["operation_id"], digest("request", request))["status"], "APPLIED")
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 1)

    def test_bad_response_mac_preserves_uncertainty_and_committed_ledger(self):
        adapter = self.open()
        original = adapter._receive
        def tamper(*args):
            packet = original(*args)
            if "request_root" in packet["body"]:
                packet["mac"] = "0" * 64
            return packet
        request = self.request()
        with patch.object(adapter, "_receive", side_effect=tamper):
            with self.assertRaisesRegex(MMCError, "AUTHENTICATION"):
                adapter.apply(request)
        self.assertEqual(self.open().lookup(request["operation_id"], digest("request", request))["status"], "APPLIED")
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 1)

    def test_forged_host_mac_is_rejected_before_effect(self):
        adapter = self.open()
        original = transport_module.sign
        def tamper(key, label, body):
            packet = original(key, label, body)
            if label == "request":
                packet["mac"] = "0" * 64
            return packet
        with patch.object(transport_module, "sign", side_effect=tamper):
            with self.assertRaisesRegex(MMCError, "WORKER_EXITED"):
                adapter.apply(self.request())
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 0)

    def test_replayed_session_is_rejected_even_with_valid_host_mac(self):
        adapter = self.open()
        original = transport_module.sign
        def tamper(key, label, body):
            return original(key, label, {**body, "session": "0" * 64} if label == "request" else body)
        with patch.object(transport_module, "sign", side_effect=tamper):
            with self.assertRaisesRegex(MMCError, "WORKER_EXITED"):
                adapter.apply(self.request())
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 0)

    def test_mac_domain_separation_and_fresh_session_identity(self):
        key = b"k" * 32
        packet = sign(key, "challenge", {"value": 1})
        with self.assertRaisesRegex(MMCError, "AUTHENTICATION"):
            authenticate(key, "response", packet)
        self.assertNotEqual(session_id("1"*64, "2"*64, "3"*64), session_id("1"*64, "4"*64, "3"*64))

    def test_deadline_after_apply_leaves_one_effect_for_reconciliation(self):
        # The worker's admitted post-commit fault sleeps for five seconds.  A
        # three-second host deadline leaves a deterministic post-commit timeout
        # window without making process startup itself the event under test.
        adapter = self.open(deadline_seconds=3, allow_test_faults=True)
        request = self.request()
        with self.assertRaisesRegex(MMCError, "DEADLINE_EXCEEDED"):
            adapter.apply(request, fault="transport.delay-after-apply")
        self.assertTrue(adapter._transport["io_threads_reaped"])
        self.assertEqual(self.open().lookup(request["operation_id"], digest("request", request))["status"], "APPLIED")
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 1)

    def test_cancel_terminates_real_worker_without_automatic_retry(self):
        adapter = self.open(allow_test_faults=True)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(adapter.apply, self.request(), fault="transport.delay-before-apply")
            until = time.monotonic() + 5
            while adapter.active_worker_pid is None and time.monotonic() < until:
                time.sleep(0.005)
            self.assertTrue(adapter.cancel())
            with self.assertRaisesRegex(MMCError, "CANCELLED"):
                future.result(timeout=5)
        self.assertTrue(adapter._transport["io_threads_reaped"])
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 0)

    def test_close_during_process_startup_prevents_apply_dispatch(self):
        adapter = self.open()
        launching = threading.Event(); release = threading.Event()
        original = adapter._launch
        def blocked_launch():
            launching.set()
            self.assertTrue(release.wait(3))
            return original()
        with patch.object(adapter, "_launch", side_effect=blocked_launch):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(adapter.apply, self.request())
                self.assertTrue(launching.wait(3))
                adapter.close()
                release.set()
                with self.assertRaisesRegex(MMCError, "CANCELLED"):
                    future.result(timeout=5)
        self.assertTrue(adapter._transport["io_threads_reaped"])
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 0)

    def test_opt_in_raw_transcript_preserves_bytes_and_omits_bootstrap_secret(self):
        secrets_seen = []
        original = AuthenticatedAdapter._send
        def observe(instance, channel, packet, *args, **kwargs):
            if kwargs.get("bootstrap"):
                secrets_seen.append(packet["secret"].encode("ascii"))
            return original(instance, channel, packet, *args, **kwargs)
        with patch.object(AuthenticatedAdapter, "_send", new=observe):
            adapter = self.open(retain_transcripts=True)
            adapter.snapshot(["producer.old"])
        exported = adapter.export_transcripts()
        receipt = adapter.transport_receipt(include_transcripts=True)
        self.assertEqual(len(exported), 2)
        for index, raw in enumerate(exported):
            self.assertEqual(hashlib.sha256(raw["stdout"]).hexdigest(), receipt["calls"][index]["stdout_sha256"])
            for name in ("request", "stdout", "stderr"):
                decoded = b"".join(base64.b64decode(chunk) for chunk in receipt["raw_transcripts"][index][name+"_base64_chunks"])
                self.assertEqual(decoded, raw[name])
                for secret in secrets_seen:
                    self.assertNotIn(secret, decoded)
        self.assertEqual(receipt["transcript_custody"], "RETAINED_RAW_BYTES")

    def test_startup_failure_retains_empty_terminal_custody_and_typed_refusal(self):
        adapter = self.open(retain_transcripts=True)
        with patch.object(adapter, "_launch", side_effect=OSError("test executable unavailable")):
            with self.assertRaisesRegex(MMCError, "MMC_TRANSPORT_FAILURE"):
                adapter.snapshot(["producer.old"])
        record = adapter.transport_receipt(include_transcripts=True)
        self.assertEqual(record["calls"][-1]["status"], "UNKNOWN")
        self.assertIsNone(record["calls"][-1]["exit_code"])
        self.assertEqual(record["calls"][-1]["stdout_sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual(record["calls"][-1]["stdout_bytes"], 0)
        self.assertEqual(record["calls"][-1]["stderr_bytes"], 0)
        self.assertEqual(adapter.export_transcripts()[-1]["stdout"], b"")
        self.assertEqual(adapter.export_transcripts()[-1]["stderr"], b"")

    def test_maximum_row_count_workload_has_bounded_wire_summary_before_and_after_copy(self):
        from mosaic_mmc_product.sqlite_target import SQLiteTargetAdapter
        from mosaic_mmc_product.target_qualification import initialize_customer_database, qualification_manifest
        from mosaic_mmc_product.adapter import WORKLOAD_STEPS
        database = Path(self.temporary.name) / "capacity.sqlite"
        initialize_customer_database(database)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("DELETE FROM customer_credentials_v1")
            connection.executemany("INSERT INTO customer_credentials_v1 VALUES (?,?,?)",
                                   [(f"capacity.{number:04}", "blue", "x"*4096) for number in range(512)])
        manifest = qualification_manifest(); manifest.update(max_rows=512, max_payload_bytes=4096)
        local = SQLiteTargetAdapter.enroll(database, manifest, {
            "producer.old": "legacy", "consumer.main": "legacy", "asset.legacy": "legacy"})
        adapter = AuthenticatedAdapter.open(database, backend="sqlite.table-migration.v1",
                                             expected_descriptor=local.descriptor())
        self.addCleanup(adapter.close)
        for copied in (False, True):
            if copied:
                for serial, (step, mapping) in enumerate(WORKLOAD_STEPS.items(), 1):
                    targets = sorted(mapping); before = local.snapshot(targets)
                    request = {"schema": "mmc.effect-request.t3", "operation_id": f"capacity.op.{serial}",
                               "scope": {"migration": manifest["migration_id"], "transition": step,
                                         "cohort": manifest["cohort_id"], "targets": targets,
                                         "plan_root": "0"*64, "policy_root": "1"*64},
                               "context_root": "2"*64, "direction": "FORWARD", "compensates": None,
                               "adapter": local.descriptor(), "pre_state": before,
                               "post_state": {name: {"state": mapping[name][1], "floor": value["floor"],
                                                     "revoked": value["revoked"]} for name, value in before.items()},
                               "prepared_at": 100, "expires_at": 130, "max_attempts": 2}
                    local.apply(request)
                    if step == "step.reconcile":
                        break
            summary = adapter.workload_snapshot()
            full = local.workload_snapshot()
            self.assertEqual(summary, workload_summary(full))
            for name in ("legacy", "new"):
                expected = hashlib.sha256(b"MMC/ADAPTER/ROWS/v1\0" + name.encode("ascii") + b"\0")
                for row in full[name]:
                    raw = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                    expected.update(struct.pack(">Q", len(raw))); expected.update(raw)
                self.assertEqual(summary["inventories"][name]["rows_sha256"], expected.hexdigest())
            self.assertEqual(summary["schema"], "mmc.adapter-workload-summary.v1")
            self.assertEqual(summary["inventories"]["legacy"]["row_count"], 512)
            self.assertEqual(summary["inventories"]["new"]["row_count"], 512 if copied else 0)
            self.assertLess(len(frame(summary)), 4096)
            self.assertNotIn("x"*4096, str(summary))

    def test_transcript_budget_refuses_before_process_or_effect(self):
        adapter = self.open(retain_transcripts=True)
        adapter._transcript_bytes = adapter._transcript_limit-TRANSCRIPT_RESERVATION+1
        with patch.object(adapter, "_launch") as launch:
            with self.assertRaisesRegex(MMCError, "TRANSCRIPT_BUDGET"):
                adapter.apply(self.request())
        launch.assert_not_called()
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 0)

    def test_identity_substitution_is_refused_by_worker(self):
        descriptor = self.local.descriptor(); descriptor["id"] = "substituted"
        with self.assertRaisesRegex(MMCError, "ADAPTER_PIN"):
            AuthenticatedAdapter.open(self.path, expected_descriptor=descriptor)

    def test_implementation_pin_substitution_refuses_before_process(self):
        with patch.object(AuthenticatedAdapter, "_launch") as launch:
            with self.assertRaisesRegex(MMCError, "IMPLEMENTATION_PIN"):
                AuthenticatedAdapter.open(self.path, expected_descriptor=self.local.descriptor(), implementation_pin="0"*64)
        launch.assert_not_called()

    def test_package_directory_junction_is_refused_before_launch(self):
        package = Path(transport_module.__file__).absolute().parent
        original = getattr(Path, "is_junction", lambda unused: False)
        with patch.object(Path, "is_junction", lambda path: path == package or original(path), create=True):
            with self.assertRaisesRegex(MMCError, "IMPLEMENTATION_PATH"):
                execution_pin("disposable.sqlite.v1")

    def test_frame_limits_reject_oversized_encode_and_decode(self):
        with self.assertRaisesRegex(MMCError, "FRAME_LIMIT"):
            frame({"chunks": ["x" * 64] * 33000})
        with self.assertRaisesRegex(MMCError, "FRAME_LIMIT"):
            parse_frame(b"x" * (MAX_FRAME + 2))

    def _fake_worker(self, code):
        return subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-I", "-S", "-c", code],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_stdout_flood_is_bounded_and_worker_reaped(self):
        adapter = self.open(deadline_seconds=2)
        with patch.object(adapter, "_launch", side_effect=lambda: self._fake_worker("import sys,time; sys.stdout.write('x'*2200000); sys.stdout.flush(); time.sleep(5)")):
            with self.assertRaisesRegex(MMCError, "FRAME_LIMIT"):
                adapter.snapshot(["producer.old"])
        self.assertTrue(adapter._transport["io_threads_reaped"])

    def test_stderr_flood_is_bounded_and_worker_reaped(self):
        adapter = self.open(deadline_seconds=2)
        with patch.object(adapter, "_launch", side_effect=lambda: self._fake_worker("import sys,time; sys.stderr.write('x'*100000); sys.stderr.flush(); time.sleep(5)")):
            with self.assertRaisesRegex(MMCError, "STDERR_LIMIT"):
                adapter.snapshot(["producer.old"])
        self.assertLessEqual(adapter._transport["stderr_bytes"], 65536)
        self.assertTrue(adapter._transport["io_threads_reaped"])

    def _signed_fake_worker(self, suffix):
        return ("import sys,os,hashlib; sys.path.insert(0," + repr(str(ROOT / "src")) + "); "
                "from mosaic_mmc import canonical; "
                "from mosaic_mmc_product.transport_wire import *; "
                "b=parse_frame(sys.stdin.buffer.readline()); k=bytes.fromhex(b['secret']); "
                "n='1'*64; s=session_id(b['host_nonce'],n,b['implementation_pin']); "
                "c={'protocol':PROTOCOL,'session':s,'host_nonce':b['host_nonce'],'worker_nonce':n,"
                "'implementation_pin':b['implementation_pin'],'backend':b['backend'],'worker_pid':os.getpid()}; "
                "sys.stdout.buffer.write(frame(sign(k,'challenge',c))); sys.stdout.buffer.flush(); "
                "r=authenticate(k,'request',parse_frame(sys.stdin.buffer.readline())); sys.stdin.buffer.read(1); "
                "v={'protocol':PROTOCOL,'session':s,'sequence':1,'request_root':hashlib.sha256(canonical(r)).hexdigest(),"
                "'ok':True,'result':{'value':'valid-signed-response'}}; "
                "sys.stdout.buffer.write(frame(sign(k,'response',v))); sys.stdout.buffer.flush(); " + suffix)

    def test_valid_signed_response_followed_by_extra_frame_is_not_success(self):
        adapter = self.open(deadline_seconds=2)
        code = self._signed_fake_worker("sys.stdout.buffer.write(b'{}\\n'); sys.stdout.buffer.flush()")
        with patch.object(adapter, "_launch", side_effect=lambda: self._fake_worker(code)):
            with self.assertRaisesRegex(MMCError, "FRAME_LIMIT"):
                adapter.snapshot(["producer.old"])
        self.assertEqual(adapter._transport["status"], "UNKNOWN")
        self.assertTrue(adapter._transport["io_threads_reaped"])

    def test_valid_signed_response_followed_by_stderr_flood_is_not_success(self):
        adapter = self.open(deadline_seconds=2)
        code = self._signed_fake_worker("sys.stderr.write('x'*100000); sys.stderr.flush()")
        with patch.object(adapter, "_launch", side_effect=lambda: self._fake_worker(code)):
            with self.assertRaisesRegex(MMCError, "STDERR_LIMIT"):
                adapter.snapshot(["producer.old"])
        self.assertEqual(adapter._transport["status"], "UNKNOWN")
        self.assertTrue(adapter._transport["io_threads_reaped"])

    def test_test_fault_selection_is_disabled_by_default(self):
        adapter = self.open()
        with self.assertRaisesRegex(MMCError, "TEST_FAULT_DISABLED"):
            adapter.apply(self.request(), fault="before")
        self.assertEqual(self.local.workload_snapshot()["effect_count"], 0)


if __name__ == "__main__":
    unittest.main()
