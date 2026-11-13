"""Disposable qualification of an enrolled customer-table target over transport."""
from __future__ import annotations

import argparse
from contextlib import closing, ExitStack
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from mosaic_mmc_t3 import Controller, digest, make_plan, validate_policy
from mosaic_mmc_t5.fixtures import make_bundle, reader_policy, approve_records, STEPS
from .disposable import _actual_records
from .sqlite_target import SQLiteTargetAdapter


def _sha(value): return hashlib.sha256(value).hexdigest()


def qualification_manifest(identity="qualified.customer"):
    return {"schema": "mmc.sqlite-target-enrollment.v1", "id": identity,
            "migration_id": "migration.customer.blue", "cohort_id": "cohort.blue",
            "cohort": "blue", "cohorts": ["blue", "green"],
            "source_table": "customer_credentials_v1", "destination_table": "customer_credentials_v2",
            "id_column": "credential_id", "cohort_column": "tenant", "payload_column": "credential_payload",
            "checksum_column": "source_digest", "target_ids": {"producer": "producer.old", "consumer": "consumer.main", "asset": "asset.legacy"},
            "max_rows": 512, "max_payload_bytes": 4096}


def initialize_customer_database(path):
    """A target application creates its own tables before any MMC enrollment."""
    with closing(sqlite3.connect(path)) as con, con:
        con.execute("CREATE TABLE customer_credentials_v1(credential_id TEXT PRIMARY KEY NOT NULL, tenant TEXT NOT NULL, credential_payload TEXT NOT NULL)")
        con.execute("CREATE TABLE customer_credentials_v2(credential_id TEXT PRIMARY KEY NOT NULL, tenant TEXT NOT NULL, credential_payload TEXT NOT NULL, source_digest TEXT NOT NULL)")
        con.executemany("INSERT INTO customer_credentials_v1 VALUES (?,?,?)", [
            (f"blue.{index:03}", "blue", f"customer credential payload {index} α") for index in range(32)
        ] + [("green.000", "green", "unmigrated tenant payload")])


def _write(path, cohort, key, payload):
    try:
        with closing(sqlite3.connect(path)) as con, con:
            con.execute("INSERT INTO customer_credentials_v1 VALUES (?,?,?)", (key, cohort, payload))
        return {"status": "LEGACY_WRITE_ACCEPTED", "cohort": cohort, "pid": os.getpid()}
    except sqlite3.IntegrityError as error:
        if "legacy_write_fenced" not in str(error): raise
        return {"status": "LEGACY_WRITE_FENCED", "cohort": cohort, "pid": os.getpid()}


