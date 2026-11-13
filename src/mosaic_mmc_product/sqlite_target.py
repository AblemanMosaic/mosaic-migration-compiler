"""Host-enrolled migration of existing SQLite TEXT tables.

The host selects a manifest, never SQL or a module from an effect request. The
customer database exists before enrollment. Target state, copied rows and the
idempotency ledger share one SQLite transaction. This is a cooperating-host
adapter; it does not isolate a malicious database owner or qualify power loss.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import sqlite3
import uuid

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from mosaic_mmc_t3 import EffectAdapter, digest
from mosaic_mmc_t3.common import closed, hashhex, integer, safe_database, strings, token
from mosaic_mmc_t3.courts import validate_request
from mosaic_mmc_t3.storage import CrashInjected, LostAcknowledgment
from .adapter import WORKLOAD_STEPS

PREFIX = "mmc_target_"
TABLES = {"enrollment", "states", "effects", "control"}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", value)
            and not value.lower().startswith(("sqlite_", PREFIX)), "MMC_SQLITE_TARGET_IDENTIFIER")
    return '"' + value + '"'


def validate_manifest(value):
    closed(value, {"schema", "id", "migration_id", "cohort_id", "cohort", "cohorts",
                   "source_table", "destination_table", "id_column", "cohort_column",
                   "payload_column", "checksum_column", "target_ids", "max_rows", "max_payload_bytes"})
    require(value["schema"] == "mmc.sqlite-target-enrollment.v1", "MMC_SQLITE_TARGET_MANIFEST")
    for key in ("id", "migration_id", "cohort_id", "cohort"):
        token(value[key])
    require(len(value["id"]) <= 90, "MMC_SQLITE_TARGET_ID_LENGTH")
    strings(value["cohorts"], 32)
    require(value["cohort"] in value["cohorts"] and len(value["cohorts"]) >= 1,
            "MMC_SQLITE_TARGET_COHORTS")
    for key in ("source_table", "destination_table", "id_column", "cohort_column", "payload_column", "checksum_column"):
        identifier(value[key])
    require(value["source_table"].lower() != value["destination_table"].lower(), "MMC_SQLITE_TARGET_TABLE_ALIAS")
    columns = [value[key].lower() for key in ("id_column", "cohort_column", "payload_column", "checksum_column")]
    require(len(set(columns)) == 4, "MMC_SQLITE_TARGET_COLUMN_ALIAS")
    closed(value["target_ids"], {"producer", "consumer", "asset"})
    for key in value["target_ids"].values(): token(key)
    require(len(set(value["target_ids"].values())) == 3, "MMC_SQLITE_TARGET_ROLE_ALIAS")
    integer(value["max_rows"], 1, 512); integer(value["max_payload_bytes"], 1, 65536)
    return deepcopy(value)


class SQLiteTargetAdapter(EffectAdapter):
    model_adapter = "sqlite.table-migration.v1"

    def __init__(self, path):
        self.path = safe_database(path)
        with closing(self._connect()) as con:
            con.execute("BEGIN")
            rows = con.execute("SELECT raw FROM mmc_target_enrollment").fetchall()
            require(len(rows) == 1, "MMC_SQLITE_TARGET_ENROLLMENT")
            record = decode(bytes(rows[0][0]), canonical_only=True, limit=2 * 1024 * 1024)
            closed(record, {"body", "root"})
            require(_hash(canonical(record["body"])) == record["root"], "MMC_SQLITE_TARGET_ENROLLMENT_HASH")
            self.enrollment = record
            self.manifest = validate_manifest(record["body"]["manifest"])
            self.identity = {"schema": "mmc.sqlite-target.v1", "id": self.manifest["id"] + "." + record["root"]}
            token(self.identity["id"])
            self._check_schema(con)

    def _connect(self):
        safe_database(self.path)
        con = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=30)
        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("PRAGMA trusted_schema=OFF")
            if hasattr(self, "enrollment"):
                rows = con.execute("SELECT raw FROM mmc_target_enrollment").fetchall()
                require(len(rows) == 1 and bytes(rows[0][0]) == canonical(self.enrollment),
                        "MMC_SQLITE_TARGET_IDENTITY_CHANGED")
            return con
        except BaseException:
            con.close(); raise

    @classmethod
    def enroll(cls, path, manifest, states, *, floor=5, revoked=("revoked.key",)):
        path = safe_database(path)
        manifest = validate_manifest(manifest)
        integer(floor); strings(sorted(revoked), 128)
        require(type(states) is dict and set(states) == set(manifest["target_ids"].values()) and
                all(value == "legacy" for value in states.values()), "MMC_SQLITE_TARGET_INITIAL_STATES")
        con = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=30)
        try:
            con.execute("PRAGMA trusted_schema=OFF"); con.execute("BEGIN IMMEDIATE")
            require(not con.execute("SELECT 1 FROM sqlite_master WHERE lower(name) LIKE 'mmc_target_%'").fetchone(),
                    "MMC_SQLITE_TARGET_ALREADY_ENROLLED")
            source_sql = cls._table_shape(con, manifest, False)
            destination_sql = cls._table_shape(con, manifest, True)
            require(not con.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name IN (?,?)",
                                    (manifest["source_table"], manifest["destination_table"])).fetchone(),
                    "MMC_SQLITE_TARGET_FOREIGN_TRIGGER")
            cls._rows(con, manifest, False)
            require(not con.execute(f"SELECT 1 FROM {identifier(manifest['destination_table'])} WHERE {identifier(manifest['cohort_column'])} COLLATE BINARY=? LIMIT 1",
                                    (manifest["cohort"],)).fetchone(), "MMC_SQLITE_TARGET_DESTINATION_NOT_EMPTY")
            cls._rows(con, manifest, True)
            ddl = [
                "CREATE TABLE mmc_target_enrollment(raw BLOB NOT NULL)",
                "CREATE TABLE mmc_target_states(id TEXT PRIMARY KEY, raw BLOB NOT NULL)",
                "CREATE TABLE mmc_target_effects(id TEXT PRIMARY KEY, raw BLOB NOT NULL)",
                "CREATE TABLE mmc_target_control(cohort TEXT PRIMARY KEY, legacy_writes_allowed INTEGER NOT NULL CHECK(legacy_writes_allowed IN(0,1)), route TEXT NOT NULL, retired INTEGER NOT NULL CHECK(retired IN(0,1)), security_floor INTEGER NOT NULL, revoked BLOB NOT NULL)",
            ]
            for statement in ddl: con.execute(statement)
            for name, state in sorted(states.items()):
                con.execute("INSERT INTO mmc_target_states VALUES (?,?)", (name, canonical({"state": state, "version": 0, "floor": floor, "revoked": sorted(revoked)})))
            con.executemany("INSERT INTO mmc_target_control VALUES (?,1,'LEGACY',0,?,?)",
                            [(cohort, floor, canonical(sorted(revoked))) for cohort in manifest["cohorts"]])
            source = identifier(manifest["source_table"]); cohort = identifier(manifest["cohort_column"])
            # REPLACE may delete a conflicting row without firing its DELETE
            # trigger on an independent connection with recursive_triggers=OFF.
            # Check conflicts before INSERT/UPDATE, including every admitted
            # unique index and the hidden rowid when it is addressable.
            conflict = cls._protected_source_conflict(con, manifest)
            # A REPLACE policy can substitute a NOT NULL column's default only
            # after BEFORE triggers. Reject explicit NULL before it can acquire
            # a protected key or cohort. Omitted defaults are already in NEW.
            nulls = " OR ".join(f"NEW.{identifier(manifest[key])} IS NULL"
                                for key in ("id_column", "cohort_column", "payload_column"))
            conditions = {
                "insert": f"{nulls} OR COALESCE((SELECT legacy_writes_allowed FROM mmc_target_control WHERE cohort=NEW.{cohort}),0)=0 OR {conflict}",
                "update": f"{nulls} OR COALESCE((SELECT legacy_writes_allowed FROM mmc_target_control WHERE cohort=OLD.{cohort}),0)=0 OR COALESCE((SELECT legacy_writes_allowed FROM mmc_target_control WHERE cohort=NEW.{cohort}),0)=0 OR {conflict}",
                "delete": f"COALESCE((SELECT legacy_writes_allowed FROM mmc_target_control WHERE cohort=OLD.{cohort}),0)=0",
            }
            for operation, condition in conditions.items():
                con.execute(f"CREATE TRIGGER mmc_target_fence_{operation} BEFORE {operation.upper()} ON {source} WHEN {condition} BEGIN SELECT RAISE(ABORT,'legacy_write_fenced'); END")
            con.execute("CREATE TRIGGER mmc_target_no_reopen BEFORE UPDATE OF legacy_writes_allowed ON mmc_target_control WHEN OLD.legacy_writes_allowed=0 AND NEW.legacy_writes_allowed=1 BEGIN SELECT RAISE(ABORT,'legacy_fence_is_monotone'); END")
            body = {"schema": "mmc.sqlite-target-custody.v1", "manifest": manifest, "nonce": uuid.uuid4().hex,
                    "source_sql": source_sql, "destination_sql": destination_sql,
                    "owned_sql": cls._owned_sql(con, manifest)}
            record = {"body": body, "root": _hash(canonical(body))}
            con.execute("INSERT INTO mmc_target_enrollment VALUES (?)", (canonical(record),))
            con.commit()
        except BaseException:
            con.rollback(); raise
        finally:
            con.close()
        return cls(path)

    @staticmethod
    def _protected_source_conflict(con, manifest):
        source = identifier(manifest["source_table"])
        fields = {manifest[key] for key in ("id_column", "cohort_column", "payload_column")}
        conflicts = []
        for name, partial in con.execute('SELECT name,partial FROM pragma_index_list(?) WHERE "unique"=1 ORDER BY name',
                                         (manifest["source_table"],)):
            require(partial == 0, "MMC_SQLITE_TARGET_SOURCE_UNIQUE_INDEX")
            columns = []
            for cid, column, collation in con.execute('SELECT cid,name,coll FROM pragma_index_xinfo(?) WHERE "key"=1 ORDER BY seqno', (name,)):
                require(cid >= 0 and column in fields and type(collation) is str and
                        collation.upper() in {"BINARY", "NOCASE", "RTRIM"},
                        "MMC_SQLITE_TARGET_SOURCE_UNIQUE_INDEX")
                columns.append(f"mmc_existing.{identifier(column)} COLLATE {collation.upper()}=NEW.{identifier(column)} COLLATE {collation.upper()}")
            require(bool(columns), "MMC_SQLITE_TARGET_SOURCE_UNIQUE_INDEX")
            conflicts.append("(" + " AND ".join(columns) + ")")
        for alias in ("rowid", "_rowid_", "oid"):
            if alias in {column.lower() for column in fields}:
                continue
            # Qualified lookup avoids SQLite's double-quoted string fallback
            # for WITHOUT ROWID tables. No input expression is executed.
            try:
                con.execute(f'SELECT mmc_existing."{alias}" FROM {source} AS mmc_existing LIMIT 0')
            except sqlite3.OperationalError as error:
                if str(error) != f"no such column: mmc_existing.{alias}":
                    raise
            else:
                conflicts.append(f'mmc_existing."{alias}"=NEW."{alias}"')
            break
        require(bool(conflicts), "MMC_SQLITE_TARGET_SOURCE_UNIQUE_INDEX")
        cohort = identifier(manifest["cohort_column"])
        return (f"EXISTS(SELECT 1 FROM {source} AS mmc_existing WHERE "
                f"COALESCE((SELECT legacy_writes_allowed FROM mmc_target_control WHERE cohort=mmc_existing.{cohort} COLLATE BINARY),0)=0 "
                "AND (" + " OR ".join(conflicts) + "))")

    @staticmethod
    def _owned_sql(con, manifest):
        # A trigger's name is not its effect scope. Pin every schema object
        # attached to every table this adapter reads or writes, including
        # foreign-named triggers/indexes and SQLite-generated primary indexes.
        tables = [PREFIX + name for name in sorted(TABLES)] + [manifest["source_table"], manifest["destination_table"]]
        placeholders = ",".join("?" for _ in tables)
        return {name: sql for name, sql in con.execute(
            "SELECT name,sql FROM sqlite_master WHERE name LIKE 'mmc_target_%' OR tbl_name IN (" + placeholders + ") ORDER BY name", tables)}

    @staticmethod
    def _table_shape(con, manifest, destination):
        table = manifest["destination_table" if destination else "source_table"]
        row = con.execute("SELECT name,type,sql FROM sqlite_master WHERE name=? COLLATE NOCASE", (table,)).fetchone()
        require(row is not None and row[0] == table and row[1] == "table" and row[2].upper().startswith("CREATE TABLE"), "MMC_SQLITE_TARGET_TABLE_KIND")
        fields = [manifest[key] for key in ("id_column", "cohort_column", "payload_column")]
        if destination: fields.append(manifest["checksum_column"])
        info = con.execute(f"PRAGMA table_xinfo({identifier(table)})").fetchall()
        require(len(info) == len(fields) and {value[1] for value in info} == set(fields) and all(
            value[2].upper() == "TEXT" and value[3] == 1 and value[6] == 0 and
            value[5] == int(value[1] == manifest["id_column"]) for value in info), "MMC_SQLITE_TARGET_TABLE_SHAPE")
        require(not con.execute(f"PRAGMA foreign_key_list({identifier(table)})").fetchall(), "MMC_SQLITE_TARGET_FOREIGN_KEY")
        return row[2]

    def _check_schema(self, con):
        body = self.enrollment["body"]
        require(self._table_shape(con, self.manifest, False) == body["source_sql"] and
                self._table_shape(con, self.manifest, True) == body["destination_sql"] and
                self._owned_sql(con, self.manifest) == body["owned_sql"], "MMC_SQLITE_TARGET_SCHEMA_CHANGED")
        allowed = {name for name in body["owned_sql"] if name.startswith("mmc_target_fence_")}
        triggers = {name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name IN (?,?)",
                                                   (self.manifest["source_table"], self.manifest["destination_table"]))}
        require(triggers == allowed, "MMC_SQLITE_TARGET_FOREIGN_TRIGGER")

    @staticmethod
    def _rows(con, manifest, destination, selected=False):
        fields = [manifest[key] for key in ("id_column", "cohort_column", "payload_column")]
        if destination: fields.append(manifest["checksum_column"])
        table = identifier(manifest["destination_table" if destination else "source_table"])
        where = " WHERE " + identifier(manifest["cohort_column"]) + " COLLATE BINARY=?" if selected else ""
        values = (manifest["cohort"],) if selected else ()
        rows = con.execute("SELECT " + ",".join(map(identifier, fields)) + " FROM " + table + where +
                           " ORDER BY " + identifier(manifest["id_column"]) + " COLLATE BINARY LIMIT ?", (*values, manifest["max_rows"] + 1)).fetchall()
        require(len(rows) <= manifest["max_rows"], "MMC_SQLITE_TARGET_ROW_LIMIT")
        for row in rows:
            require(all(type(value) is str for value in row) and row[1] in manifest["cohorts"] and
                    all(len(value.encode("utf-8")) <= manifest["max_payload_bytes"] for value in row[:3]), "MMC_SQLITE_TARGET_ROW_TYPE")
            if destination: hashhex(row[3])
        return rows

    def descriptor(self):
        return {"schema": "mmc.adapter.t3", "id": self.identity["id"], "mode": "SQLITE_TABLE_MIGRATION",
                "atomic_preconditions": True, "idempotency": "ATOMIC_LOCAL_LEDGER", "production": False,
                "max_targets": 64, "effect": "MIGRATE_ENROLLED_SQLITE_TABLES", "power_loss_qualification": "NOT_PERFORMED"}

    def _snapshot(self, con, targets):
        result = {}
        for target in targets:
            row = con.execute("SELECT raw FROM mmc_target_states WHERE id=?", (target,)).fetchone()
            require(row is not None, "MMC_T3_TARGET_MISSING")
            value = decode(bytes(row[0]), canonical_only=True)
            closed(value, {"state", "version", "floor", "revoked"})
            token(value["state"]); integer(value["version"]); integer(value["floor"]); strings(value["revoked"], 128)
            result[target] = value
        return result

    def snapshot(self, targets):
        strings(targets, 64)
        with closing(self._connect()) as con:
            con.execute("BEGIN"); self._check_schema(con)
            return self._snapshot(con, targets)

    def lookup(self, op_id, request_root):
        token(op_id); hashhex(request_root)
        with closing(self._connect()) as con:
            con.execute("BEGIN"); self._check_schema(con)
            row = con.execute("SELECT raw FROM mmc_target_effects WHERE id=?", (op_id,)).fetchone()
            if row is None: return {"status": "ABSENT_FROM_LOCAL_LEDGER", "effects": "NOT_RECORDED"}
            result = decode(bytes(row[0]), canonical_only=True)
            require(result["request_root"] == request_root, "MMC_T3_IDEMPOTENCY_CONFLICT")
            return result

    def _inventory(self, con):
        source = self._rows(con, self.manifest, False, True)
        target = self._rows(con, self.manifest, True, True)
        expected = [(*row, _hash(row[2].encode("utf-8"))) for row in source]
        require(target == expected, "MMC_SQLITE_TARGET_INVENTORY_MISMATCH")

    def _workload(self, con, request):
        m = self.manifest; scope = request["scope"]; step = scope["transition"]; direction = request["direction"]
        require(scope["migration"] == m["migration_id"] and scope["cohort"] == m["cohort_id"] and step in WORKLOAD_STEPS,
                "MMC_SQLITE_TARGET_SCOPE")
        require(direction == "FORWARD" or step == "step.cutover", "MMC_SQLITE_TARGET_COMPENSATION")
        aliases = dict(zip(("producer.old", "consumer.main", "asset.legacy"), (m["target_ids"][role] for role in ("producer", "consumer", "asset"))))
        mapping = {aliases[name]: pair for name, pair in WORKLOAD_STEPS[step].items()}
        before, after = (0, 1) if direction == "FORWARD" else (1, 0)
        require({name: value["state"] for name, value in request["pre_state"].items()} == {name: pair[before] for name, pair in mapping.items()} and
                {name: value["state"] for name, value in request["post_state"].items()} == {name: pair[after] for name, pair in mapping.items()}, "MMC_SQLITE_TARGET_STATES")
        allowed, route, retired = con.execute("SELECT legacy_writes_allowed,route,retired FROM mmc_target_control WHERE cohort=?", (m["cohort"],)).fetchone()
        routes = {"step.prepare": {"LEGACY"}, "step.canary": {"PREPARED"}, "step.coexist": {"CANARY"}, "step.fence": {"DUAL"},
                  "step.reconcile": {"DUAL"}, "step.cutover": {"DUAL", "RECOVERY_DUAL"} if direction == "FORWARD" else {"NEW"}, "step.retire": {"NEW"}}
        require(retired == 0 and route in routes[step], "MMC_SQLITE_TARGET_LIVE_ROUTE")
        if step in ("step.prepare", "step.canary", "step.coexist"):
            route = {"step.prepare": "PREPARED", "step.canary": "CANARY", "step.coexist": "DUAL"}[step]
            con.execute("UPDATE mmc_target_control SET route=? WHERE cohort=?", (route, m["cohort"]))
        elif step == "step.fence":
            con.execute("UPDATE mmc_target_control SET legacy_writes_allowed=0 WHERE cohort=?", (m["cohort"],))
        elif step == "step.reconcile":
            require(allowed == 0, "MMC_SQLITE_TARGET_COPY_BEFORE_FENCE")
            columns = [m[key] for key in ("id_column", "cohort_column", "payload_column", "checksum_column")]
            # Override customer schema conflict policies: a copied row must not
            # replace a control tenant or be silently ignored.
            sql = "INSERT OR ABORT INTO " + identifier(m["destination_table"]) + "(" + ",".join(map(identifier, columns)) + ") VALUES (?,?,?,?)"
            con.executemany(sql, [(*row, _hash(row[2].encode("utf-8"))) for row in self._rows(con, m, False, True)])
        elif step == "step.cutover":
            require(allowed == 0, "MMC_SQLITE_TARGET_CUTOVER_BEFORE_FENCE")
            self._inventory(con)
            con.execute("UPDATE mmc_target_control SET route=? WHERE cohort=?", ("NEW" if direction == "FORWARD" else "RECOVERY_DUAL", m["cohort"]))
        else:
            require(allowed == 0 and route == "NEW", "MMC_SQLITE_TARGET_RETIRE_BEFORE_CUTOVER")
            self._inventory(con)
            con.execute("UPDATE mmc_target_control SET retired=1 WHERE cohort=?", (m["cohort"],))

    def apply(self, request, *, fault=None):
        require(fault in (None, "before", "lost_ack", "crash_after"), "MMC_SQLITE_TARGET_FAULT")
        validate_request(request)
        root = digest("request", request); operation = request["operation_id"]
        if fault == "before": return {"status": "NOT_APPLIED", "request_root": root, "effects": "NONE_CONFIRMED"}
        with closing(self._connect()) as con:
            try:
                con.execute("BEGIN IMMEDIATE"); self._check_schema(con)
                require(request["adapter"] == self.descriptor(), "MMC_T3_ADAPTER_SUBSTITUTION")
                prior = con.execute("SELECT raw FROM mmc_target_effects WHERE id=?", (operation,)).fetchone()
                if prior:
                    result = decode(bytes(prior[0]), canonical_only=True)
                    require(result["request_root"] == root, "MMC_T3_IDEMPOTENCY_CONFLICT")
                    con.commit(); return result
                targets = request["scope"]["targets"]
                current = self._snapshot(con, targets)
                require(canonical(current) == canonical(request["pre_state"]), "MMC_T3_PRECONDITION_CHANGED")
                floor, revoked = con.execute("SELECT security_floor,revoked FROM mmc_target_control WHERE cohort=?", (self.manifest["cohort"],)).fetchone()
                live_revoked = set(decode(bytes(revoked)))
                for name in targets:
                    post = request["post_state"][name]
                    require(post["floor"] >= max(current[name]["floor"], floor) and
                            set(current[name]["revoked"]) | live_revoked <= set(post["revoked"]), "MMC_T3_SECURITY_FLOOR")
                self._workload(con, request)
                for name in targets:
                    post = request["post_state"][name]
                    con.execute("UPDATE mmc_target_states SET raw=? WHERE id=?", (canonical({**post, "version": current[name]["version"] + 1}), name))
                floor = max(floor, *(value["floor"] for value in request["post_state"].values()))
                revoked = sorted(set(decode(bytes(revoked))).union(*(set(value["revoked"]) for value in request["post_state"].values())))
                con.execute("UPDATE mmc_target_control SET security_floor=?,revoked=? WHERE cohort=?", (floor, canonical(revoked), self.manifest["cohort"]))
                result = {"schema": "mmc.sqlite-target-effect.v1", "operation_id": operation, "request_root": root,
                          "status": "APPLIED", "changed": targets, "post_state": self._snapshot(con, targets),
                          "effects": "ENROLLED_SQLITE_TABLES_CHANGED", "authority_effect": "NONE"}
                con.execute("INSERT INTO mmc_target_effects VALUES (?,?)", (operation, canonical(result))); con.commit()
            except BaseException:
                con.rollback(); raise
        if fault == "lost_ack": raise LostAcknowledgment("Target transaction committed; reply lost")
        if fault == "crash_after": raise CrashInjected("Target transaction committed; worker exits before reply")
        return result

    def workload_snapshot(self):
        with closing(self._connect()) as con:
            con.execute("BEGIN"); self._check_schema(con)
            control = con.execute("SELECT cohort,legacy_writes_allowed,route,retired,security_floor,revoked FROM mmc_target_control ORDER BY cohort").fetchall()
            source = self._rows(con, self.manifest, False)
            destination = self._rows(con, self.manifest, True)
            count = con.execute("SELECT count(*) FROM mmc_target_effects").fetchone()[0]
        return {"enrollment_root": self.enrollment["root"], "control": [
            {"cohort": row[0], "legacy_writes_allowed": bool(row[1]), "route": row[2], "retired": bool(row[3]), "security_floor": row[4], "revoked": decode(bytes(row[5]))} for row in control],
            "legacy": [{"id": row[0], "cohort": row[1], "payload": row[2]} for row in source],
            "new": [{"id": row[0], "cohort": row[1], "payload": row[2], "source_sha256": row[3]} for row in destination], "effect_count": count}
