"""Failure and concurrency witnesses for the finite real SQLite adapter."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from mosaic_mmc import MMCError, canonical
from mosaic_mmc_t3 import digest
from mosaic_mmc_t3.storage import LostAcknowledgment
from mosaic_mmc_product.adapter import DisposableSQLiteAdapter, WORKLOAD_STEPS


class AdapterSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "workload.sqlite"
        self.adapter = DisposableSQLiteAdapter.create(
            self.path, "disposable.audit", dict.fromkeys(
                ["producer.old", "consumer.main", "asset.legacy"], "legacy"),
        )
        self.number = 0
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.executemany("INSERT INTO legacy_records VALUES (?,?,?)", [
                ("blue.1", "blue", "value"), ("green.1", "green", "control"),
            ])

    def request(self, transition, *, direction="FORWARD"):
        self.number += 1
        mapping = WORKLOAD_STEPS[transition]
        targets = sorted(mapping)
        pre = self.adapter.snapshot(targets)
        after_index = 1 if direction == "FORWARD" else 0
        return {
            "schema": "mmc.effect-request.t3", "operation_id": f"audit.op.{self.number}",
            "scope": {"migration": "migration.audit", "transition": transition,
                      "cohort": "cohort.blue", "targets": targets,
                      "plan_root": "0" * 64, "policy_root": "1" * 64},
            "context_root": "2" * 64, "direction": direction,
            "compensates": "prior.operation" if direction == "COMPENSATE" else None,
            "adapter": self.adapter.descriptor(), "pre_state": pre,
            "post_state": {key: {"state": mapping[key][after_index],
                                 "floor": value["floor"], "revoked": value["revoked"]}
                           for key, value in pre.items()},
            "prepared_at": 100, "expires_at": 130, "max_attempts": 2,
        }

    def advance(self, through):
        for step in WORKLOAD_STEPS:
            self.adapter.apply(self.request(step))
            if step == through:
                return
        raise AssertionError(through)

    def test_fence_blocks_insert_update_delete_and_cohort_moves(self):
        self.advance("step.fence")
        statements = [
            ("INSERT INTO legacy_records VALUES (?,?,?)", ("blue.2", "blue", "late")),
            ("UPDATE legacy_records SET payload=? WHERE id=?", ("changed", "blue.1")),
            ("DELETE FROM legacy_records WHERE id=?", ("blue.1",)),
            ("UPDATE legacy_records SET cohort=? WHERE id=?", ("green", "blue.1")),
            ("UPDATE legacy_records SET cohort=? WHERE id=?", ("blue", "green.1")),
        ]
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for sql, args in statements:
                with self.subTest(sql=sql, args=args), self.assertRaisesRegex(
                        sqlite3.IntegrityError, "legacy_write_fenced"):
                    connection.execute(sql, args)
            connection.execute("UPDATE legacy_records SET payload='still-live' WHERE cohort='green'")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_fence_is_monotone"):
                connection.execute("UPDATE cohort_control SET legacy_writes_allowed=1 WHERE cohort='blue'")
        self.assertEqual(next(row for row in self.adapter.workload_snapshot()["legacy"]
                              if row["cohort"] == "blue")["payload"], "value")

    def test_cutover_refuses_content_corruption_even_with_recomputed_checksum(self):
        self.advance("step.reconcile")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE new_records SET payload='corrupt',source_sha256=?",
                               (__import__("hashlib").sha256(b"corrupt").hexdigest(),))
        before = self.adapter.workload_snapshot()
        request = self.request("step.cutover")
        with self.assertRaisesRegex(MMCError, "SOURCE_DESTINATION_MISMATCH"):
            self.adapter.apply(request)
        self.assertEqual(self.adapter.workload_snapshot(), before)
        self.assertEqual(self.adapter.snapshot(["consumer.main"]), request["pre_state"])

    def test_replace_conflicts_cannot_delete_fenced_source_rows(self):
        self.advance("step.fence")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA recursive_triggers=OFF")
            before = connection.execute("SELECT * FROM legacy_records ORDER BY id").fetchall()
            for statement in (
                "INSERT OR REPLACE INTO legacy_records VALUES ('blue.1','green','replacement')",
                "REPLACE INTO legacy_records VALUES ('blue.1','green','replacement')",
                "UPDATE OR REPLACE legacy_records SET id='blue.1' WHERE id='green.1'",
            ):
                with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                    connection.execute(statement)
            self.assertEqual(connection.execute("SELECT * FROM legacy_records ORDER BY id").fetchall(), before)
            connection.execute("INSERT OR REPLACE INTO legacy_records VALUES ('green.1','green','allowed')")

    def test_replace_conflicts_cannot_delete_fenced_rows_by_hidden_rowid(self):
        self.advance("step.fence")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA recursive_triggers=OFF")
            rowid = connection.execute("SELECT rowid FROM legacy_records WHERE id='blue.1'").fetchone()[0]
            for statement, args in (
                ("INSERT OR REPLACE INTO legacy_records(rowid,id,cohort,payload) VALUES (?,'fresh','green','replacement')", (rowid,)),
                ("UPDATE OR REPLACE legacy_records SET oid=? WHERE id='green.1'", (rowid,)),
            ):
                with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                    connection.execute(statement, args)
            self.assertEqual(connection.execute("SELECT count(*) FROM legacy_records").fetchone(), (2,))

    def test_legacy_disposable_fixture_has_the_same_source_fence(self):
        from mosaic_mmc_product.disposable import _initialize
        path = Path(self.temporary.name) / "legacy-fixture.sqlite"
        _initialize(path)
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("INSERT INTO legacy_records VALUES ('selected','blue','protected')")
            connection.execute("INSERT INTO legacy_records VALUES ('control','green','allowed')")
            connection.execute("UPDATE cohort_control SET legacy_writes_allowed=0 WHERE cohort='blue'")
            connection.execute("PRAGMA recursive_triggers=OFF")
            for statement in (
                "REPLACE INTO legacy_records VALUES ('selected','green','replacement')",
                "UPDATE OR REPLACE legacy_records SET id='selected' WHERE id='control'",
                "DELETE FROM legacy_records WHERE id='selected'",
            ):
                with self.subTest(statement=statement), self.assertRaisesRegex(sqlite3.IntegrityError, "legacy_write_fenced"):
                    connection.execute(statement)
            connection.execute("REPLACE INTO legacy_records VALUES ('control','green','replacement')")

    def test_retirement_rechecks_live_copy_in_same_transaction(self):
        self.advance("step.cutover")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM new_records")
        before = self.adapter.workload_snapshot()
        with self.assertRaisesRegex(MMCError, "SOURCE_DESTINATION_MISMATCH"):
            self.adapter.apply(self.request("step.retire"))
        self.assertEqual(self.adapter.workload_snapshot(), before)

    def test_failure_after_workload_mutation_rolls_back_effect_and_ledger(self):
        request = self.request("step.prepare")
        before = self.adapter.workload_snapshot()
        original = self.adapter._apply_workload
        def fail_after_work(connection, value):
            original(connection, value)
            raise RuntimeError("injected after workload write")
        with patch.object(self.adapter, "_apply_workload", side_effect=fail_after_work):
            with self.assertRaisesRegex(RuntimeError, "after workload"):
                self.adapter.apply(request)
        self.assertEqual(self.adapter.workload_snapshot(), before)
        self.assertEqual(self.adapter.snapshot(["producer.old"]), request["pre_state"])
        self.assertEqual(self.adapter.lookup(request["operation_id"], digest("request", request))["status"],
                         "ABSENT_FROM_LOCAL_LEDGER")

    def test_same_request_concurrently_returns_one_effect(self):
        request = self.request("step.prepare")
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.adapter.apply(request), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.adapter.workload_snapshot()["effect_count"], 1)
        self.assertEqual(self.adapter.snapshot(["producer.old"])["producer.old"]["version"], 1)

    def test_competing_requests_cannot_both_apply_stale_prestate(self):
        first = self.request("step.prepare")
        second = deepcopy(first); second["operation_id"] = "competing.op"
        def attempt(request):
            try:
                return self.adapter.apply(request)["status"]
            except MMCError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, [first, second]))
        self.assertCountEqual(results, ["APPLIED", "MMC_T3_PRECONDITION_CHANGED"])
        self.assertEqual(self.adapter.workload_snapshot()["effect_count"], 1)

    def test_lost_ack_reopens_and_reconciles_without_reapplying(self):
        request = self.request("step.prepare")
        with self.assertRaises(LostAcknowledgment):
            self.adapter.apply(request, fault="lost_ack")
        reopened = DisposableSQLiteAdapter(self.path)
        result = reopened.lookup(request["operation_id"], digest("request", request))
        self.assertEqual(result, reopened.apply(request))
        self.assertEqual(reopened.workload_snapshot()["effect_count"], 1)
        conflict = deepcopy(request); conflict["expires_at"] += 1
        with self.assertRaisesRegex(MMCError, "IDEMPOTENCY_CONFLICT"):
            reopened.apply(conflict)

    def test_cohort_security_floor_does_not_regress_on_disjoint_target(self):
        first = self.request("step.prepare")
        first["post_state"]["producer.old"].update(floor=10, revoked=["new.revocation", "revoked.key"])
        self.adapter.apply(first)
        self.adapter.apply(self.request("step.canary"))
        blue = next(row for row in self.adapter.workload_snapshot()["control"] if row["cohort"] == "blue")
        self.assertEqual(blue["security_floor"], 10)
        self.assertEqual(blue["revoked"], ["new.revocation", "revoked.key"])

    def test_unsupported_compensation_cannot_reopen_fence(self):
        self.advance("step.fence")
        before = self.adapter.workload_snapshot()
        with self.assertRaisesRegex(MMCError, "COMPENSATION_UNSUPPORTED"):
            self.adapter.apply(self.request("step.fence", direction="COMPENSATE"))
        self.assertEqual(self.adapter.workload_snapshot(), before)

    def test_request_cannot_use_model_state_label_to_misrepresent_workload(self):
        request = self.request("step.prepare")
        request["post_state"]["producer.old"]["state"] = "retired"
        with self.assertRaisesRegex(MMCError, "REQUEST_STATES"):
            self.adapter.apply(request)
        self.assertEqual(self.adapter.workload_snapshot()["effect_count"], 0)

    def test_replaced_database_identity_is_rechecked(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE adapter_meta SET raw=?", (canonical({
                "schema": "mmc.disposable-target.v1", "id": "different.adapter",
            }),))
        with self.assertRaisesRegex(MMCError, "ADAPTER_IDENTITY"):
            self.adapter.snapshot(["producer.old"])

    def test_missing_database_is_refused_without_recreating_file(self):
        self.path.unlink()
        with self.assertRaisesRegex(MMCError, "DATABASE_MISSING"):
            self.adapter.snapshot(["producer.old"])
        self.assertFalse(self.path.exists())

    def test_malformed_adapter_success_does_not_poison_controller_journal(self):
        from tests_t3.helpers import Env, TIME
        from mosaic_mmc_t3 import Controller
        environment = Env(Path(self.temporary.name))
        request = environment.prepare(); environment.approve(request)
        real_apply = environment.store.apply
        def corrupt_return(value, *, fault=None):
            result = deepcopy(real_apply(value, fault=fault))
            result["post_state"]["producer.old"]["state"] = "false.success"
            return result
        with patch.object(environment.store, "apply", side_effect=corrupt_return):
            result = environment.controller.commit("op.1", environment.store, TIME)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["refusal_code"], "MMC_T3_POSTCONDITION")
        reopened = Controller(environment.root / "controller.sqlite",
                              expected_policy_root=digest("policy", environment.policy))
        self.assertEqual(reopened.replay()["projection"]["operations"]["op.1"]["status"], "UNKNOWN")
        self.assertEqual(reopened.reconcile("op.1", environment.store)["status"], "APPLIED")
        self.assertEqual(environment.store.snapshot(["producer.old"])["producer.old"]["version"], 1)

    def test_invalid_ledger_result_leaves_controller_reconcilable(self):
        from tests_t3.helpers import Env, TIME
        environment = Env(Path(self.temporary.name))
        request = environment.prepare(); environment.approve(request)
        environment.controller.commit("op.1", environment.store, TIME, fault="lost_ack")
        before = environment.controller.replay()["projection"]["head"]
        result = environment.store.lookup("op.1", digest("request", request))
        result["changed"] = []
        with patch.object(environment.store, "lookup", return_value=result):
            with self.assertRaisesRegex(MMCError, "POSTCONDITION"):
                environment.controller.reconcile("op.1", environment.store)
        self.assertEqual(environment.controller.replay()["projection"]["head"], before)
        self.assertEqual(environment.controller.reconcile("op.1", environment.store)["status"], "APPLIED")


if __name__ == "__main__":
    unittest.main()
