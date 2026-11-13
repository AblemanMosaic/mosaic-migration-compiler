"""Disposable, process-backed SQLite migration used by qualification.

This is a real local workload and real SQLite state transition.  It is not a
production adapter and it grants no authority outside its temporary directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import os
import time
from contextlib import closing, ExitStack
from copy import deepcopy

from mosaic_mmc import canonical, decode, MMCError
from mosaic_mmc_t3 import Controller, make_plan, digest, validate_policy
from mosaic_mmc_t5.fixtures import (
    make_bundle, reader_policy, signed, approve_records, STEPS,
)
from .adapter import DisposableSQLiteAdapter


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _worker(database: Path, cohort: str, record_id: str, payload: str) -> dict:
    try:
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                "INSERT INTO legacy_records(id, cohort, payload) VALUES (?,?,?)",
                (record_id, cohort, payload),
            )
            connection.execute(
                "UPDATE worker_checkpoints SET attempts=attempts+1, last_record=? WHERE cohort=?",
                (record_id, cohort),
            )
        return {"schema": "mmc.disposable-worker.v1", "status": "LEGACY_WRITE_COMMITTED",
                "cohort": cohort, "record_id": record_id, "pid": os.getpid(),
                "authority_effect": "NONE"}
    except sqlite3.IntegrityError as error:
        if "legacy_write_fenced" not in str(error):
            raise
        return {"schema": "mmc.disposable-worker.v1", "status": "LEGACY_WRITE_FENCED",
                "cohort": cohort, "record_id": record_id,
                "database_enforcement": "SQLITE_TRIGGER", "pid": os.getpid(),
                "authority_effect": "NONE"}


def _run_worker(database: Path, cohort: str, record_id: str, payload: str) -> dict:
    environment = dict(__import__("os").environ)
    package_root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = str(package_root)
    run = subprocess.run(
        [sys.executable, "-B", "-m", "mosaic_mmc_product.disposable", "worker",
         str(database), cohort, record_id, payload],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=environment, timeout=30, check=False,
    )
    if run.returncode != 0:
        raise RuntimeError("MMC_DISPOSABLE_WORKER_FAILED:" + run.stderr.decode("utf-8", "replace")[:512])
    return decode(run.stdout)


def _inventory(rows: list[tuple]) -> list[dict]:
    return [{"id": identifier, "cohort": cohort, "payload": payload,
             "sha256": _sha(payload.encode("utf-8"))}
            for identifier, cohort, payload in rows]


def _verify_copy(source: list[dict], destination: list[tuple]) -> None:
    expected = [(row["id"], row["cohort"], row["payload"], row["sha256"]) for row in source]
    if not expected or destination != expected:
        raise RuntimeError("MMC_DISPOSABLE_SOURCE_DESTINATION_MISMATCH")


def _start_dormant(database: Path, cleanup: ExitStack) -> subprocess.Popen:
    ready = database.parent / "dormant-ready.json"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    process = subprocess.Popen(
        [sys.executable, "-B", "-m", "mosaic_mmc_product.disposable", "dormant-worker",
         str(database), str(ready)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=environment)
    def stop():
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)
    cleanup.callback(stop)
    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(.01)
    if not ready.exists() or process.poll() is not None:
        raise RuntimeError("MMC_DISPOSABLE_DORMANT_WORKER_NOT_READY")
    handshake = decode(ready.read_bytes())
    if handshake.get("checkpoint") != ["legacy-v1", 1, 1, "blue-001"] or \
            handshake.get("status") != "WAITING_FOR_RESUME" or \
            type(handshake.get("pid")) is not int or handshake["pid"] <= 0:
        raise RuntimeError("MMC_DISPOSABLE_DORMANT_CHECKPOINT")
    process.mmc_worker_pid = handshake["pid"]
    return process


def _resume_dormant(process: subprocess.Popen) -> dict:
    raw, error = process.communicate(input=b"RESUME\n", timeout=30)
    if process.returncode != 0:
        raise RuntimeError("MMC_DISPOSABLE_RESUME_FAILED:" + error.decode("utf-8", "replace")[:512])
    result = decode(raw)
    if result.get("pid") != process.mmc_worker_pid:
        raise RuntimeError("MMC_DISPOSABLE_DORMANT_PROCESS_CHANGED")
    return result


def _initialize(database: Path) -> None:
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE cohort_control(
          cohort TEXT PRIMARY KEY,
          legacy_writes_allowed INTEGER NOT NULL CHECK(legacy_writes_allowed IN (0,1)),
          route TEXT NOT NULL,
          security_floor INTEGER NOT NULL,
          revoked TEXT NOT NULL
        );
        CREATE TABLE legacy_records(
          id TEXT PRIMARY KEY,
          cohort TEXT NOT NULL REFERENCES cohort_control(cohort),
          payload TEXT NOT NULL
        );
        CREATE TABLE new_records(
          id TEXT PRIMARY KEY,
          cohort TEXT NOT NULL,
          payload TEXT NOT NULL,
          source_sha256 TEXT NOT NULL
        );
        CREATE TABLE worker_checkpoints(
          cohort TEXT PRIMARY KEY,
          runtime TEXT NOT NULL,
          resumable INTEGER NOT NULL,
          attempts INTEGER NOT NULL,
          last_record TEXT
        );
        CREATE TRIGGER enforce_legacy_fence
        BEFORE INSERT ON legacy_records
        WHEN COALESCE((SELECT legacy_writes_allowed FROM cohort_control WHERE cohort=NEW.cohort),0)=0
          OR EXISTS(SELECT 1 FROM legacy_records AS existing
                    WHERE (existing.id=NEW.id OR existing.rowid=NEW.rowid)
                      AND COALESCE((SELECT legacy_writes_allowed FROM cohort_control WHERE cohort=existing.cohort),0)=0)
        BEGIN SELECT RAISE(ABORT, 'legacy_write_fenced'); END;
        CREATE TRIGGER enforce_legacy_update_fence
        BEFORE UPDATE ON legacy_records
        WHEN COALESCE((SELECT legacy_writes_allowed FROM cohort_control WHERE cohort=OLD.cohort),0)=0
          OR COALESCE((SELECT legacy_writes_allowed FROM cohort_control WHERE cohort=NEW.cohort),0)=0
          OR EXISTS(SELECT 1 FROM legacy_records AS existing
                    WHERE (existing.id=NEW.id OR existing.rowid=NEW.rowid)
                      AND COALESCE((SELECT legacy_writes_allowed FROM cohort_control WHERE cohort=existing.cohort),0)=0)
        BEGIN SELECT RAISE(ABORT, 'legacy_write_fenced'); END;
        CREATE TRIGGER enforce_legacy_delete_fence
        BEFORE DELETE ON legacy_records
        WHEN COALESCE((SELECT legacy_writes_allowed FROM cohort_control WHERE cohort=OLD.cohort),0)=0
        BEGIN SELECT RAISE(ABORT, 'legacy_write_fenced'); END;
        CREATE TRIGGER enforce_no_legacy_reopen
        BEFORE UPDATE OF legacy_writes_allowed ON cohort_control
        WHEN OLD.legacy_writes_allowed=0 AND NEW.legacy_writes_allowed=1
        BEGIN SELECT RAISE(ABORT, 'legacy_fence_is_monotone'); END;
        """)
        connection.executemany(
            "INSERT INTO cohort_control VALUES (?,?,?,?,?)",
            [("blue", 1, "LEGACY", 4, '["revoked.key"]'),
             ("green", 1, "LEGACY", 4, '["revoked.key"]')],
        )
        connection.executemany(
            "INSERT INTO worker_checkpoints VALUES (?,?,?,?,?)",
            [("blue", "legacy-v1", 1, 0, None), ("green", "legacy-v1", 1, 0, None)],
        )


