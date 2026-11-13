"""Qualified disposable SQLite effect adapter for the native T3 controller.

This adapter performs real local database effects in a caller-selected temporary
directory.  It is deliberately non-production and has no path or network
selection surface in controller requests.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from mosaic_mmc_t3 import EffectAdapter, digest
from mosaic_mmc_t3.courts import validate_request
from mosaic_mmc_t3.storage import LostAcknowledgment, CrashInjected
from mosaic_mmc_t3.common import safe_database, token, integer, strings, closed, hashhex


# This adapter realizes one finite workload, not arbitrary state labels. Recovery
# is qualified only for cutover; inverse fencing would reopen an obsolete writer.
WORKLOAD_STEPS = {
    "step.prepare": {"producer.old": ("legacy", "prepared")},
    "step.canary": {"consumer.main": ("legacy", "canary")},
    "step.coexist": {"producer.old": ("prepared", "dual"),
                     "consumer.main": ("canary", "dual")},
    "step.fence": {"producer.old": ("dual", "fenced")},
    "step.reconcile": {"asset.legacy": ("legacy", "new")},
    "step.cutover": {"consumer.main": ("dual", "new")},
    "step.retire": {"producer.old": ("fenced", "retired")},
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class DisposableSQLiteAdapter(EffectAdapter):
    """Atomic real-workload adapter used only by disposable qualification."""

    model_adapter = "disposable.sqlite.v1"

    def __init__(self, path: Path):
        self.path = safe_database(path)
        with closing(self._connect()) as connection:
            require(connection.execute("PRAGMA application_id").fetchone()[0] == 1296917332,
                    "MMC_T7_DISPOSABLE_ADAPTER_IDENTITY")
            rows = connection.execute("SELECT raw FROM adapter_meta").fetchall()
            require(len(rows) == 1, "MMC_T7_DISPOSABLE_ADAPTER_IDENTITY")
            self.identity = decode(bytes(rows[0][0]), canonical_only=True)
        require(set(self.identity) == {"schema", "id"} and
                self.identity.get("schema") == "mmc.disposable-target.v1",
                "MMC_T7_DISPOSABLE_ADAPTER_IDENTITY")
        token(self.identity["id"])

    def _connect(self):
        safe_database(self.path)
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=30)
        try:
            require(connection.execute("PRAGMA application_id").fetchone()[0] == 1296917332,
                    "MMC_T7_DISPOSABLE_ADAPTER_IDENTITY")
            if hasattr(self, "identity"):
                rows = connection.execute("SELECT raw FROM adapter_meta").fetchall()
                require(len(rows) == 1 and bytes(rows[0][0]) == canonical(self.identity),
                        "MMC_T7_DISPOSABLE_ADAPTER_IDENTITY")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA trusted_schema=OFF")
            return connection
        except BaseException:
            connection.close()
            raise

    @classmethod
    def create(cls, path: Path, adapter_id: str, states: dict, *, floor=5,
               revoked=("revoked.key",)):
        path = safe_database(path, create=True)
        token(adapter_id); integer(floor); strings(sorted(revoked), 128)
        require(set(states) == {"producer.old", "consumer.main", "asset.legacy"},
                "MMC_T7_DISPOSABLE_TARGETS")
        require(all(value == "legacy" for value in states.values()),
                "MMC_T7_DISPOSABLE_INITIAL_STATE")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        connection = sqlite3.connect(path)
        try:
            connection.executescript("""
            PRAGMA foreign_keys=ON;
            PRAGMA application_id=1296917332;
            CREATE TABLE adapter_meta(raw BLOB NOT NULL);
            CREATE TABLE targets(id TEXT PRIMARY KEY, raw BLOB NOT NULL);
            CREATE TABLE effects(id TEXT PRIMARY KEY, raw BLOB NOT NULL);
            CREATE TABLE cohort_control(
              cohort TEXT PRIMARY KEY,
              legacy_writes_allowed INTEGER NOT NULL CHECK(legacy_writes_allowed IN (0,1)),
              route TEXT NOT NULL,
              retired INTEGER NOT NULL CHECK(retired IN (0,1)),
              security_floor INTEGER NOT NULL,
              revoked BLOB NOT NULL
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
            connection.execute("INSERT INTO adapter_meta VALUES (?)", (canonical({
                "schema": "mmc.disposable-target.v1", "id": adapter_id,
            }),))
            for target, state in sorted(states.items()):
                connection.execute("INSERT INTO targets VALUES (?,?)", (target, canonical({
                    "state": state, "version": 0, "floor": floor,
                    "revoked": sorted(revoked),
                })))
            rev = canonical(sorted(revoked))
            connection.executemany("INSERT INTO cohort_control VALUES (?,?,?,?,?,?)", [
                ("blue", 1, "LEGACY", 0, floor, rev),
                ("green", 1, "LEGACY", 0, floor, rev),
            ])
            connection.executemany("INSERT INTO worker_checkpoints VALUES (?,?,?,?,?)", [
                ("blue", "legacy-v1", 1, 0, None),
                ("green", "legacy-v1", 1, 0, None),
            ])
            connection.commit()
        finally:
            connection.close()
        return cls(path)

    def descriptor(self):
        return {
            "schema": "mmc.adapter.t3", "id": self.identity["id"],
            "mode": "DISPOSABLE_LOCAL_SQLITE", "atomic_preconditions": True,
            "idempotency": "ATOMIC_LOCAL_LEDGER", "production": False,
            "max_targets": 64, "effect": "MIGRATE_DISPOSABLE_WORKLOAD",
            "power_loss_qualification": "NOT_PERFORMED",
        }

    @staticmethod
    def _snapshot(connection, targets):
        result = {}
        for target in targets:
            row = connection.execute("SELECT raw FROM targets WHERE id=?", (target,)).fetchone()
            require(row is not None, "MMC_T3_TARGET_MISSING", target)
            value = decode(bytes(row[0]), canonical_only=True)
            closed(value, {"state", "version", "floor", "revoked"})
            token(value["state"]); integer(value["version"]); integer(value["floor"])
            strings(value["revoked"], 128)
            result[target] = value
        return result

    def snapshot(self, targets):
        strings(targets, 64)
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            return self._snapshot(connection, targets)

    def lookup(self, op_id, request_root):
        token(op_id); hashhex(request_root)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT raw FROM effects WHERE id=?", (op_id,)).fetchone()
            if row is None:
                return {"status": "ABSENT_FROM_LOCAL_LEDGER", "effects": "NOT_RECORDED"}
            result = decode(bytes(row[0]), canonical_only=True)
            require(result["request_root"] == request_root, "MMC_T3_IDEMPOTENCY_CONFLICT")
            return result

    @staticmethod
    def _verify_inventory(connection):
        source = connection.execute(
            "SELECT id,cohort,payload FROM legacy_records WHERE cohort='blue' ORDER BY id"
        ).fetchall()
        destination = connection.execute(
            "SELECT id,cohort,payload,source_sha256 FROM new_records WHERE cohort='blue' ORDER BY id"
        ).fetchall()
        expected = [(*row, _sha(row[2].encode("utf-8"))) for row in source]
        require(bool(source) and destination == expected,
                "MMC_DISPOSABLE_SOURCE_DESTINATION_MISMATCH")

    @staticmethod
    def _apply_workload(connection, request):
        transition = request["scope"]["transition"]
        direction = request["direction"]
        post = request["post_state"]
        states = {target: value["state"] for target, value in post.items()}
        require(request["scope"]["cohort"] == "cohort.blue" and
                transition in WORKLOAD_STEPS, "MMC_T7_DISPOSABLE_SCOPE")
        require(direction == "FORWARD" or transition == "step.cutover",
                "MMC_T7_DISPOSABLE_COMPENSATION_UNSUPPORTED")
        mapping = WORKLOAD_STEPS[transition]
        pre_index, post_index = (0, 1) if direction == "FORWARD" else (1, 0)
        require({key: value["state"] for key, value in request["pre_state"].items()} ==
                {key: value[pre_index] for key, value in mapping.items()} and
                states == {key: value[post_index] for key, value in mapping.items()},
                "MMC_T7_DISPOSABLE_REQUEST_STATES")
        allowed, route, retired = connection.execute(
            "SELECT legacy_writes_allowed,route,retired FROM cohort_control WHERE cohort='blue'"
        ).fetchone()
        require(retired == 0, "MMC_T7_DISPOSABLE_ALREADY_RETIRED")
        expected_routes = {
            "step.prepare": {"LEGACY"}, "step.canary": {"PREPARED"},
            "step.coexist": {"CANARY"}, "step.fence": {"DUAL"},
            "step.reconcile": {"DUAL"},
            "step.cutover": {"DUAL", "RECOVERY_DUAL"} if direction == "FORWARD" else {"NEW"},
            "step.retire": {"NEW"},
        }
        require(route in expected_routes[transition], "MMC_T7_DISPOSABLE_LIVE_ROUTE")
        if transition == "step.prepare":
            connection.execute("UPDATE cohort_control SET route='PREPARED' WHERE cohort='blue'")
        elif transition == "step.canary":
            connection.execute("UPDATE cohort_control SET route='CANARY' WHERE cohort='blue'")
        elif transition == "step.coexist":
            connection.execute("UPDATE cohort_control SET route='DUAL' WHERE cohort='blue'")
        elif transition == "step.fence":
            connection.execute("UPDATE cohort_control SET legacy_writes_allowed=0 WHERE cohort='blue'")
        elif transition == "step.reconcile":
            fenced = connection.execute(
                "SELECT legacy_writes_allowed FROM cohort_control WHERE cohort='blue'"
            ).fetchone()[0]
            require(fenced == 0, "MMC_T7_DISPOSABLE_COPY_BEFORE_FENCE")
            rows = connection.execute(
                "SELECT id,cohort,payload FROM legacy_records WHERE cohort='blue' ORDER BY id"
            ).fetchall()
            require(bool(rows), "MMC_T7_DISPOSABLE_EMPTY_SOURCE")
            for identifier, cohort, payload in rows:
                connection.execute(
                    "INSERT INTO new_records VALUES (?,?,?,?)",
                    (identifier, cohort, payload, _sha(payload.encode("utf-8"))),
                )
        elif transition == "step.cutover":
            require(allowed == 0, "MMC_T7_DISPOSABLE_CUTOVER_BEFORE_FENCE")
            if direction == "FORWARD":
                DisposableSQLiteAdapter._verify_inventory(connection)
            route = "RECOVERY_DUAL" if direction == "COMPENSATE" else "NEW"
            connection.execute("UPDATE cohort_control SET route=? WHERE cohort='blue'", (route,))
        elif transition == "step.retire":
            require(allowed == 0 and route == "NEW", "MMC_T7_DISPOSABLE_RETIRE_BEFORE_CUTOVER")
            DisposableSQLiteAdapter._verify_inventory(connection)
            connection.execute(
                "UPDATE cohort_control SET retired=? WHERE cohort='blue'",
                (1 if states.get("producer.old") == "retired" else 0,),
            )
        else:
            require(False, "MMC_T7_DISPOSABLE_TRANSITION", transition)

    def apply(self, request, *, fault=None):
        require(fault in (None, "before", "lost_ack", "crash_after"),
                "MMC_T7_DISPOSABLE_FAULT_MODE")
        validate_request(request)
        request_root = digest("request", request)
        operation_id = request["operation_id"]
        if fault == "before":
            return {"status": "NOT_APPLIED", "request_root": request_root,
                    "effects": "NONE_CONFIRMED"}
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT raw FROM effects WHERE id=?", (operation_id,)).fetchone()
            if row is not None:
                result = decode(bytes(row[0]), canonical_only=True)
                require(result["request_root"] == request_root, "MMC_T3_IDEMPOTENCY_CONFLICT")
                connection.commit()
                return result
            require(request["adapter"] == self.descriptor(), "MMC_T3_ADAPTER_SUBSTITUTION")
            targets = request["scope"]["targets"]
            actual = self._snapshot(connection, targets)
            require(canonical(actual) == canonical(request["pre_state"]),
                    "MMC_T3_PRECONDITION_CHANGED")
            self._apply_workload(connection, request)
            for target in targets:
                before = actual[target]
                after = request["post_state"][target]
                require(after["floor"] >= before["floor"] and
                        set(before["revoked"]) <= set(after["revoked"]),
                        "MMC_T3_SECURITY_FLOOR")
                connection.execute("UPDATE targets SET raw=? WHERE id=?", (canonical({
                    **after, "version": before["version"] + 1,
                }), target))
            prior_floor, prior_revoked = connection.execute(
                "SELECT security_floor,revoked FROM cohort_control WHERE cohort='blue'"
            ).fetchone()
            floor = max(prior_floor, *(value["floor"] for value in request["post_state"].values()))
            revoked = sorted(set(decode(bytes(prior_revoked))).union(
                *(set(value["revoked"]) for value in request["post_state"].values())))
            connection.execute(
                "UPDATE cohort_control SET security_floor=?,revoked=? WHERE cohort='blue'",
                (floor, canonical(revoked)),
            )
            result = {
                "schema": "mmc.disposable-effect.v1", "operation_id": operation_id,
                "request_root": request_root, "status": "APPLIED",
                "changed": targets, "post_state": self._snapshot(connection, targets),
                "effects": "DISPOSABLE_SQLITE_WORKLOAD_CHANGED",
                "authority_effect": "NONE",
            }
            connection.execute("INSERT INTO effects VALUES (?,?)",
                               (operation_id, canonical(result)))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        if fault == "lost_ack":
            raise LostAcknowledgment("Disposable effect committed; acknowledgment lost")
        if fault == "crash_after":
            raise CrashInjected("Disposable effect committed before acknowledgment")
        return result

    def workload_snapshot(self):
        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            control = connection.execute(
                "SELECT cohort,legacy_writes_allowed,route,retired,security_floor,revoked "
                "FROM cohort_control ORDER BY cohort"
            ).fetchall()
            legacy = connection.execute(
                "SELECT id,cohort,payload FROM legacy_records ORDER BY id"
            ).fetchall()
            new = connection.execute(
                "SELECT id,cohort,payload,source_sha256 FROM new_records ORDER BY id"
            ).fetchall()
            effects = connection.execute("SELECT count(*) FROM effects").fetchone()[0]
        return {
            "control": [{"cohort": row[0], "legacy_writes_allowed": bool(row[1]),
                         "route": row[2], "retired": bool(row[3]),
                         "security_floor": row[4], "revoked": decode(bytes(row[5]))}
                        for row in control],
            "legacy": [{"id": row[0], "cohort": row[1], "payload": row[2]}
                       for row in legacy],
            "new": [{"id": row[0], "cohort": row[1], "payload": row[2],
                     "source_sha256": row[3]} for row in new],
            "effect_count": effects,
        }