def _dormant(path, ready, stack):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen([sys.executable, "-B", "-X", "pycache_prefix=" + str(ready.parent / "client-cache"),
                                "-m", "mosaic_mmc_product.target_qualification", "dormant-worker", str(path), str(ready)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    def stop():
        if process.poll() is None: process.kill()
        process.communicate(timeout=10)
    stack.callback(stop)
    until = time.monotonic() + 15
    while not ready.exists() and process.poll() is None and time.monotonic() < until:
        time.sleep(.01)
    require(ready.exists() and process.poll() is None, "MMC_TARGET_DORMANT_NOT_READY")
    handshake = decode(ready.read_bytes())
    require(handshake["status"] == "WAITING" and type(handshake["pid"]) is int, "MMC_TARGET_DORMANT_HANDSHAKE")
    return process, handshake["pid"]


def _inventory(path):
    with closing(sqlite3.connect(path)) as con:
        con.execute("BEGIN")
        return {"source": [list(row) for row in con.execute("SELECT credential_id,tenant,credential_payload FROM customer_credentials_v1 ORDER BY credential_id")],
                "destination": [list(row) for row in con.execute("SELECT credential_id,tenant,credential_payload,source_digest FROM customer_credentials_v2 ORDER BY credential_id")]}


def run_target_qualification(*, authenticated=True):
    """Run the actual target adapter; public default requires process transport."""
    bundle = make_bundle("identity")
    for obj in bundle["model"]["objects"]:
        if obj["kind"] == "Effect": obj["attributes"]["adapter"] = SQLiteTargetAdapter.model_adapter
    policy = reader_policy([bundle]); policy["observers"][0]["methods"] = ["disposable-sqlite-observation"]
    policy = validate_policy(policy); plan = make_plan(bundle, policy)
    now = 100; clock = {"now": now, "uncertainty": 0}; migration = "migration.customer.blue"
    temporary_root = Path(os.environ.get("MMC_DISPOSABLE_TEMP_ROOT", Path.cwd()))
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mmc-customer-target-", dir=temporary_root) as temporary, ExitStack() as stack:
        path = Path(temporary); database = path / "customer.sqlite"; journal = path / "controller.sqlite"
        initialize_customer_database(database)
        prior = _inventory(database)
        manifest = qualification_manifest("customer." + path.name)
        states = {row["target"]: row["state"] for row in bundle["model"]["initial_states"]}
        local = SQLiteTargetAdapter.enroll(database, manifest, states)
        require(_inventory(database) == prior, "MMC_TARGET_ENROLLMENT_MUTATED_CUSTOMER_ROWS")
        if authenticated:
            from .transport import AuthenticatedAdapter
            adapter = AuthenticatedAdapter.open(database, backend="sqlite.table-migration.v1", expected_descriptor=local.descriptor(), deadline_seconds=30, allow_test_faults=True, retain_transcripts=True)
        else:
            adapter = local
        controller = Controller.create(journal, policy); controller.raise_floor(5, ["revoked.key"])
        controller.submit(migration, bundle, expected_plan_root=plan["root"])
        dormant, dormant_pid = _dormant(database, path / "dormant.ready", stack)
        unsafe = controller.assess(migration, "step.retire", clock)
        require(unsafe["body"]["status"] != "EVIDENCE_SATISFIES_SELECTED_POLICY", "MMC_TARGET_UNSAFE_RETIREMENT")
        number = 0; effects = []; lost_ack = None; resumed = None; recovery = None; retirement = None; transport_segments = []

        def perform(step, direction="FORWARD", fault=None):
            nonlocal number
            if direction == "FORWARD":
                for observation in _actual_records(controller, local, bundle, plan, migration, step, now, 5):
                    controller.observe(migration, observation)
            assessment = controller.assess(migration, step, clock)
            require(assessment["body"]["status"] == "EVIDENCE_SATISFIES_SELECTED_POLICY", "MMC_TARGET_EVIDENCE_HELD", step)
            number += 1
            request = controller.prepare(migration, step, adapter, clock, operation_id=f"customer.op.{number}", direction=direction)
            controller.approve(request["operation_id"], approve_records(plan, request, now), clock)
            result = controller.commit(request["operation_id"], adapter, clock, fault=fault)
            effects.append({"transition": step, "direction": direction, "operation_id": request["operation_id"],
                            "request_root": digest("request", request), "status": result["status"]})
            return request, result, assessment

        for step in STEPS:
            # The native controller exposes only its closed host test faults.
            # In a worker, crash_after commits then exits without any reply;
            # the host observes a real process/pipe failure and retains UNKNOWN.
            copy_fault = "crash_after" if authenticated else "lost_ack"
            request, result, assessment = perform(step, fault=copy_fault if step == "step.reconcile" else None)
            if step == "step.reconcile":
                require(result["status"] == "UNKNOWN", "MMC_TARGET_LOST_ACK_NOT_UNKNOWN")
                controller = Controller(journal, expected_policy_root=digest("policy", policy))
                if authenticated:
                    # Fresh host wrapper and child process must recover from the same
                    # database ledger, never from an in-memory cached success.
                    transport_segments.append(adapter.transport_receipt(include_transcripts=True))
                    failed_call = transport_segments[-1]["calls"][-1]
                    require(failed_call["operation"] == "apply" and failed_call["worker_authentication_verified"] and
                            failed_call["request_authenticator_sent"] and not failed_call.get("response_authentication_verified", False) and
                            failed_call["exit_code"] not in (None, 0) and failed_call["io_threads_reaped"],
                            "MMC_TARGET_EXPECTED_WORKER_EXIT_NOT_OBSERVED")
                    adapter = AuthenticatedAdapter.open(database, backend="sqlite.table-migration.v1", expected_descriptor=local.descriptor(), deadline_seconds=30, allow_test_faults=True, retain_transcripts=True)
                outcome = controller.reconcile(request["operation_id"], adapter)
                require(outcome["status"] == "APPLIED" and local.workload_snapshot()["effect_count"] == 5, "MMC_TARGET_RECONCILIATION")
                lost_ack = {"initial": "UNKNOWN", "reopened_controller": True, "fresh_transport": authenticated,
                            "reconciled": outcome["status"], "effect_count_after_reconcile": 5,
                            "fault": "WORKER_EXIT_AFTER_TARGET_COMMIT" if authenticated else "BACKEND_ACKNOWLEDGMENT_LOST"}
                if authenticated:
                    lost_ack.update(worker_pid=failed_call["worker_pid"], worker_exit_code=failed_call["exit_code"],
                                    authenticated_challenge_and_request=True, response_received=False)
            else:
                require(result["status"] == "APPLIED", "MMC_TARGET_EFFECT_FAILED", step)
            if step == "step.fence":
                stdout, stderr = dormant.communicate(input=b"RESUME\n", timeout=30)
                require(dormant.returncode == 0, "MMC_TARGET_DORMANT_FAILED", stderr.decode("utf-8", "replace")[:256])
                resumed = decode(stdout)
                require(resumed["pid"] == dormant_pid and resumed["status"] == "LEGACY_WRITE_FENCED", "MMC_TARGET_DORMANT_NOT_FENCED")
            if step == "step.cutover":
                _, compensated, _ = perform(step, "COMPENSATE")
                blue = next(row for row in local.workload_snapshot()["control"] if row["cohort"] == "blue")
                attempted = _write(database, "blue", "late.recovery", "obsolete writer")
                require(compensated["status"] == "APPLIED" and blue["route"] == "RECOVERY_DUAL" and
                        not blue["legacy_writes_allowed"] and blue["security_floor"] == 5 and blue["revoked"] == ["revoked.key"] and
                        attempted["status"] == "LEGACY_WRITE_FENCED", "MMC_TARGET_RECOVERY_REGRESSION")
                recovery = {"route": blue["route"], "floor": blue["security_floor"], "revoked": blue["revoked"], "legacy_write": attempted["status"]}
                _, reapplied, _ = perform(step)
                require(reapplied["status"] == "APPLIED", "MMC_TARGET_RECUTOVER")
            if step == "step.retire": retirement = assessment["body"]["retirement"]
        green = _write(database, "green", "green.001", "control tenant still writable")
        require(green["status"] == "LEGACY_WRITE_ACCEPTED", "MMC_TARGET_COHORT_ISOLATION")
        observed = _inventory(database)
        selected = [row for row in observed["source"] if row[1] == "blue"]
        copied = [row for row in observed["destination"] if row[1] == "blue"]
        require(copied == [row + [_sha(row[2].encode("utf-8"))] for row in selected], "MMC_TARGET_INDEPENDENT_INVENTORY")
        workload = local.workload_snapshot(); projection = controller.replay()["projection"]
        complete = projection["migrations"][migration]["completed"]
        require(len(complete) == 7 and workload["effect_count"] == 9 and retirement["status"] == "MODEL_RETIREMENT_CONDITIONS_MET", "MMC_TARGET_FINAL_STATE")
        events = controller.journal.export()
        if authenticated:
            transport_segments.append(adapter.transport_receipt(include_transcripts=True))
            calls = [call for segment in transport_segments for call in segment["calls"]]
            require(all(call["worker_authentication_verified"] and call["request_authenticator_sent"] and call["io_threads_reaped"] for call in calls) and
                    sum(call["operation"] == "apply" for call in calls) == 9 and
                    sum(not call.get("response_authentication_verified", False) for call in calls) == 1,
                    "MMC_TARGET_TRANSPORT_EVIDENCE_INCOMPLETE")
            transport = {"protocol": "mmc.adapter-transport.v1", "segments": transport_segments,
                         "fresh_process_per_rpc": True, "automatic_apply_retry": False,
                         "authenticated_calls": len(calls), "apply_calls": 9,
                         "unanswered_committed_apply_calls": 1}
        else: transport = {"scope": "DIRECT_IN_PROCESS_QUALIFICATION"}
        body = {"schema": "mmc.sqlite-target-qualification.v1", "status": "PASS_AUTHENTICATED_SQLITE_TARGET_MIGRATION" if authenticated else "PASS_DIRECT_SQLITE_TARGET_MIGRATION",
                "target": "EXTERNALLY_CREATED_CUSTOMER_SQLITE_TABLES", "manifest": manifest, "enrollment_root": local.enrollment["root"],
                "adapter_descriptor": local.descriptor(), "transport": transport, "plan_root": plan["root"],
                "enrollment_preserved_customer_inventory": True, "initial_customer_inventory_root": _sha(canonical(prior)),
                "unsafe_retirement": unsafe["body"]["status"], "lost_ack": lost_ack, "dormant_worker": resumed,
                "recovery": recovery, "control_cohort_write": green, "source_inventory_root": _sha(canonical(selected)),
                "destination_inventory_root": _sha(canonical(copied)), "independent_sql_inventory": "MATCH", "migrated_rows": len(copied),
                "effects": effects, "adapter_effect_count": workload["effect_count"], "completed_transitions": [row["transition"] for row in complete],
                "retirement_status": retirement["status"], "journal_events": len(events), "journal_head": projection["head"],
                "database_sha256_before_disposal": _sha(database.read_bytes()), "database_disposition": "REMOVED_WITH_OWNED_TEMPORARY_DIRECTORY",
                "coverage_scope": "ENROLLED_TABLES_AND_DECLARED_COHORTS_ONLY", "authority_scope": "SIGNED_PUBLIC_FIXTURE_NOT_EXTERNAL_AUTHORIZATION",
                "production_adapter": False, "power_loss_qualification": "NOT_PERFORMED", "authority_effect": "NONE"}
    return {**body, "receipt_root": _sha(canonical(body))}


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("dormant-worker"); worker.add_argument("database"); worker.add_argument("ready")
    sub.add_parser("run")
    args = parser.parse_args(argv)
    if args.command == "dormant-worker":
        # This client uses only native SQL. It does not call an MMC adapter to
        # voluntarily comply with the fence.
        with closing(sqlite3.connect(args.database)) as con:
            con.execute("SELECT 1 FROM customer_credentials_v1 LIMIT 1").fetchall()
            Path(args.ready).write_bytes(canonical({"status": "WAITING", "pid": os.getpid()}))
            require(sys.stdin.buffer.readline() == b"RESUME\n", "MMC_TARGET_DORMANT_SIGNAL")
            result = _write(Path(args.database), "blue", "late.dormant", "old runtime resumed")
    else: result = run_target_qualification()
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0


if __name__ == "__main__": raise SystemExit(main())