def _retirement_record(base: dict, *, ready: bool) -> dict:
    row = json.loads(json.dumps(base))
    row["now"] = 100
    row["max_age"] = 30
    row["producers"][0].update({"active": False, "can_resume": True,
                                 "fenced": ready, "legacy_capable": True})
    row["workers"][0].update({
        "status": "SUSPENDED", "code_version": "legacy", "resume_version": "legacy",
        "checkpoint_version": "checkpoint.blue.v1", "can_resume": True,
        "can_write": True, "pending_writes": 0,
        "disposition": "FENCE", "fenced": ready,
    })
    row["assets"][0].update({
        "disposition": "MIGRATED" if ready else "UNRESOLVED",
        "legacy_reader_available": False, "writer_fenced": ready,
        "retention_satisfied": ready, "hold": False,
    })
    row["consumers"][0].update({"required": True, "new_ready": ready})
    row["coverage"].update({
        "status": "DECLARED_COMPLETE" if ready else "UNKNOWN",
        "observed_at": 99, "valid_until": 120,
        "source_ref": "disposable:sqlite-observation",
    })
    row["approval"].update({
        "status": "DECLARED_APPROVED" if ready else "UNKNOWN",
        "not_before": 99, "not_after": 120,
    })
    row["recovery"].update({
        "current_floor": 5, "proposed_floor": 5,
        "current_revoked": ["revoked.key"], "proposed_revoked": ["revoked.key"],
        "plan_ref": "disposable:recovery-floor-5",
    })
    return row


