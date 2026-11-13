"""Plan or execute canonical MMC test lanes without changing legacy test identities."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical
from mosaic_mmc.errors import MMCError, require
from tools.common import source_snapshot
from tools_t7.qualify import _host_limitation, _outcomes, _superseded
from tools_t7.test_system import flattened, plan, resolve_source_pin, validate_discovery_profile


def bind_runtime(output: Path) -> Path:
    runtime = output / "runtime"
    runtime.mkdir()
    for name in ("TEMP", "TMP", "TMPDIR", "MMC_DISPOSABLE_TEMP_ROOT",
                 "MMC_INTEGRATION_TEMP_ROOT"):
        os.environ[name] = str(runtime)
    # A source-lane runner must establish the same exact import envelope for
    # child processes that it uses in-process.  Mutating sys.path above is not
    # inherited by subprocesses, and an ambient PYTHONPATH is not an admitted
    # substitute for the pinned source tree.
    os.environ["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    return runtime


def execute(lane_id: str, expected_source: str, output: Path, source_pin_origin: str) -> dict:
    require(not output.exists(), "MMC_TEST_SYSTEM_OUTPUT_EXISTS")
    require(not output.resolve().is_relative_to(ROOT.resolve()), "MMC_TEST_SYSTEM_OUTPUT_INSIDE_SOURCE")
    test_plan = plan(lane_id, expected_source)
    if test_plan["execution_profile"] == "release-qualification-offline.v1":
        validate_discovery_profile()
    require(source_snapshot(ROOT)["root"] == expected_source, "MMC_TEST_SYSTEM_SOURCE_PIN")
    output.mkdir(parents=True)
    bind_runtime(output)
    selected = [test_id for ids in test_plan["selections"].values() for test_id in ids]
    suite = unittest.TestSuite()
    loaded = []
    for test_id in selected:
        cases = list(flattened(unittest.defaultTestLoader.loadTestsFromName(test_id)))
        require(len(cases) == 1 and cases[0].id() == test_id and "_FailedTest" not in cases[0].id(),
                "MMC_TEST_SYSTEM_LOAD", test_id)
        suite.addTest(cases[0])
        loaded.append(test_id)
    require(loaded == selected, "MMC_TEST_SYSTEM_EXECUTION_DENOMINATOR")
    stream = io.StringIO()
    started = time.perf_counter_ns()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter_ns() - started
    status, detail = _outcomes(selected, result)
    limitations = sorted(test_id for test_id in selected if status[test_id] != "PASS" and
                         _host_limitation(test_id, detail.get(test_id, ""), status[test_id]))
    superseded = sorted(test_id for test_id in selected if
                        _superseded(test_id, detail.get(test_id, ""), status[test_id]))
    admitted_nonpasses = sorted(test_id for test_id, admission in
                                test_plan["admitted_nonpasses"].items()
                                if test_id in status and status[test_id] == admission["outcome"] and
                                detail.get(test_id, "") == admission["detail"])
    unexpected = sorted(test_id for test_id in selected if status[test_id] != "PASS" and
                        test_id not in limitations and test_id not in superseded and
                        test_id not in admitted_nonpasses)
    log = output / "tests.txt"
    log.write_text(stream.getvalue(), encoding="utf-8")
    record = {
        "schema": "mosaic.mmc.test-lane-result.v0.1",
        "status": ("PASS_WITH_DECLARED_NONPASSES" if admitted_nonpasses else
                   "PASS_WITH_DECLARED_LIMITATIONS") if not unexpected else "FAIL_UNEXPECTED_OUTCOME",
        "plan": test_plan,
        "source_pin_origin": source_pin_origin,
        "test_outcomes": status,
        "test_details": detail,
        "counts": {kind: sum(value == kind for value in status.values()) for kind in
                   ("PASS", "FAIL", "ERROR", "SKIP", "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS")},
        "host_limitations": limitations,
        "successor_superseded_assertions": superseded,
        "admitted_nonpasses": admitted_nonpasses,
        "unexpected": unexpected,
        "elapsed_ns": elapsed,
        "log": {"path": log.name, "bytes": log.stat().st_size},
        "source_after": source_snapshot(ROOT)["root"],
        "authority_effect": "NONE",
    }
    require(record["source_after"] == expected_source, "MMC_TEST_SYSTEM_SOURCE_CHANGED")
    (output / "TEST-LANE-RESULT.json").write_bytes(canonical(record) + b"\n")
    require(not unexpected, "MMC_TEST_SYSTEM_LANE_FAILED", detail=",".join(unexpected))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--expected-source")
    source.add_argument("--self-pin", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    expected_source, pin_origin = resolve_source_pin(args.lane, args.expected_source, args.self_pin)
    if args.plan_only:
        require(args.out is None, "MMC_TEST_SYSTEM_PLAN_OUTPUT")
        print(canonical({**plan(args.lane, expected_source), "source_pin_origin": pin_origin}).decode())
        return 0
    require(args.out is not None, "MMC_TEST_SYSTEM_OUTPUT_REQUIRED")
    print(canonical(execute(args.lane, expected_source, Path(args.out).resolve(), pin_origin)).decode())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MMCError as error:
        print(canonical({"schema": "mosaic.mmc.test-system-refusal.v0.1",
                         "error": error.record(), "authority_effect": "NONE"}).decode())
        raise SystemExit(2)
