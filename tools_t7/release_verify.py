"""Offline release preparation, exact wheel installation, and terminal evidence.

This repository command never publishes. Use a fresh output directory for each attempt.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.pycache_prefix = str(ROOT.parent / ("release-import-cache-" + uuid.uuid4().hex))
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from tools.common import source_snapshot
from tools.package import safe_names, verify_source_archive
from tools_t7.package import build_source, build_wheel

WHEEL_NAME = "mosaic_migration_compiler-0.1.0a9-py3-none-any.whl"


def _stop_owned_process(process):
    """Stop only the process tree created by this invocation.

    Windows venv launchers can own a separate Python child; killing only the
    launcher would leave qualification running and its capture pipes open.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        killer = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
        stopped = subprocess.run([str(killer), "/PID", str(process.pid), "/T", "/F"],
                                 capture_output=True, timeout=10,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if stopped.returncode != 0 and process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rooted(body: dict) -> dict:
    return {**body, "receipt_root": sha(canonical(body))}


def verify_wheel(raw: bytes, root: Path = ROOT) -> dict:
    """Compare every wheel byte to deterministic current source and metadata."""
    require(raw == build_wheel(root), "MMC_RELEASE_WHEEL_SOURCE_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        safe_names(archive.namelist())
        files = [{"path": name, "bytes": len(archive.read(name)),
                  "sha256": sha(archive.read(name))} for name in sorted(archive.namelist())]
    return {"status": "PASS_EXACT_SOURCE_WHEEL", "sha256": sha(raw), "files": files}


def verify_target_receipt(target: dict) -> dict:
    """Recheck recorded workflow and raw custody, not external identity/authority.

    Ephemeral HMAC keys are destroyed. Archive verification checks exact bytes
    and recorded execution testimony; it cannot independently reauthenticate MACs.
    """
    require(type(target) is dict and rooted({key: value for key, value in target.items() if key != "receipt_root"}) == target,
            "MMC_RELEASE_TARGET_ROOT")
    require(target.get("status") == "PASS_AUTHENTICATED_SQLITE_TARGET_MIGRATION" and
            target.get("adapter_effect_count") == 9 and type(target.get("adapter_effect_count")) is int and
            target.get("retirement_status") == "MODEL_RETIREMENT_CONDITIONS_MET" and
            target.get("independent_sql_inventory") == "MATCH" and
            target.get("completed_transitions") == ["step.prepare", "step.canary", "step.coexist", "step.fence", "step.reconcile", "step.cutover", "step.retire"],
            "MMC_RELEASE_TARGET_SEMANTICS")
    require(type(target.get("migrated_rows")) is int and target["migrated_rows"] == 32 and
            target.get("dormant_worker", {}).get("status") == "LEGACY_WRITE_FENCED" and
            target.get("control_cohort_write", {}).get("status") == "LEGACY_WRITE_ACCEPTED" and
            target.get("recovery") == {"route": "RECOVERY_DUAL", "floor": 5, "revoked": ["revoked.key"], "legacy_write": "LEGACY_WRITE_FENCED"} and
            target.get("production_adapter") is False and target.get("authority_effect") == "NONE" and
            target.get("coverage_scope") == "ENROLLED_TABLES_AND_DECLARED_COHORTS_ONLY" and
            target.get("authority_scope") == "SIGNED_PUBLIC_FIXTURE_NOT_EXTERNAL_AUTHORIZATION",
            "MMC_RELEASE_TARGET_SCOPE")
    lost = target.get("lost_ack", {})
    require(lost.get("initial") == "UNKNOWN" and lost.get("reconciled") == "APPLIED" and
            lost.get("fresh_transport") is True and lost.get("worker_exit_code") == 73 and
            lost.get("response_received") is False and lost.get("effect_count_after_reconcile") == 5,
            "MMC_RELEASE_TARGET_RECONCILIATION")
    transport = target.get("transport", {})
    require(transport.get("protocol") == "mmc.adapter-transport.v1" and
            transport.get("automatic_apply_retry") is False and type(transport.get("segments")) is list,
            "MMC_RELEASE_TARGET_TRANSPORT")
    all_calls = []; recorded_effects = []; lookups = []
    from mosaic_mmc_t3 import digest
    from mosaic_mmc_product.transport_wire import session_id
    for segment in transport["segments"]:
        require(rooted({key: value for key, value in segment.items() if key != "receipt_root"}) == segment and
                segment.get("transcript_custody") == "RETAINED_RAW_BYTES" and
                len(segment.get("raw_transcripts", [])) == len(segment.get("calls", [])),
                "MMC_RELEASE_TARGET_TRANSPORT_CUSTODY")
        for call, transcript in zip(segment["calls"], segment["raw_transcripts"]):
            require(call.get("worker_authentication_verified") is True and call.get("request_authenticator_sent") is True and
                    call.get("io_threads_reaped") is True and call.get("automatic_retry") is False and
                    call.get("stdout_capture_truncated") is False and call.get("stderr_capture_truncated") is False and
                    transcript.get("bootstrap") == "OMITTED_EPHEMERAL_SECRET", "MMC_RELEASE_TARGET_AUTHENTICATION")
            values = {name: b"".join(base64.b64decode(chunk, validate=True) for chunk in transcript[name + "_base64_chunks"])
                      for name in ("request", "stdout", "stderr")}
            require(sha(values["stdout"]) == call["stdout_sha256"] and sha(values["stderr"]) == call["stderr_sha256"] and
                    len(values["request"]) == call["request_bytes_written"] and transcript["exit_code"] == call["exit_code"],
                    "MMC_RELEASE_TARGET_TRANSCRIPT_HASH")
            request = decode(values["request"][:-1], canonical_only=True, limit=2 * 1024 * 1024)
            require(values["request"].endswith(b"\n") and sha(canonical(request["body"])) == call["request_root"] and
                    request["body"]["session"] == call["session"] and
                    request["body"]["protocol"] == "mmc.adapter-transport.v1" and
                    type(request["body"]["sequence"]) is int and request["body"]["sequence"] == 1 and
                    request["body"]["operation"] == call["operation"], "MMC_RELEASE_TARGET_REQUEST_BINDING")
            frames = [decode(raw, canonical_only=True, limit=2 * 1024 * 1024) for raw in values["stdout"].splitlines()]
            require(values["stdout"].endswith(b"\n") and len(frames) == (2 if call["response_authentication_verified"] else 1),
                    "MMC_RELEASE_TARGET_RESPONSE_COUNT")
            challenge = frames[0]["body"]
            require(challenge["protocol"] == "mmc.adapter-transport.v1" and challenge["backend"] == segment["backend"] and
                    challenge["worker_pid"] == call["worker_pid"] == call["launcher_pid"] and
                    challenge["implementation_pin"] == segment["implementation_pin"] == call["implementation_pin"] and
                    challenge["session"] == call["session"] == session_id(challenge["host_nonce"], challenge["worker_nonce"], segment["implementation_pin"]) and
                    sha(canonical(challenge)) == request["body"]["challenge_root"], "MMC_RELEASE_TARGET_CHALLENGE_BINDING")
            result = None
            if call["response_authentication_verified"]:
                reply = frames[1]["body"]
                require(reply["protocol"] == "mmc.adapter-transport.v1" and reply["session"] == call["session"] and
                        type(reply["sequence"]) is int and reply["sequence"] == 1 and reply["ok"] is True and
                        reply["request_root"] == call["request_root"] and call["exit_code"] == 0 and
                        sha(canonical(reply["result"])) == call["result_sha256"], "MMC_RELEASE_TARGET_RESPONSE_BINDING")
                result = reply["result"]
            else:
                require(call["operation"] == "apply" and call["exit_code"] == 73, "MMC_RELEASE_TARGET_UNKNOWN_OUTCOME")
            if call["operation"] == "apply":
                effect = request["body"]["arguments"]["request"]
                require(effect["adapter"] == target["adapter_descriptor"] and
                        effect["scope"]["migration"] == target["manifest"]["migration_id"] and
                        effect["scope"]["cohort"] == target["manifest"]["cohort_id"], "MMC_RELEASE_TARGET_EFFECT_SCOPE")
                recorded_effects.append({"transition": effect["scope"]["transition"], "direction": effect["direction"],
                    "operation_id": effect["operation_id"], "request_root": digest("request", effect),
                    "status": "UNKNOWN" if result is None else result["status"]})
            elif call["operation"] == "lookup":
                lookups.append((request["body"]["arguments"], result))
            all_calls.append(call)
    require(len(all_calls) == transport.get("authenticated_calls") and
            sum(call["operation"] == "apply" for call in all_calls) == transport.get("apply_calls") == 9 and
            sum(not call.get("response_authentication_verified", False) for call in all_calls) == 1,
            "MMC_RELEASE_TARGET_CALL_ACCOUNTING")
    require(recorded_effects == target["effects"] and len({row["operation_id"] for row in recorded_effects}) == 9,
            "MMC_RELEASE_TARGET_EFFECT_ACCOUNTING")
    unknown = [row for row in recorded_effects if row["status"] == "UNKNOWN"]
    require(len(unknown) == 1 and any(arguments == {"operation_id": unknown[0]["operation_id"], "request_root": unknown[0]["request_root"]}
            and result["status"] == "APPLIED" and result["request_root"] == unknown[0]["request_root"]
            for arguments, result in lookups), "MMC_RELEASE_TARGET_LEDGER_RECONCILIATION")
    return target


def verify_qualification(path: Path, expected_source: str, *,
                         subject_root: Path | None = None) -> dict:
    # Direct release verification runs from the admitted source tree, while a
    # later platform audit runs from the maintainer checkout and must rebuild
    # the qualification index from the source tree retained with that exact
    # execution.  In particular, packaged FILE-MANIFEST.json bytes are not
    # required to equal a maintainer checkout's pre-package copy.
    subject_root = ROOT if subject_root is None else Path(subject_root).resolve()
    receipt = decode(path.read_bytes(), limit=16 * 1024 * 1024)
    body = {key: value for key, value in receipt.items() if key != "receipt_root"}
    require(sha(canonical(body)) == receipt.get("receipt_root"), "MMC_RELEASE_QUALIFICATION_ROOT")
    require(receipt.get("source_root") == expected_source and receipt.get("status") ==
            "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS",
            "MMC_RELEASE_QUALIFICATION_SUBJECT")
    environment = receipt.get("environment")
    require(type(environment) is dict and environment.get("platform") in ("Windows", "Linux", "Darwin"),
            "MMC_RELEASE_QUALIFICATION_PLATFORM")
    # A retained execution must be checked against the test denominator that
    # was admitted by that execution's retained source, not against a newer
    # maintainer checkout.  Otherwise adding a validator regression after an
    # effectful run makes honest raw-evidence revalidation impossible.
    registry = decode((subject_root / "provenance/turn7/TEST-REGISTRY.json").read_bytes(),
                      limit=8 * 1024 * 1024)
    require(set(receipt["tests"]) == set(registry["groups"]), "MMC_RELEASE_TEST_GROUPS")
    for name, group in receipt["tests"].items():
        outcome = decode((path.parent / (name + "-tests.json")).read_bytes(), limit=8 * 1024 * 1024)
        require({key: value for key, value in outcome.items() if key != "test_ids"} == group and
                sorted(outcome["test_ids"]) == registry["groups"][name] and
                set(outcome["test_outcomes"]) == set(outcome["test_ids"]),
                "MMC_RELEASE_TEST_IDENTITIES", name)
        require(not group["unexpected"], "MMC_RELEASE_UNEXPECTED_TESTS", name)
        from tools_t7.qualify import _host_limitation, _superseded
        statuses = ("PASS", "FAIL", "ERROR", "SKIP", "EXPECTED_FAILURE", "UNEXPECTED_SUCCESS")
        require(set(group["test_outcomes"].values()) <= set(statuses), "MMC_RELEASE_TEST_STATUS")
        require(group["counts"] == {status: sum(value == status for value in group["test_outcomes"].values())
                                    for status in statuses}, "MMC_RELEASE_TEST_COUNTS")
        nonpasses = {identifier for identifier, status in group["test_outcomes"].items() if status != "PASS"}
        require(set(group["test_details"]) == nonpasses, "MMC_RELEASE_TEST_DETAILS")
        limitations = sorted(identifier for identifier in nonpasses
                             if _host_limitation(identifier, group["test_details"][identifier], group["test_outcomes"][identifier],
                                                 host_system=environment["platform"]))
        superseded = sorted(identifier for identifier in nonpasses
                            if _superseded(identifier, group["test_details"][identifier], group["test_outcomes"][identifier]))
        require(group["host_limitations"] == limitations and group["successor_superseded_assertions"] == superseded and
                not set(limitations) & set(superseded) and nonpasses == set(limitations) | set(superseded),
                "MMC_RELEASE_TEST_ACCOUNTING", name)
        log = group["log"]
        require(log["path"] == name + "-tests.txt", "MMC_RELEASE_LOG_PATH")
        raw = (path.parent / log["path"]).read_bytes()
        require(sha(raw) == log["sha256"] and len(raw) == log["bytes"], "MMC_RELEASE_LOG_HASH")
    evidence_scope = receipt.get("evidence_scope")
    require(type(evidence_scope) is dict and
            evidence_scope.get("standard") == "EVIDENCE_SCOPE_AND_REQUALIFICATION_DISCIPLINE" and
            evidence_scope.get("authority_effect") == "NONE" and
            evidence_scope.get("impact_authority") == "UCM_EVALUATE_REQUALIFICATION_IMPACT",
            "MMC_RELEASE_EVIDENCE_SCOPE")
    inventory = decode((path.parent / "MMC-EVIDENCE-SCOPE-INVENTORY.json").read_bytes(), limit=16 * 1024 * 1024)
    profile = decode((path.parent / "MMC-EVIDENCE-SCOPE-PROFILE.json").read_bytes(), limit=16 * 1024 * 1024)
    claim_map = decode((path.parent / "MMC-CLAIM-DEPENDENCY-MAP.json").read_bytes(), limit=16 * 1024 * 1024)
    inventory_root = sha(canonical(inventory))
    profile_root = sha(canonical({key: value for key, value in profile.items() if key != "profile_root"}))
    claim_map_root = sha(canonical({key: value for key, value in claim_map.items() if key != "claim_map_root"}))
    require(inventory.get("subject_root") == expected_source and
            inventory.get("external_closure") == "COMPLETE" and
            all(row.get("closure_coverage") == "COMPLETE" for row in inventory.get("components", [])) and
            evidence_scope.get("inventory_root") == inventory_root,
            "MMC_RELEASE_EVIDENCE_SCOPE_INVENTORY")
    require(profile.get("profile_root") == evidence_scope.get("profile_root") == profile_root and
            profile.get("subject_root") == expected_source and profile.get("closure_complete") is True,
            "MMC_RELEASE_EVIDENCE_SCOPE_PROFILE")
    require(claim_map.get("claim_map_root") == evidence_scope.get("claim_map_root") == claim_map_root and
            claim_map.get("baseline_profile_root") == profile_root and
            claim_map.get("baseline_subject_root") == expected_source and
            claim_map.get("closure_complete") is True,
            "MMC_RELEASE_EVIDENCE_SCOPE_CLAIM_MAP")
    from tools_t7.qualification_index import (
        build_index as build_qualification_index,
        summary as qualification_summary,
        verify_index,
    )
    component = receipt.get("qualification_index")
    require(isinstance(component, dict) and component.get("path") == "QUALIFICATION-INDEX.json",
            "MMC_RELEASE_QUALIFICATION_INDEX")
    component_path = path.parent / component["path"]
    component_raw = component_path.read_bytes()
    require(len(component_raw) == component.get("bytes")
            and sha(component_raw) == component.get("sha256"),
            "MMC_RELEASE_QUALIFICATION_INDEX_HASH")
    component_index = verify_index(decode(component_raw, limit=8 * 1024 * 1024))
    require(component_index["source_root"] == expected_source
            and component == {**qualification_summary(component_index),
                              "path": component_path.name,
                              "bytes": len(component_raw),
                              "sha256": sha(component_raw)}
            and component_index == build_qualification_index(
                subject_root, external_bindings=component_index["external_bindings"]),
            "MMC_RELEASE_QUALIFICATION_INDEX_SUBJECT")
    stage = path.parent / "MMC-APPLICATION-STAGE-I1.zip"
    require(sha(stage.read_bytes()) == receipt["stage_i1"]["sha256"] and
            stage.stat().st_size == receipt["stage_i1"]["bytes"], "MMC_RELEASE_STAGE_HASH")
    migration = decode((path.parent / "DISPOSABLE-MIGRATION.json").read_bytes(), limit=8 * 1024 * 1024)
    require(rooted({key: value for key, value in migration.items() if key != "receipt_root"}) == migration and
            migration["receipt_root"] == receipt["disposable_migration"]["receipt_root"] and
            migration["status"] == receipt["disposable_migration"]["status"] ==
            "PASS_NATIVE_CONTROLLER_DISPOSABLE_MIGRATION_RETIREMENT_RECOVERY" and
            migration["retirement_status"] == receipt["disposable_migration"]["retirement_status"] ==
            "MODEL_RETIREMENT_CONDITIONS_MET" and
            migration["dormant_worker_resume"]["status"] == receipt["disposable_migration"]["dormant_worker_resume"],
            "MMC_RELEASE_MIGRATION_ROOT")
    target = decode((path.parent / "TARGET-MIGRATION.json").read_bytes(), limit=8 * 1024 * 1024)
    verify_target_receipt(target)
    require(rooted({key: value for key, value in target.items() if key != "receipt_root"}) == target and
            target["receipt_root"] == receipt["target_migration"]["receipt_root"] and
            target["status"] == receipt["target_migration"]["status"] == "PASS_AUTHENTICATED_SQLITE_TARGET_MIGRATION",
            "MMC_RELEASE_TARGET_ROOT")
    return receipt


def inventory(raw: bytes, wheel: bytes, source_root: str, dependencies: dict | None = None) -> dict:
    """SPDX file inventory plus explicit dependency/relationship scope."""
    namespace = "https://mosaic.invalid/spdx/" + sha(canonical({"source": sha(raw), "wheel": sha(wheel)}))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = [{"SPDXID": f"SPDXRef-File-{index}", "fileName": "./" + name,
                  "checksums": [{"algorithm": "SHA256", "checksumValue": sha(archive.read(name))}],
                  "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"}
                 for index, name in enumerate(sorted(archive.namelist()))]
    packages = [{"SPDXID": "SPDXRef-MMC", "name": "mosaic-migration-compiler", "versionInfo": "0.1.0a9",
                 "downloadLocation": "NOASSERTION", "filesAnalyzed": False, "licenseDeclared": "NOASSERTION",
                 "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"}]
    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-MMC"}]
    if dependencies is not None:
        packages.append({"SPDXID": "SPDXRef-QualificationProfile", "name": dependencies["profile"],
                         "downloadLocation": "NOASSERTION", "filesAnalyzed": False, "licenseDeclared": "NOASSERTION",
                         "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"})
        relationships.append({"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-QualificationProfile"})
        for index, row in enumerate(dependencies["wheels"]):
            identifier = "SPDXRef-Dependency-" + str(index)
            packages.append({"SPDXID": identifier, "name": row["name"], "versionInfo": row["version"],
                             "downloadLocation": row["acquisition"]["url"], "filesAnalyzed": False,
                             "checksums": [{"algorithm": "SHA256", "checksumValue": row["sha256"]}],
                             "licenseDeclared": row["license_expression"], "licenseConcluded": "NOASSERTION",
                             "copyrightText": "NOASSERTION"})
            relationships.append({"spdxElementId": "SPDXRef-QualificationProfile", "relationshipType": "DEPENDS_ON", "relatedSpdxElement": identifier})
    return {"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
            "name": "MMC-0.1.0a9-source-inventory", "documentNamespace": namespace,
            "creationInfo": {"creators": ["Tool: mmc-release-verify"], "created": "2026-11-09T00:00:00Z"},
            "documentComment": "Exact source inventory and locked qualification dependencies; license conclusions and vulnerability clearance require separate review. Source root: " + source_root,
            "files": files, "packages": packages, "relationships": relationships}


def _capture(out: Path, name: str, command: list[str], env: dict, *, timeout: int = 300,
             stdin: bytes | None = None) -> bytes:
    # Every command in this runner starts a Python interpreter, including future
    # executable names. Isolated mode ignores environment-only cache settings.
    command = [command[0], "-B", "-X", "pycache_prefix=" + str(out / ("cache-" + name)), *command[1:]]
    require(re.fullmatch(r"[a-z0-9-]+", name) is not None and
            not any((out / (name + suffix)).exists() for suffix in (".started.json", ".terminal.json", ".stdout", ".stderr", ".stdin")),
            "MMC_RELEASE_COMMAND_CUSTODY_EXISTS")
    started = time.perf_counter_ns()
    progress = lambda status: print(canonical({"schema": "mmc.release-progress.v1", "command": name,
        "status": status, "elapsed_ms": (time.perf_counter_ns() - started) // 1000000,
        "evidence": "NONSEMANTIC_PROGRESS_ONLY"}).decode(), file=sys.stderr, flush=True)
    progress("STARTED")
    initial = rooted({"schema": "mmc.release-command-start.v1", "name": name, "command": command,
                      "status": "STARTED", "stdin_sha256": None if stdin is None else sha(stdin)})
    (out / (name + ".started.json")).write_bytes(canonical(initial))
    if stdin is not None:
        (out / (name + ".stdin")).write_bytes(stdin)
    process = None; interrupted = None
    stdout = b""; stderr = b""; code = None; status = "START_FAILED"
    capture_complete = False; cleanup_errors = []
    def stop_and_drain():
        nonlocal stdout, stderr, code, capture_complete
        if process is None:
            return
        try:
            _stop_owned_process(process)
        except BaseException as error:
            cleanup_errors.append(type(error).__name__)
        try:
            stdout, stderr = process.communicate(timeout=10)
            capture_complete = True
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.output or stdout, error.stderr or stderr
            cleanup_errors.append("PIPE_DRAIN_TIMEOUT")
        except BaseException as error:
            cleanup_errors.append(type(error).__name__)
        code = process.returncode
    try:
        process = subprocess.Popen(command, cwd=out, env=env, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=os.name != "nt",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + timeout
        first_input = stdin
        while True:
            try:
                stdout, stderr = process.communicate(input=first_input, timeout=min(30, max(0.001, deadline-time.monotonic())))
                code, status, capture_complete = process.returncode, "COMPLETED", True
                break
            except subprocess.TimeoutExpired as error:
                first_input = None
                stdout, stderr = error.output or stdout, error.stderr or stderr
                if time.monotonic() >= deadline:
                    status = "TIMEOUT"
                    stop_and_drain()
                    break
                progress("RUNNING")
    except OSError as error:
        if process is not None:
            stop_and_drain()
            stderr += str(error).encode()
            code, status = process.returncode, "IO_FAILED"
        else:
            stdout, stderr, code, status = b"", str(error).encode(), None, "START_FAILED"
    except BaseException as error:
        interrupted = error
        if process is not None:
            stop_and_drain()
        else:
            stdout, stderr, code = b"", b"", None
        status = "INTERRUPTED"
    (out / (name + ".stdout")).write_bytes(stdout)
    (out / (name + ".stderr")).write_bytes(stderr)
    if stdin is not None:
        (out / (name + ".stdin")).write_bytes(stdin)
    terminal = rooted({"schema": "mmc.release-command.v1", "name": name, "command": command,
                       "status": status, "exit_code": code, "stdout_sha256": sha(stdout),
                       "stdin_sha256": None if stdin is None else sha(stdin),
                       "stdout_bytes": len(stdout), "stderr_bytes": len(stderr),
                       "stdin_bytes": None if stdin is None else len(stdin),
                       "capture_complete": capture_complete, "cleanup_errors": cleanup_errors,
                       "stderr_sha256": sha(stderr), "elapsed_ns": time.perf_counter_ns() - started})
    (out / (name + ".terminal.json")).write_bytes(canonical(terminal))
    progress(status)
    if interrupted is not None:
        raise interrupted
    require(status == "COMPLETED" and code == 0 and capture_complete and not cleanup_errors, "MMC_RELEASE_COMMAND_FAILED", name)
    return stdout


def release_verify(output: Path, expected_source: str, ucm_source: Path,
                   pippi_source: Path, semcrys_source: Path, subject: Path, *,
                   preflight_only: bool = False,
                   dependency_bundle: Path | None = None, dependency_lock_root: str | None = None,
                   cmba_a4_wheel: Path | None = None, cmba_a7_wheel: Path | None = None,
                   dkn_rc5_wheel: Path | None = None) -> dict:
    output = output.resolve()
    require(not output.is_relative_to(ROOT.resolve()), "MMC_RELEASE_OUTPUT_INSIDE_SOURCE")
    require(not output.exists(), "MMC_RELEASE_CUSTODY_EXISTS")
    require(source_snapshot(ROOT)["root"] == expected_source, "MMC_RELEASE_SOURCE_PIN")
    output.mkdir(parents=True)
    terminal = {"schema": "mmc.release-verification.v1", "source_root": expected_source,
                "status": "RUNNING", "authority_effect": "NONE",
                "public_release": "OWNER_AUTHORIZED_APACHE_2_0_SOURCE_PUBLICATION_NOT_AN_EFFECT_OF_VERIFIER"}
    (output / "RELEASE-VERIFICATION.json").write_bytes(canonical(rooted(terminal)))
    try:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None); env.pop("PYTHONHOME", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = "0"
        env["PYTHONPYCACHEPREFIX"] = str(output / "cache-children")
        temp = output / "temp"; temp.mkdir()
        for variable in ("TEMP", "TMP", "TMPDIR", "MMC_DISPOSABLE_TEMP_ROOT"):
            env[variable] = str(temp)
        # Preserve the exact candidate even when later qualification fails.
        source, wheel = build_source(ROOT), build_wheel(ROOT)
        require(build_source(ROOT) == source and build_wheel(ROOT) == wheel, "MMC_RELEASE_REPRODUCIBILITY")
        source_verification = verify_source_archive(source)
        wheel_verification = verify_wheel(wheel)
        (output / "MMC-SOURCE.zip").write_bytes(source)
        wheel_path = output / WHEEL_NAME; wheel_path.write_bytes(wheel)
        from tools_t7.dependencies import verify_wheelhouse, installation_command, observation_command, CURRENT_FULL_PROFILES
        require(dependency_bundle is not None and dependency_lock_root is not None, "MMC_RELEASE_CURRENT_FULL_PROFILE_REQUIRED")
        require(cmba_a4_wheel is not None and cmba_a7_wheel is not None and dkn_rc5_wheel is not None,
                "MMC_RELEASE_EXTERNAL_NATIVE_INPUTS_REQUIRED")
        dependency_options = {"dependency_bundle": dependency_bundle, "dependency_lock_root": dependency_lock_root}
        dependencies = verify_wheelhouse(ROOT, **dependency_options)
        require(dependencies["profile"] in CURRENT_FULL_PROFILES, "MMC_RELEASE_CURRENT_FULL_PROFILE_REQUIRED")
        (output / "SBOM.spdx.json").write_bytes(canonical(inventory(source, wheel, expected_source, dependencies)))
        (output / "OFFLINE-DEPENDENCIES.json").write_bytes(canonical(dependencies))
        qualifier = output / "qualifier"
        _capture(output, "qualifier-venv", [sys.executable, "-m", "venv", "--without-pip", str(qualifier)], env)
        qualifier_python = qualifier / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _capture(output, "qualifier-dependencies", installation_command(qualifier_python, ROOT, **dependency_options), env)
        qualification_dependencies = decode(_capture(output, "qualifier-dependency-observation",
            observation_command(qualifier_python, ROOT, **dependency_options), env, timeout=300))
        source_env = {**env, "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT))), "PYTHONNOUSERSITE": "1"}
        # Test fixtures receive the same explicitly admitted external bundle.
        # The dependency library never selects trust roots from environment.
        source_env.pop("MMC_QUALIFICATION_DEPENDENCY_BUNDLE", None)
        source_env.pop("MMC_QUALIFICATION_DEPENDENCY_LOCK_ROOT", None)
        if dependency_bundle is not None:
            source_env["MMC_QUALIFICATION_DEPENDENCY_BUNDLE"] = str(dependency_bundle.absolute())
            source_env["MMC_QUALIFICATION_DEPENDENCY_LOCK_ROOT"] = dependency_lock_root
        source_env["MMC_QUALIFICATION_CMBA_A4_WHEEL"] = str(cmba_a4_wheel.absolute())
        source_env["MMC_QUALIFICATION_CMBA_A7_WHEEL"] = str(cmba_a7_wheel.absolute())
        source_env["MMC_QUALIFICATION_DKN_RC5_WHEEL"] = str(dkn_rc5_wheel.absolute())
        source_env["MMC_UCM_R038_SOURCE"] = str(pippi_source.resolve())
        # Discovery imports test modules. Do it only after the qualifier's
        # complete dependency closure has been installed and observed, so a
        # clean -I -S base interpreter needs no ambient test dependencies.
        _capture(output, "registry-check", [str(qualifier_python), "-B",
                 str(ROOT / "tools_t7/registry_refresh.py"), "--expected-source", expected_source], source_env)
        receipt = None
        if preflight_only:
            # The bounded lane catches high-fanout input and contract failures before
            # the expensive complete denominator. It cannot satisfy release qualification.
            _capture(output, "preflight-tests", [str(qualifier_python), "-B",
                     str(ROOT / "tools_t7/test_runner.py"), "--lane", "preflight",
                     "--expected-source", expected_source,
                     "--out", str(output / "preflight-tests")], source_env, timeout=1200)
        else:
            qualification = output / "qualification"
            _capture(output, "qualification", [str(qualifier_python), "-B", str(ROOT / "tools_t7/qualify.py"),
                     "--out", str(qualification), "--expected-source", expected_source,
                     "--ucm-source", str(ucm_source.resolve()),
                     "--pippi-source", str(pippi_source.resolve()),
                     "--semcrys-source", str(semcrys_source.resolve()),
                     "--subject", str(subject.resolve()),
                     "--cmba-a4-wheel", str(cmba_a4_wheel.resolve()),
                     "--cmba-a7-wheel", str(cmba_a7_wheel.resolve()),
                     "--dkn-rc5-wheel", str(dkn_rc5_wheel.resolve()),
                     "--dependency-bundle", str(dependency_bundle.resolve()),
                     "--dependency-lock-root", dependency_lock_root], source_env, timeout=2700)
            receipt = verify_qualification(qualification / "T7-QUALIFICATION.json", expected_source)
            program = ("import sys; from pathlib import Path; "
                       "sys.path.insert(0,sys.argv[1]); from ucm.stage1 import verify_stage1_bundle; "
                       "verify_stage1_bundle(Path(sys.argv[2]).read_bytes()); print('PASS_STAGE_I1')")
            _capture(output, "stage-i1-verification", [str(qualifier_python), "-B", "-c", program,
                     str(ucm_source.resolve() / "src"), str(qualification / "MMC-APPLICATION-STAGE-I1.zip")], source_env)
        require(source_snapshot(ROOT)["root"] == expected_source, "MMC_RELEASE_SOURCE_CHANGED")
        dependencies_after = decode(_capture(output, "qualifier-dependencies-after",
            observation_command(qualifier_python, ROOT, **dependency_options), env, timeout=300))
        require(dependencies_after == qualification_dependencies, "MMC_RELEASE_QUALIFICATION_DEPENDENCY_DRIFT")
        # Independent installation has no system-site or user-site dependencies.
        venv = output / "installed"
        _capture(output, "venv", [sys.executable, "-m", "venv", "--without-pip", str(venv)], env)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _capture(output, "installed-dependencies", installation_command(python, ROOT, **dependency_options), env)
        _capture(output, "install", [str(python), "-I", "-m", "pip", "--isolated", "install",
                 "--no-index", "--no-deps", "--no-compile", "--disable-pip-version-check", str(wheel_path)], env)
        installed_dependencies = decode(_capture(output, "installed-dependency-observation",
            observation_command(python, ROOT, allow_mmc_version="0.1.0a9", mmc_wheel=wheel_path, **dependency_options), env, timeout=300))
        observation = decode(_capture(output, "installed-observation", [str(python), "-I", "-c",
            "import json,sys,sysconfig,importlib.metadata as m; import mosaic_mmc_product,cryptography; "
            "print(json.dumps({'module':mosaic_mmc_product.__file__,'purelib':sysconfig.get_path('purelib'),"
            "'python':sys.version,'crypto_version':m.version('cryptography'),'crypto_path':cryptography.__file__}))"], env))
        purelib = Path(observation["purelib"]).resolve()
        require(purelib.is_relative_to(venv.resolve()) and
                Path(observation["module"]).resolve().is_relative_to(purelib), "MMC_RELEASE_IMPORT_SUBSTITUTION")
        for row in wheel_verification["files"]:
            if row["path"].endswith("/RECORD"):
                continue  # pip rewrites RECORD with generated launcher metadata.
            require(sha((purelib / row["path"]).read_bytes()) == row["sha256"],
                    "MMC_RELEASE_INSTALLED_HASH", row["path"])
        protocol = decode(_capture(output, "installed-protocol", [str(python), "-I", "-m", "mosaic_mmc_product", "protocol"], env))
        schemas = decode(_capture(output, "installed-schemas", [str(python), "-I", "-m", "mosaic_mmc_product", "schema", "all"], env))
        request = {"schema": "mmc.agent-request.v1", "protocol": "mmc.agent.v1", "request_id": "release.verify", "operation": "product.capabilities", "arguments": {}}
        response = decode(_capture(output, "installed-agent", [str(python), "-I", "-m", "mosaic_mmc_product", "request", "-"], env, stdin=canonical(request)))
        require(response.get("ok") is True, "MMC_RELEASE_AGENT_REFUSAL")
        conformance = decode(_capture(output, "installed-conformance", [str(python), "-I", "-c",
            "from mosaic_mmc import canonical; from mosaic_mmc_product.conformance import run_conformance; "
            "print(canonical(run_conformance()).decode())"], env))
        require(conformance["status"] == "PASS_PROTOCOL_CONFORMANCE", "MMC_RELEASE_CONFORMANCE")
        _capture(output, "installed-schema-validation", [str(python), "-I", "-c",
            "import json; from pathlib import Path; from jsonschema import Draft202012Validator as V; "
            "s=json.loads(Path('installed-schemas.stdout').read_bytes()); "
            "[V.check_schema(s[k]) for k in ('request','response')]; "
            "V(s['request']).validate(json.loads(Path('installed-agent.stdin').read_bytes())); "
            "V(s['response']).validate(json.loads(Path('installed-agent.stdout').read_bytes())); print('PASS_INSTALLED_SCHEMAS')"], env)
        migration = decode(_capture(output, "installed-migration", [str(python), "-I", "-m", "mosaic_mmc_product", "verify-disposable-migration"], env))
        require(migration["status"] == "PASS_NATIVE_CONTROLLER_DISPOSABLE_MIGRATION_RETIREMENT_RECOVERY" and
                rooted({key: value for key, value in migration.items() if key != "receipt_root"}) == migration,
                "MMC_RELEASE_INSTALLED_MIGRATION")
        target = decode(_capture(output, "installed-target-migration", [str(python), "-I", "-m",
            "mosaic_mmc_product", "verify-target-migration"], env, timeout=600))
        verify_target_receipt(target)
        require(target.get("status") == "PASS_AUTHENTICATED_SQLITE_TARGET_MIGRATION" and
                rooted({key: value for key, value in target.items() if key != "receipt_root"}) == target,
                "MMC_RELEASE_INSTALLED_TARGET")
        installed_after = decode(_capture(output, "installed-dependencies-after",
            observation_command(python, ROOT, allow_mmc_version="0.1.0a9", mmc_wheel=wheel_path, **dependency_options), env, timeout=300))
        require(installed_after == installed_dependencies, "MMC_RELEASE_INSTALLED_DEPENDENCY_DRIFT")
        require(source_snapshot(ROOT)["root"] == expected_source, "MMC_RELEASE_SOURCE_CHANGED")
        terminal.update(status="PASS_PREFLIGHT_ONLY" if preflight_only else "PASS_SCOPED_ALPHA_CANDIDATE",
                        qualification_root=None if receipt is None else receipt["receipt_root"],
                        source_archive=source_verification,
                        wheel={key: value for key, value in wheel_verification.items() if key != "files"},
                        installed={"environment": observation, "all_wheel_members_verified": True,
                                   "protocol_root": sha(canonical(protocol)), "schemas_root": sha(canonical(schemas)),
                                   "conformance_cases": conformance["case_count"],
                                   "migration_receipt_root": migration["receipt_root"],
                                   "target_migration_receipt_root": target["receipt_root"]},
                        offline_dependencies={"closure_receipt_root": dependencies["receipt_root"],
                                              "lock_root": dependencies["lock_root"], "profile": dependencies["profile"],
                                              "qualification_environment": qualification_dependencies,
                                              "installed_environment": installed_dependencies},
                        platform=platform.system(), release_channel="ALPHA_REVIEW_CANDIDATE",
                        stage_i1_verified=not preflight_only,
                        remaining_gates=["DKN_ASSET_CERTIFICATION", "INDEPENDENT_PUBLICATION_SECURITY_REVIEW",
                                         "MACOS_NATIVE_EXECUTION", "NATIVE_INTEGRATION_ACCEPTANCE",
                                         "PRODUCTION_ADAPTER_AND_IDENTITY_QUALIFICATION", "INDEPENDENT_OPERATOR_STUDY"],
                        procedure_scope="HASH_LOCKED_OFFLINE_INSTALL_IN_TWO_CLEAN_VENVS_NO_SYSTEM_SITE")
    except BaseException as error:
        terminal.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        terminal = rooted(terminal)
        (output / "RELEASE-VERIFICATION.json").write_bytes(canonical(terminal))
    return terminal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--ucm-source", required=True)
    parser.add_argument("--pippi-source", required=True)
    parser.add_argument("--semcrys-source", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--preflight", action="store_true", help="run current Release Convergence tests and installed checks; not full qualification")
    parser.add_argument("--dependency-bundle", type=Path, help="external exact native-platform offline closure")
    parser.add_argument("--dependency-lock-root", help="separately admitted SHA-256 of external lock body")
    parser.add_argument("--cmba-a4-wheel", type=Path, required=True)
    parser.add_argument("--cmba-a7-wheel", type=Path, required=True)
    parser.add_argument("--dkn-rc5-wheel", type=Path, required=True)
    args = parser.parse_args()
    result = release_verify(Path(args.out), args.expected_source, Path(args.ucm_source),
                            Path(args.pippi_source), Path(args.semcrys_source),
                            Path(args.subject), preflight_only=args.preflight,
                            dependency_bundle=args.dependency_bundle, dependency_lock_root=args.dependency_lock_root,
                            cmba_a4_wheel=args.cmba_a4_wheel, cmba_a7_wheel=args.cmba_a7_wheel,
                            dkn_rc5_wheel=args.dkn_rc5_wheel)
    print(canonical(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