def _actual_records(controller, adapter, bundle, plan, migration, step, now, sequence):
    """Build public-fixture signatures over observations read from the live DB."""
    workload = adapter.workload_snapshot()
    control = next(row for row in workload["control"] if row["cohort"] == "blue")
    if step in ("step.cutover", "step.retire"):
        source = [row for row in workload["legacy"] if row["cohort"] == "blue"]
        destination = [row for row in workload["new"] if row["cohort"] == "blue"]
        if not source or destination != [
            {**row, "source_sha256": _sha(row["payload"].encode("utf-8"))} for row in source
        ]:
            raise RuntimeError("MMC_DISPOSABLE_SOURCE_DESTINATION_MISMATCH")
    objects = {row["id"]: row for row in bundle["model"]["objects"]}
    transition = objects[step]["attributes"]
    cohort = transition["cohort"]
    roster = sorted(objects[cohort]["attributes"]["members"])
    rows = []

    def add(claim, subject, value, members=(), evidence_class="OBSERVATION"):
        rows.append(signed(plan, migration, step, "observation", {
            "claim": claim, "subject": subject, "value": deepcopy(value),
            "coverage": "COMPLETE", "members": sorted(members),
            "method": "disposable-sqlite-observation",
            "evidence_class": evidence_class,
        }, now=now, sequence=sequence))

    add("coverage", cohort, {"members": roster, "complete": True}, roster, "COVERAGE")
    for assessment in bundle["assessments"]:
        if assessment["transition"] == step:
            record = deepcopy(assessment["record"])
            if "now" in record:
                record["now"] = now
            add("domain:" + assessment["id"], assessment["subject"], record)

    retirement = next((row["record"] for row in bundle["retirements"]
                       if row["transition"] == step), None)
    if retirement is not None:
        record = deepcopy(retirement)
        record["now"] = now
        record["coverage"].update(
            observed_at=now, valid_until=now + 30,
            source_ref="disposable:sqlite-live-inventory",
        )
        record["approval"].update(not_before=now, not_after=now + 30)
        projection = controller.replay()["projection"]
        record["recovery"].update(
            current_floor=projection["floor"], proposed_floor=projection["floor"],
            current_revoked=projection["revoked"], proposed_revoked=projection["revoked"],
            plan_ref="disposable:controller-journal-recovery",
        )
        for producer in record["producers"]:
            state = adapter.snapshot([producer["id"]])[producer["id"]]["state"]
            producer["fenced"] = state in ("fenced", "retired") and not control["legacy_writes_allowed"]
        for worker in record["workers"]:
            state = adapter.snapshot([worker["id"]])[worker["id"]]["state"]
            worker["fenced"] = state in ("fenced", "retired") and not control["legacy_writes_allowed"]
        for asset in record["assets"]:
            state = adapter.snapshot([asset["id"]])[asset["id"]]["state"]
            asset["disposition"] = "MIGRATED" if state == "new" else "UNRESOLVED"
        for consumer in record["consumers"]:
            state = adapter.snapshot([consumer["id"]])[consumer["id"]]["state"]
            consumer["new_ready"] = state == "new" and control["route"] == "NEW"
        add("retirement:" + step, cohort, record, roster)
        for identifier, obj in objects.items():
            if obj["kind"] == "Observation":
                subject = obj["attributes"]["subject"]
                state = adapter.snapshot([subject])[subject]["state"]
                add("fact:" + identifier, subject,
                    state in ("fenced", "retired", "new"), (),
                    "ENFORCEMENT" if "drain" in identifier else "OBSERVATION")
    return rows


