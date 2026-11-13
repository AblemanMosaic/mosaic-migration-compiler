"""Actual customer-table enrollment, atomicity and storage enforcement witnesses."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import MMCError, canonical
from mosaic_mmc_t3 import digest
from mosaic_mmc_t3.storage import LostAcknowledgment
from mosaic_mmc_product.adapter import WORKLOAD_STEPS
from mosaic_mmc_product.sqlite_target import SQLiteTargetAdapter
from mosaic_mmc_product.target_qualification import qualification_manifest, initialize_customer_database, run_target_qualification


class SQLiteTargetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mmc-target-test-", dir=ROOT.parent)
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "customer.sqlite"
        initialize_customer_database(self.database)
        self.manifest = qualification_manifest()
        self.states = dict.fromkeys(["producer.old", "consumer.main", "asset.legacy"], "legacy")
        self.number = 0

    def enroll(self):
        self.adapter = SQLiteTargetAdapter.enroll(self.database, self.manifest, self.states)
        return self.adapter

    def sql(self, statement, parameters=()):
        with closing(sqlite3.connect(self.database)) as con, con:
            return con.execute(statement, parameters).fetchall()

    def request(self, step, direction="FORWARD"):
        self.number += 1
        mapping = WORKLOAD_STEPS[step]; targets = sorted(mapping)
        before = self.adapter.snapshot(targets)
        return {"schema": "mmc.effect-request.t3", "operation_id": f"target.test.{self.number}",
                "scope": {"migration": self.manifest["migration_id"], "cohort": self.manifest["cohort_id"],
                          "transition": step, "targets": targets, "plan_root": "0" * 64, "policy_root": "1" * 64},
                "context_root": "2" * 64, "direction": direction, "compensates": None if direction == "FORWARD" else "accepted.previous",
                "adapter": self.adapter.descriptor(), "pre_state": before,
                "post_state": {target: {"state": mapping[target][1 if direction == "FORWARD" else 0],
                                        "floor": value["floor"], "revoked": value["revoked"]} for target, value in before.items()},
                "prepared_at": 100, "expires_at": 130, "max_attempts": 2}

    def advance(self, end):
        for step in WORKLOAD_STEPS:
            self.adapter.apply(self.request(step))
            if step == end: break

    def test_enrollment_preserves_customer_tables_rows_and_application_id(self):
        before = self.sql("SELECT * FROM customer_credentials_v1 ORDER BY credential_id")
        self.sql("PRAGMA application_id=1666")
        self.enroll()
        self.assertEqual(self.sql("SELECT * FROM customer_credentials_v1 ORDER BY credential_id"), before)
        self.assertEqual(self.sql("PRAGMA application_id"), [(1666,)])
        self.assertIn(self.adapter.enrollment["root"], self.adapter.descriptor()["id"])

    def test_manifest_sql_injection_and_case_aliases_refuse_before_enrollment(self):
        for source in ("customer_credentials_v1; DROP TABLE customer_credentials_v2", "CUSTOMER_CREDENTIALS_V1"):
            value = deepcopy(self.manifest); value["source_table"] = source
            with self.assertRaises(MMCError): SQLiteTargetAdapter.enroll(self.database, value, self.states)
        self.assertEqual(self.sql("SELECT count(*) FROM customer_credentials_v1"), [(33,)])
        self.assertFalse(self.sql("SELECT name FROM sqlite_master WHERE name='mmc_target_enrollment'"))

    def test_exact_case_positive_and_foreign_trigger_negative(self):
        self.sql("CREATE TRIGGER customer_side_effect AFTER INSERT ON customer_credentials_v1 BEGIN SELECT 1; END")
        with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_FOREIGN_TRIGGER"): self.enroll()
        self.sql("DROP TRIGGER customer_side_effect")
        self.assertEqual(self.enroll().manifest["source_table"], "customer_credentials_v1")

    def test_existing_database_is_required_and_never_created(self):
        missing = self.database.parent / "absent.sqlite"
        with self.assertRaises(MMCError): SQLiteTargetAdapter(missing)
        self.assertFalse(missing.exists())

    def test_source_shape_and_existing_destination_refuse_atomically(self):
        self.sql("INSERT INTO customer_credentials_v2 VALUES ('already','blue','existing',?)", ("0" * 64,))
        with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_DESTINATION_NOT_EMPTY"): self.enroll()
        self.assertFalse(self.sql("SELECT name FROM sqlite_master WHERE name='mmc_target_enrollment'"))

    def test_host_manifest_selects_genuinely_different_customer_schema(self):
        self.sql("CREATE TABLE event_store_2025(event_key TEXT PRIMARY KEY NOT NULL, tenant_key TEXT NOT NULL, body TEXT NOT NULL)")
        self.sql("CREATE TABLE event_store_2026(body TEXT NOT NULL, payload_digest TEXT NOT NULL, event_key TEXT PRIMARY KEY NOT NULL, tenant_key TEXT NOT NULL)")
        self.sql("INSERT INTO event_store_2025 VALUES ('event.1','blue','external application payload')")
        self.manifest.update(source_table="event_store_2025", destination_table="event_store_2026", id_column="event_key",
                             cohort_column="tenant_key", payload_column="body", checksum_column="payload_digest")
        self.enroll(); self.advance("step.reconcile")
        self.assertEqual(self.sql("SELECT event_key,tenant_key,body FROM event_store_2026"), [("event.1", "blue", "external application payload")])
        self.assertEqual(self.sql("SELECT count(*) FROM customer_credentials_v1"), [(33,)])

    def test_fence_enforced_by_independent_sql_for_all_writer_forms(self):
        self.enroll(); self.advance("step.fence")
        attempts = [
            ("INSERT INTO customer_credentials_v1 VALUES ('late','blue','bad')", ()),
            ("UPDATE customer_credentials_v1 SET credential_payload='changed' WHERE credential_id='blue.000'", ()),
            ("DELETE FROM customer_credentials_v1 WHERE credential_id='blue.000'", ()),
            ("UPDATE customer_credentials_v1 SET tenant='blue' WHERE credential_id='green.000'", ()),
            ("UPDATE customer_credentials_v1 SET tenant='green' WHERE credential_id='blue.000'", ()),
        ]
        for statement, parameters in attempts:
            with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                self.sql(statement, parameters)
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('green.001','green','allowed')")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_fence_is_monotone"):
            self.sql("UPDATE mmc_target_control SET legacy_writes_allowed=1 WHERE cohort='blue'")

    def test_trigger_or_schema_drift_refuses_before_effect(self):
        self.enroll(); request = self.request("step.prepare")
        self.sql("DROP TRIGGER mmc_target_fence_delete")
        with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_SCHEMA_CHANGED"): self.adapter.apply(request)
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(0,)])

    def test_replace_conflicts_cannot_delete_fenced_source_rows(self):
        self.enroll(); self.advance("step.fence")
        before = self.sql("SELECT * FROM customer_credentials_v1 ORDER BY credential_id")
        statements = [
            "INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('blue.000','green','replacement')",
            "REPLACE INTO customer_credentials_v1 VALUES ('blue.000','green','replacement')",
            "UPDATE OR REPLACE customer_credentials_v1 SET credential_id='blue.000' WHERE credential_id='green.000'",
        ]
        with closing(sqlite3.connect(self.database)) as con, con:
            con.execute("PRAGMA recursive_triggers=OFF")
            for statement in statements:
                with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                    con.execute(statement)
            self.assertEqual(con.execute("SELECT * FROM customer_credentials_v1 ORDER BY credential_id").fetchall(), before)
            con.execute("INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('green.000','green','allowed replacement')")
            con.execute("INSERT INTO customer_credentials_v1 VALUES ('green.001','green','new control row')")
        self.assertEqual(self.sql("SELECT credential_payload FROM customer_credentials_v1 WHERE credential_id='green.000'"), [("allowed replacement",)])

    def test_replace_conflicts_honor_unique_payload_index_collation(self):
        self.sql("DROP TABLE customer_credentials_v1")
        self.sql("CREATE TABLE customer_credentials_v1(credential_id TEXT PRIMARY KEY NOT NULL, tenant TEXT NOT NULL, credential_payload TEXT COLLATE NOCASE UNIQUE NOT NULL)")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('selected','blue','Protected')")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('control','green','Other')")
        self.enroll(); self.advance("step.fence")
        with closing(sqlite3.connect(self.database)) as con, con:
            con.execute("PRAGMA recursive_triggers=OFF")
            for statement in (
                "INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('fresh','green','protected')",
                "UPDATE OR REPLACE customer_credentials_v1 SET credential_payload='protected' WHERE credential_id='control'",
            ):
                with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                    con.execute(statement)
            con.execute("INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('control','green','Distinct')")
        self.assertEqual(self.sql("SELECT credential_payload FROM customer_credentials_v1 WHERE credential_id='selected'"), [("Protected",)])

    def test_replace_null_defaults_cannot_evade_unique_conflict_fence(self):
        self.sql("DROP TABLE customer_credentials_v1")
        self.sql("CREATE TABLE customer_credentials_v1(credential_id TEXT PRIMARY KEY NOT NULL DEFAULT 'selected', tenant TEXT NOT NULL DEFAULT 'blue', credential_payload TEXT UNIQUE NOT NULL DEFAULT 'Protected')")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('selected','blue','Protected')")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('control','green','Other')")
        self.enroll(); self.advance("step.fence")
        with closing(sqlite3.connect(self.database)) as con, con:
            con.execute("PRAGMA recursive_triggers=OFF")
            before = con.execute("SELECT * FROM customer_credentials_v1 ORDER BY credential_id").fetchall()
            for statement in (
                "INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('fresh','green',NULL)",
                "INSERT OR REPLACE INTO customer_credentials_v1 VALUES (NULL,'green','Fresh')",
                "INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('fresh',NULL,'Fresh')",
                "UPDATE OR REPLACE customer_credentials_v1 SET credential_payload=NULL WHERE credential_id='control'",
                "UPDATE OR REPLACE customer_credentials_v1 SET credential_id=NULL WHERE credential_id='control'",
            ):
                with self.subTest(statement=statement):
                    con.execute("SAVEPOINT default_case")
                    try:
                        with self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                            con.execute(statement)
                    finally:
                        con.execute("ROLLBACK TO default_case"); con.execute("RELEASE default_case")
            self.assertEqual(con.execute("SELECT * FROM customer_credentials_v1 ORDER BY credential_id").fetchall(), before)

    def test_omitted_defaults_remain_supported_but_explicit_null_writes_refuse(self):
        self.sql("DROP TABLE customer_credentials_v1")
        self.sql("CREATE TABLE customer_credentials_v1(credential_id TEXT PRIMARY KEY NOT NULL DEFAULT 'generated.id', tenant TEXT NOT NULL DEFAULT 'green', credential_payload TEXT UNIQUE NOT NULL DEFAULT (lower('GENERATED.PAYLOAD')))")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('selected','blue','Protected')")
        self.enroll(); self.advance("step.fence")
        self.sql("INSERT INTO customer_credentials_v1 DEFAULT VALUES")
        self.assertEqual(self.sql("SELECT tenant,credential_payload FROM customer_credentials_v1 WHERE credential_id='generated.id'"), [("green", "generated.payload")])
        for statement in (
            "INSERT OR REPLACE INTO customer_credentials_v1 VALUES (NULL,'green','fresh')",
            "INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('fresh','green',NULL)",
            "INSERT OR REPLACE INTO customer_credentials_v1 VALUES ('fresh',NULL,'fresh')",
        ):
            with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                self.sql(statement)

    def test_replace_conflicts_cannot_delete_fenced_rows_by_hidden_rowid(self):
        self.enroll(); self.advance("step.fence")
        with closing(sqlite3.connect(self.database)) as con, con:
            con.execute("PRAGMA recursive_triggers=OFF")
            rowid = con.execute("SELECT rowid FROM customer_credentials_v1 WHERE credential_id='blue.000'").fetchone()[0]
            for statement, args in (
                ("INSERT OR REPLACE INTO customer_credentials_v1(rowid,credential_id,tenant,credential_payload) VALUES (?,'fresh','green','replacement')", (rowid,)),
                ("UPDATE OR REPLACE customer_credentials_v1 SET _rowid_=? WHERE credential_id='green.000'", (rowid,)),
            ):
                with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                    con.execute(statement, args)
        self.assertEqual(self.sql("SELECT count(*) FROM customer_credentials_v1"), [(33,)])

    def test_source_without_rowid_still_allows_control_replacement(self):
        self.sql("DROP TABLE customer_credentials_v1")
        self.sql("CREATE TABLE customer_credentials_v1(credential_id TEXT PRIMARY KEY NOT NULL, tenant TEXT NOT NULL, credential_payload TEXT NOT NULL) WITHOUT ROWID")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('selected','blue','protected')")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('control','green','allowed')")
        self.enroll(); self.advance("step.fence")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
            self.sql("REPLACE INTO customer_credentials_v1 VALUES ('selected','green','replacement')")
        self.sql("REPLACE INTO customer_credentials_v1 VALUES ('control','green','replacement')")
        self.assertEqual(self.sql("SELECT credential_payload FROM customer_credentials_v1 WHERE credential_id='selected'"), [("protected",)])

    def test_unreproducible_source_unique_indexes_refuse_atomically(self):
        for statement in (
            "CREATE UNIQUE INDEX restricted_unique ON customer_credentials_v1(credential_payload) WHERE tenant='blue'",
            "CREATE UNIQUE INDEX restricted_unique ON customer_credentials_v1(lower(credential_payload))",
        ):
            with self.subTest(statement=statement):
                self.sql(statement)
                with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_SOURCE_UNIQUE_INDEX"):
                    self.enroll()
                self.assertFalse(self.sql("SELECT name FROM sqlite_master WHERE name LIKE 'mmc_target_%'"))
                self.sql("DROP INDEX restricted_unique")

    def test_copy_ignore_constraint_refuses_without_partial_rows_or_ledger(self):
        self.sql("DROP TABLE customer_credentials_v2")
        self.sql("CREATE TABLE customer_credentials_v2(credential_id TEXT PRIMARY KEY ON CONFLICT IGNORE NOT NULL, tenant TEXT NOT NULL, credential_payload TEXT NOT NULL, source_digest TEXT NOT NULL)")
        self.sql("INSERT INTO customer_credentials_v2 VALUES ('blue.001','green','existing control',?)", ("0" * 64,))
        self.enroll(); self.advance("step.fence")
        before = self.sql("SELECT * FROM customer_credentials_v2")
        with self.assertRaises(sqlite3.IntegrityError):
            self.adapter.apply(self.request("step.reconcile"))
        self.assertEqual(self.sql("SELECT * FROM customer_credentials_v2"), before)
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(4,)])

    def test_copy_conflict_policy_cannot_replace_or_ignore_existing_control_rows(self):
        self.sql("DROP TABLE customer_credentials_v2")
        self.sql("CREATE TABLE customer_credentials_v2(credential_id TEXT PRIMARY KEY ON CONFLICT REPLACE NOT NULL, tenant TEXT NOT NULL, credential_payload TEXT NOT NULL, source_digest TEXT NOT NULL)")
        self.sql("INSERT INTO customer_credentials_v2 VALUES ('blue.001','green','existing control',?)", ("0" * 64,))
        self.enroll(); self.advance("step.fence")
        before = self.sql("SELECT * FROM customer_credentials_v2")
        with self.assertRaises(sqlite3.IntegrityError):
            self.adapter.apply(self.request("step.reconcile"))
        self.assertEqual(self.sql("SELECT * FROM customer_credentials_v2"), before)
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(4,)])
        self.assertEqual(self.adapter.snapshot(["asset.legacy"])["asset.legacy"]["state"], "legacy")

    def test_foreign_named_metadata_trigger_cannot_escape_effect_scope(self):
        self.enroll(); request = self.request("step.prepare")
        self.sql("CREATE TRIGGER foreign_metadata_effect AFTER UPDATE ON mmc_target_states BEGIN DELETE FROM customer_credentials_v1 WHERE tenant='green'; END")
        with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_SCHEMA_CHANGED"):
            self.adapter.apply(request)
        self.assertEqual(self.sql("SELECT count(*) FROM customer_credentials_v1 WHERE tenant='green'"), [(1,)])
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(0,)])

    def test_foreign_named_indexes_on_customer_or_metadata_are_schema_drift(self):
        self.enroll(); request = self.request("step.prepare")
        for table, column in (("customer_credentials_v1", "tenant"), ("mmc_target_states", "id")):
            self.sql(f"CREATE INDEX outside_index ON {table}({column})")
            with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_SCHEMA_CHANGED"):
                self.adapter.apply(request)
            self.sql("DROP INDEX outside_index")
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(0,)])

    def test_copy_constraint_failure_rolls_back_all_rows_and_ledger(self):
        self.sql("DROP TABLE customer_credentials_v2")
        self.sql("CREATE TABLE customer_credentials_v2(credential_id TEXT PRIMARY KEY NOT NULL CHECK(credential_id!='blue.001'), tenant TEXT NOT NULL, credential_payload TEXT NOT NULL, source_digest TEXT NOT NULL)")
        self.enroll(); self.advance("step.fence")
        with self.assertRaises(sqlite3.IntegrityError): self.adapter.apply(self.request("step.reconcile"))
        self.assertEqual(self.sql("SELECT count(*) FROM customer_credentials_v2"), [(0,)])
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(4,)])
        self.assertEqual(self.adapter.snapshot(["asset.legacy"])["asset.legacy"]["state"], "legacy")

    def test_cutover_rechecks_real_payload_even_with_recomputed_checksum(self):
        import hashlib
        self.enroll(); self.advance("step.reconcile")
        self.sql("UPDATE customer_credentials_v2 SET credential_payload='tampered',source_digest=? WHERE credential_id='blue.000'", (hashlib.sha256(b"tampered").hexdigest(),))
        with self.assertRaisesRegex(MMCError, "MMC_SQLITE_TARGET_INVENTORY_MISMATCH"):
            self.adapter.apply(self.request("step.cutover"))
        self.assertEqual(self.sql("SELECT route FROM mmc_target_control WHERE cohort='blue'"), [("DUAL",)])

    def test_committed_lost_ack_reopens_and_reconciles_without_duplicate(self):
        self.enroll(); request = self.request("step.prepare")
        with self.assertRaises(LostAcknowledgment): self.adapter.apply(request, fault="lost_ack")
        reopened = SQLiteTargetAdapter(self.database)
        self.assertEqual(reopened.lookup(request["operation_id"], digest("request", request))["status"], "APPLIED")
        reopened.apply(request)
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(1,)])

    def test_concurrent_same_request_is_one_atomic_effect(self):
        self.enroll(); request = self.request("step.prepare")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: SQLiteTargetAdapter(self.database).apply(request), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.sql("SELECT count(*) FROM mmc_target_effects"), [(1,)])

    def test_new_target_cannot_discard_cohort_security_knowledge(self):
        self.enroll(); first = self.request("step.prepare")
        first["post_state"]["producer.old"].update(floor=7, revoked=["new.revocation", "revoked.key"])
        self.adapter.apply(first)
        next_request = self.request("step.canary")
        with self.assertRaisesRegex(MMCError, "MMC_T3_SECURITY_FLOOR"):
            self.adapter.apply(next_request)
        self.assertEqual(self.sql("SELECT route FROM mmc_target_control WHERE cohort='blue'"), [("PREPARED",)])
        next_request["post_state"]["consumer.main"].update(floor=7, revoked=["new.revocation", "revoked.key"])
        self.assertEqual(self.adapter.apply(next_request)["status"], "APPLIED")

    def test_case_distinct_cohort_isolation_with_nocase_customer_columns(self):
        import hashlib
        self.sql("DROP TABLE customer_credentials_v1"); self.sql("DROP TABLE customer_credentials_v2")
        self.sql("CREATE TABLE customer_credentials_v1(credential_id TEXT PRIMARY KEY NOT NULL, tenant TEXT COLLATE NOCASE NOT NULL, credential_payload TEXT NOT NULL)")
        self.sql("CREATE TABLE customer_credentials_v2(credential_id TEXT PRIMARY KEY NOT NULL, tenant TEXT COLLATE NOCASE NOT NULL, credential_payload TEXT NOT NULL, source_digest TEXT NOT NULL)")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('one','blue','selected')")
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('two','BLUE','control')")
        self.sql("INSERT INTO customer_credentials_v2 VALUES ('two','BLUE','control',?)", (hashlib.sha256(b"control").hexdigest(),))
        self.manifest["cohorts"] = ["BLUE", "blue", "green"]
        self.enroll(); self.advance("step.reconcile")
        self.assertEqual(self.sql("SELECT credential_id,tenant FROM customer_credentials_v2 ORDER BY credential_id"), [("one", "blue"), ("two", "BLUE")])
        self.sql("INSERT INTO customer_credentials_v1 VALUES ('three','BLUE','still writable')")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
            self.sql("INSERT INTO customer_credentials_v1 VALUES ('four','blue','blocked')")

    def test_real_controller_workflow_without_transport_for_baseline(self):
        result = run_target_qualification(authenticated=False)
        self.assertEqual(result["status"], "PASS_DIRECT_SQLITE_TARGET_MIGRATION")
        self.assertEqual(result["migrated_rows"], 32)
        self.assertEqual(result["adapter_effect_count"], 9)
        self.assertEqual(result["dormant_worker"]["status"], "LEGACY_WRITE_FENCED")


if __name__ == "__main__": unittest.main()