def run_disposable_migration() -> dict:
    """Execute native-controller migration, recovery, re-cutover, and retirement."""
    bundle = make_bundle("identity")
    for obj in bundle["model"]["objects"]:
        if obj["kind"] == "Effect":
            obj["attributes"]["adapter"] = DisposableSQLiteAdapter.model_adapter
    policy = reader_policy([bundle])
    policy["observers"][0]["methods"] = ["disposable-sqlite-observation"]
    policy = validate_policy(policy)
    plan = make_plan(bundle, policy)
    migration = "migration.disposable"
    now = 100
    current_time = {"now": now, "uncertainty": 0}
    temporary_root = Path(os.environ.get("MMC_DISPOSABLE_TEMP_ROOT", Path.cwd()))
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mmc-real-migration-", dir=temporary_root) as temporary, ExitStack() as cleanup:
        database = Path(temporary) / "workload.sqlite"
        journal = Path(temporary) / "controller.sqlite"
        states = {row["target"]: row["state"] for row in bundle["model"]["initial_states"]}
        adapter = DisposableSQLiteAdapter.create(
            database, "disposable.sqlite." + Path(temporary).name, states, floor=5,
            revoked=["revoked.key"],
        )
        controller = Controller.create(journal, policy)
        controller.raise_floor(5, ["revoked.key"])
        controller.submit(migration, bundle, expected_plan_root=plan["root"])
        before_blue = _run_worker(database, "blue", "blue-001", "legacy-blue")
        before_green = _run_worker(database, "green", "green-001", "legacy-green")
        dormant = _start_dormant(database, cleanup)
        unsafe = controller.assess(migration, "step.retire", current_time)
        if unsafe["body"]["status"] == "EVIDENCE_SATISFIES_SELECTED_POLICY":
            raise RuntimeError("MMC_DISPOSABLE_UNSAFE_RETIREMENT_PASSED")

        operation = 0
        effects = []
        lost_ack = None
        resumed = None
        recovery = None
        recovery_write = None

        def perform(step, *, direction="FORWARD", fault=None):
            nonlocal operation, controller
            if direction == "FORWARD":
                records = _actual_records(
                    controller, adapter, bundle, plan, migration, step, now, 5,
                )
                for record in records:
                    controller.observe(migration, record)
            assessment = controller.assess(migration, step, current_time)
            if assessment["body"]["status"] != "EVIDENCE_SATISFIES_SELECTED_POLICY":
                raise RuntimeError("MMC_DISPOSABLE_EVIDENCE_HELD:" + step)
            operation += 1
            request = controller.prepare(
                migration, step, adapter, current_time,
                operation_id=f"disposable.op.{operation}", direction=direction,
            )
            approvals = approve_records(plan, request, now)
            controller.approve(request["operation_id"], approvals, current_time)
            result = controller.commit(
                request["operation_id"], adapter, current_time, fault=fault,
            )
            effects.append({
                "transition": step, "direction": direction,
                "operation_id": request["operation_id"], "request_root": digest("request", request),
                "result": result["status"],
            })
            return request, result, assessment

        retirement_assessment = None
        for step in STEPS:
            fault = "lost_ack" if step == "step.reconcile" else None
            request, result, assessment = perform(step, fault=fault)
            if step == "step.reconcile":
                if result["status"] != "UNKNOWN":
                    raise RuntimeError("MMC_DISPOSABLE_LOST_ACK_NOT_UNKNOWN")
                controller = Controller(
                    journal, expected_policy_root=digest("policy", policy),
                )
                repaired = controller.reconcile(request["operation_id"], adapter)
                if repaired["status"] != "APPLIED":
                    raise RuntimeError("MMC_DISPOSABLE_RECONCILE_FAILED")
                lost_ack = {
                    "initial": "UNKNOWN", "after_restart": repaired["status"],
                    "operation_id": request["operation_id"],
                }
            elif result["status"] != "APPLIED":
                raise RuntimeError("MMC_DISPOSABLE_EFFECT_NOT_APPLIED:" + step)

            if step == "step.fence":
                resumed = _resume_dormant(dormant)
                if resumed["status"] != "LEGACY_WRITE_FENCED":
                    raise RuntimeError("MMC_DISPOSABLE_DORMANT_WORKER_NOT_FENCED")

            if step == "step.cutover":
                recovery_request, recovery_result, _ = perform(
                    step, direction="COMPENSATE",
                )
                snapshot = adapter.workload_snapshot()
                blue = next(row for row in snapshot["control"] if row["cohort"] == "blue")
                recovery_write = _run_worker(
                    database, "blue", "blue-003", "recovery-write-attempt",
                )
                if recovery_result["status"] != "APPLIED" or \
                        blue != {"cohort": "blue", "legacy_writes_allowed": False,
                                 "route": "RECOVERY_DUAL", "retired": False,
                                 "security_floor": 5, "revoked": ["revoked.key"]} or \
                        recovery_write["status"] != "LEGACY_WRITE_FENCED":
                    raise RuntimeError("MMC_DISPOSABLE_RECOVERY_REGRESSION")
                recovery = {
                    "operation_id": recovery_request["operation_id"],
                    "status": recovery_result["status"], "route": blue["route"],
                    "legacy_writes": recovery_write["status"],
                    "security_floor": blue["security_floor"],
                    "revoked": blue["revoked"],
                }
                _, reapplied, _ = perform(step)
                if reapplied["status"] != "APPLIED":
                    raise RuntimeError("MMC_DISPOSABLE_RECUTOVER_FAILED")

            if step == "step.retire":
                retirement_assessment = assessment

        green_after = _run_worker(database, "green", "green-002", "legacy-green-still-live")
        final_workload = adapter.workload_snapshot()
        final_targets = adapter.snapshot(sorted(states))
        final_projection = controller.replay()["projection"]
        completed = final_projection["migrations"][migration]["completed"]
        blue = next(row for row in final_workload["control"] if row["cohort"] == "blue")
        green = next(row for row in final_workload["control"] if row["cohort"] == "green")
        source = [row for row in final_workload["legacy"] if row["cohort"] == "blue"]
        destination = [row for row in final_workload["new"] if row["cohort"] == "blue"]
        expected_copy = [{**row, "source_sha256": _sha(row["payload"].encode("utf-8"))}
                         for row in source]
        if destination != expected_copy:
            raise RuntimeError("MMC_DISPOSABLE_SOURCE_DESTINATION_MISMATCH")
        if blue["route"] != "NEW" or not blue["retired"] or \
                blue["legacy_writes_allowed"] or green["route"] != "LEGACY" or \
                not green["legacy_writes_allowed"] or len(completed) != len(STEPS):
            raise RuntimeError("MMC_DISPOSABLE_FINAL_STATE")
        retirement = retirement_assessment["body"]["retirement"]
        if retirement["status"] != "MODEL_RETIREMENT_CONDITIONS_MET":
            raise RuntimeError("MMC_DISPOSABLE_RETIREMENT_HELD")
        database_sha256 = _sha(database.read_bytes())
        journal_events = controller.journal.export()

    body = {
        "schema": "mmc.disposable-migration.v2",
        "status": "PASS_NATIVE_CONTROLLER_DISPOSABLE_MIGRATION_RETIREMENT_RECOVERY",
        "environment": "TEMPORARY_SQLITE_AND_CHILD_PROCESS",
        "execution_path": "T3_NATIVE_CONTROLLER_THROUGH_DISPOSABLE_SQLITE_ADAPTER",
        "native_controller": "EXERCISED_PREPARE_APPROVE_COMMIT_RESTART_RECONCILE_COMPENSATE_RETIRE",
        "plan_root": plan["root"],
        "adapter": "DISPOSABLE_LOCAL_SQLITE_NON_PRODUCTION",
        "coverage_scope": "EXPLICIT_TEMPORARY_DATABASE_ONLY",
        "retirement_approval": "SIGNED_PUBLIC_FIXTURE_NOT_EXTERNAL_AUTHORIZATION",
        "cohort": "cohort.blue",
        "control_cohort": "cohort.green",
        "initial_writes": [before_blue, before_green],
        "dormant_worker_resume": resumed,
        "unmigrated_cohort_write": green_after,
        "unsafe_retirement_status": unsafe["body"]["status"],
        "unsafe_retirement_blockers": [row for row in unsafe["body"]["checks"] if row["outcome"] != "PASS"],
        "effects": effects,
        "lost_ack_reconciliation": lost_ack,
        "recovery": recovery,
        "migrated_records": len(destination),
        "consumer_checksum_verification": "PASS",
        "source_inventory_root": _sha(canonical(source)),
        "destination_inventory_root": _sha(canonical(destination)),
        "dormant_worker_lifecycle": "STARTED_BEFORE_MIGRATION_WAITED_THEN_RESUMED_SAME_PROCESS",
        "cohort_isolation": "PASS_GREEN_REMAINED_LEGACY_WRITABLE",
        "retirement_status": retirement["status"],
        "completed_transitions": [row["transition"] for row in completed],
        "final_targets": final_targets,
        "journal_events": len(journal_events),
        "journal_head": final_projection["head"],
        "adapter_effect_count": final_workload["effect_count"],
        "recovery_floor": 5,
        "recovery_revocations": ["revoked.key"],
        "recovery_legacy_write": recovery_write["status"],
        "database_sha256_before_disposal": database_sha256,
        "database_disposition": "DELETED_WITH_TEMPORARY_DIRECTORY",
        "production_adapter": False,
        "authority_effect": "NONE",
    }
    return {**body, "receipt_root": _sha(canonical(body))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("database"); worker.add_argument("cohort")
    worker.add_argument("record_id"); worker.add_argument("payload")
    dormant = sub.add_parser("dormant-worker")
    dormant.add_argument("database"); dormant.add_argument("ready")
    sub.add_parser("run")
    args = parser.parse_args(argv)
    if args.command == "dormant-worker":
        with closing(sqlite3.connect(args.database)) as connection:
            checkpoint = connection.execute(
                "SELECT runtime,resumable,attempts,last_record FROM worker_checkpoints WHERE cohort='blue'"
            ).fetchone()
        Path(args.ready).write_bytes(canonical({
            "status": "WAITING_FOR_RESUME", "checkpoint": list(checkpoint),
            "pid": os.getpid(),
        }))
        if sys.stdin.buffer.readline() != b"RESUME\n":
            raise RuntimeError("MMC_DISPOSABLE_RESUME_SIGNAL")
        result = _worker(Path(args.database), "blue", "blue-002", "late-legacy-blue")
    else:
        result = (_worker(Path(args.database), args.cohort, args.record_id, args.payload)
                  if args.command == "worker" else run_disposable_migration())
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
