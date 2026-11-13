"""Seal and run an exact offline qualification handoff on a genuine target host.

The copied RUNNER.py bootstrap uses only the standard library before checking
the complete envelope. Start it with -I -S -B and a separately retained root.
No command publishes, changes a live installation, or supplies external approval.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import zipfile

RELEASE_COMMANDS = {"qualifier-venv", "qualifier-dependencies", "qualifier-dependency-observation", "qualification",
    "qualifier-dependencies-after", "venv", "installed-dependencies", "install", "installed-dependency-observation",
    "installed-observation", "installed-protocol", "installed-schemas", "installed-agent", "installed-conformance",
    "installed-schema-validation", "installed-migration", "installed-target-migration", "installed-dependencies-after",
    "registry-check", "stage-i1-verification"}

NATIVE_INPUTS = {
    "cmba_a4": {"filename": "cmba_core-0.1.0a4-py3-none-any.whl",
                "sha256": "2a595c06ac64371647eeb9586defde9d3238dbe16271a788ea231de2e15831ce"},
    "cmba_a7": {"filename": "cmba_core-0.1.0a7-py3-none-any.whl",
                "sha256": "fad457fd7a8fe4598da1280fbca90881cfc5e48a5dd410ab9c784ffcb19c70ca"},
    "dkn_rc5": {"filename": "dkn_core-0.2.0rc5-py3-none-any.whl",
                "sha256": "6cc2d9e21c1c26b9b9104bb84a27b8e873f17c7e52bed15228230775e005ccf8"},
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def rooted(body):
    return {**body, "receipt_root": sha(canonical(body))}


def verify_command_set(names):
    require(len(names) == len(set(names)) and set(names) == RELEASE_COMMANDS, "MMC_PLATFORM_AUDIT_COMMAND_SET")


def platform_applicability(qualification):
    """Derive Windows-only POSIX-fixture N/A without changing raw outcomes."""
    raw = qualification["host_limitations"]
    inapplicable = []
    if qualification.get("environment", {}).get("platform") == "Windows":
        cases = (
            ("t1", "tests.test_boundaries.IOBoundaryTests.test_fifo_refused_before_block", "SKIP",
             "POSIX FIFO facility not available; not a Windows pass"),
            ("t4", "tests_t4.test_collectors.CollectorTests.test_fifo_refused", "ERROR",
             "AttributeError: module 'os' has no attribute 'mkfifo'"),
        )
        for group_name, identifier, status, detail in cases:
            group = qualification["tests"].get(group_name, {})
            observed = group.get("test_details", {}).get(identifier)
            exact_cause = observed == detail if status == "SKIP" else (
                type(observed) is str and observed.rstrip().endswith(detail))
            if identifier in raw and group.get("test_outcomes", {}).get(identifier) == status and exact_cause:
                inapplicable.append(identifier)
    return {"platform_inapplicable_tests": sorted(inapplicable),
            "actionable_host_limitations": [identifier for identifier in raw if identifier not in inapplicable]}


def verify_command_capture(directory, path):
    command = load(path)
    require(command == rooted({key: value for key, value in command.items() if key != "receipt_root"}) and
            command.get("status") == "COMPLETED" and command.get("exit_code") == 0 and
            command.get("capture_complete") is True and not command.get("cleanup_errors"), "MMC_PLATFORM_AUDIT_COMMAND_TERMINAL")
    name = command.get("name")
    require(type(name) is str and re.fullmatch(r"[a-z0-9-]+", name) and path.name == name + ".terminal.json",
            "MMC_PLATFORM_AUDIT_COMMAND_NAME")
    for suffix in ("stdout", "stderr", "stdin"):
        expected = command.get(suffix + "_sha256")
        required = suffix != "stdin" or name == "installed-agent"
        require((expected is not None or not required) and
                (expected is None or type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected)),
                "MMC_PLATFORM_AUDIT_CAPTURE_HASH_REQUIRED")
        if expected is not None:
            raw = (directory / (name + "." + suffix)).read_bytes()
            require(type(command.get(suffix + "_bytes")) is int and command[suffix + "_bytes"] == len(raw) and
                    sha(raw) == expected, "MMC_PLATFORM_AUDIT_COMMAND_CAPTURE")
    return command


def _capture_git(command, output, name, *, timeout=120):
    require(re.fullmatch(r"[a-z0-9-]+", name), "MMC_PLATFORM_GIT_COMMAND_NAME")
    terminal = {"schema": "mmc.platform-git-command.v1", "status": "STARTED", "command": command,
                "exit_code": None, "authority_effect": "NONE"}
    (output / (name + ".started.json")).write_bytes(canonical(rooted(terminal)))
    stdout = b""; stderr = b""
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        stdout, stderr = result.stdout, result.stderr
        terminal.update(status="COMPLETED", exit_code=result.returncode)
        require(result.returncode == 0, "MMC_PLATFORM_GIT_COMMAND_FAILED")
        return result
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.output or b"", error.stderr or b""
        terminal.update(status="TIMEOUT", error_type=type(error).__name__)
        raise
    except BaseException as error:
        terminal.update(status="FAILED", error_type=type(error).__name__)
        raise
    finally:
        stdout = stdout.encode() if isinstance(stdout, str) else stdout
        stderr = stderr.encode() if isinstance(stderr, str) else stderr
        (output / (name + ".stdout")).write_bytes(stdout)
        (output / (name + ".stderr")).write_bytes(stderr)
        terminal.update(stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
        (output / (name + ".terminal.json")).write_bytes(canonical(rooted(terminal)))


def load(path):
    def pairs(rows):
        value = {}
        for key, item in rows:
            require(key not in value, "MMC_PLATFORM_DUPLICATE_JSON")
            value[key] = item
        return value
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def inventory(directory):
    directory = Path(directory).absolute()
    for parent in (directory, *directory.parents):
        require(not parent.is_symlink() and not (hasattr(parent, "is_junction") and parent.is_junction()), "MMC_PLATFORM_LINK")
    rows = []
    for base, directories, files in os.walk(directory, followlinks=False):
        for name in (*directories, *files):
            item = Path(base) / name
            require(not item.is_symlink() and not (hasattr(item, "is_junction") and item.is_junction()), "MMC_PLATFORM_LINK")
        for name in files:
            path = Path(base) / name
            relative = path.relative_to(directory).as_posix()
            require(all(re.fullmatch(r"[A-Za-z0-9_.+-]+", piece) and piece not in {".", ".."}
                        for piece in relative.split("/")), "MMC_PLATFORM_PATH")
            require(stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= 128 * 1024 * 1024, "MMC_PLATFORM_FILE")
            rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
    return sorted(rows, key=lambda row: row["path"])


def _pippi_source_archive(source):
    """Package the exact P/PPI source-manifest closure without Git semantics."""
    source = Path(source).resolve()
    manifest_path = source / "release/SOURCE-MANIFEST.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    body = {key: value for key, value in manifest.items() if key != "root"}
    require(manifest.get("root") == sha(canonical(body)), "MMC_PLATFORM_PIPPI_MANIFEST_ROOT")
    require(manifest.get("member_count") == len(manifest.get("members", [])),
            "MMC_PLATFORM_PIPPI_MANIFEST_COUNT")
    require(manifest.get("logical_bytes") == sum(row.get("bytes", -1) for row in manifest["members"]),
            "MMC_PLATFORM_PIPPI_MANIFEST_BYTES")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        rows = list(manifest["members"]) + [{"path": "release/SOURCE-MANIFEST.json",
            "bytes": len(manifest_raw), "sha256": sha(manifest_raw)}]
        require(len({row.get("path", "").casefold() for row in rows}) == len(rows),
                "MMC_PLATFORM_PIPPI_MEMBER_ALIAS")
        for row in sorted(rows, key=lambda item: item["path"]):
            relative = row["path"]
            require(all(re.fullmatch(r"[A-Za-z0-9_.+-]+", piece) and piece not in {".", ".."}
                        for piece in relative.split("/")), "MMC_PLATFORM_PIPPI_PATH")
            raw = (source / Path(*relative.split("/"))).read_bytes()
            require(len(raw) == row["bytes"] and sha(raw) == row["sha256"],
                    "MMC_PLATFORM_PIPPI_MEMBER")
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return output.getvalue(), manifest["root"]


def verify_handoff(directory, expected_root):
    require(type(expected_root) is str and re.fullmatch(r"[0-9a-f]{64}", expected_root), "MMC_PLATFORM_HANDOFF_PIN_REQUIRED")
    directory = Path(directory).absolute()
    manifest = load(directory / "HANDOFF.json")
    body = {key: value for key, value in manifest.items() if key != "receipt_root"}
    require(manifest.get("receipt_root") == expected_root == sha(canonical(body)) and
            manifest.get("schema") == "mmc.platform-handoff.v1" and manifest.get("authority_effect") == "NONE" and
            manifest.get("qualification") == "NOT_EXECUTED", "MMC_PLATFORM_HANDOFF_ROOT")
    actual = [row for row in inventory(directory) if row["path"] != "HANDOFF.json"]
    require(actual == manifest.get("files"), "MMC_PLATFORM_HANDOFF_CLOSURE")
    require({row["path"] for row in actual} >= {"RUNNER.py", "MMC-SOURCE.zip", manifest["wheel"],
            "ucm.bundle", "PIPPI-SOURCE.zip", "semcrys.bundle", "SUBJECT.zip",
            "dependencies/LOCK.json", "dependencies/requirements.lock"},
            "MMC_PLATFORM_HANDOFF_INPUTS")
    pippi = manifest.get("pippi")
    require(type(pippi) is dict and type(pippi.get("source_manifest_root")) is str and
            re.fullmatch(r"[0-9a-f]{64}", pippi["source_manifest_root"]) and
            sha((directory / "PIPPI-SOURCE.zip").read_bytes()) == pippi.get("archive_sha256"),
            "MMC_PLATFORM_PIPPI_BINDING")
    for identity in NATIVE_INPUTS.values():
        path = directory / "native-inputs" / identity["filename"]
        require(path.is_file() and sha(path.read_bytes()) == identity["sha256"], "MMC_PLATFORM_NATIVE_INPUT")
    require(sha((directory / "RUNNER.py").read_bytes()) == manifest.get("runner_sha256"), "MMC_PLATFORM_RUNNER_PIN")
    return manifest


def prepare(directory, expected_source, ucm_source, pippi_source, semcrys_source, subject, dependency_bundle, dependency_lock_root,
            cmba_a4_wheel, cmba_a7_wheel, dkn_rc5_wheel):
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "src")]
    from tools.common import source_snapshot
    from tools_t7.package import build_source, build_wheel, verify_source_archive
    from tools_t7.dependencies import PROFILES, load as load_lock
    from mosaic_mmc_product.integrations import verify_git_source
    directory = Path(os.path.abspath(directory))
    require(not directory.exists() and not directory.is_relative_to(root), "MMC_PLATFORM_HANDOFF_CUSTODY_EXISTS")
    require(source_snapshot(root)["root"] == expected_source, "MMC_PLATFORM_SOURCE_PIN")
    lock = load_lock(Path(dependency_bundle) / "LOCK.json")
    body = {key: value for key, value in lock.items() if key != "lock_root"}
    require(lock.get("lock_root") == dependency_lock_root == sha(canonical(body)) and
            lock.get("profile") in PROFILES and lock.get("pins") == PROFILES[lock["profile"]][2] and
            lock.get("roots") == PROFILES[lock["profile"]][3], "MMC_PLATFORM_DEPENDENCY_LOCK")
    expected_paths = {"LOCK.json", "requirements.lock"} | {"wheels/" + row["filename"] for row in lock["wheels"]}
    source_rows = inventory(dependency_bundle)
    require({row["path"] for row in source_rows} - expected_paths <= {"ACQUISITION.json", "acquisition.stdout", "acquisition.stderr",
            "acquisition.started.json", "acquisition.terminal.json", "bootstrap-pip-metadata.json"},
            "MMC_PLATFORM_DEPENDENCY_EXTRA")
    for row in lock["wheels"]:
        require(type(row.get("filename")) is str and re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", row["filename"]),
                "MMC_PLATFORM_DEPENDENCY_PATH")
        path = Path(dependency_bundle) / "wheels" / row["filename"]
        require(path.stat().st_size == row["bytes"] and sha(path.read_bytes()) == row["sha256"], "MMC_PLATFORM_DEPENDENCY_HASH")
    # Native wheel tags, marker closure and complete installation are deliberately
    # checked on the receiving host; cross-host preparation is not execution.
    identities = {name: verify_git_source(name, source) for name, source in (("ucm", ucm_source), ("semcrys", semcrys_source))}
    source = build_source(root); verify_source_archive(source)
    immutable_subject = build_source(Path(subject)); verify_source_archive(immutable_subject)
    pippi_archive, pippi_source_manifest_root = _pippi_source_archive(pippi_source)
    wheel = build_wheel(root)
    directory.mkdir(parents=True)
    (directory / "RUNNER.py").write_bytes(Path(__file__).read_bytes())
    (directory / "MMC-SOURCE.zip").write_bytes(source)
    wheel_name = "mosaic_migration_compiler-0.1.0a9-py3-none-any.whl"
    (directory / wheel_name).write_bytes(wheel)
    (directory / "SUBJECT.zip").write_bytes(immutable_subject)
    (directory / "PIPPI-SOURCE.zip").write_bytes(pippi_archive)
    supplied_native = {"cmba_a4": Path(cmba_a4_wheel), "cmba_a7": Path(cmba_a7_wheel),
                       "dkn_rc5": Path(dkn_rc5_wheel)}
    for name, identity in NATIVE_INPUTS.items():
        raw = supplied_native[name].read_bytes()
        require(sha(raw) == identity["sha256"], "MMC_PLATFORM_NATIVE_INPUT")
        target = directory / "native-inputs" / identity["filename"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for relative in sorted(expected_paths):
        target = directory / "dependencies" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(dependency_bundle) / relative, target)
    for name, identity in identities.items():
        _capture_git(["git", "-C", str(identity["source"]), "bundle", "create", str(directory / (name + ".bundle")), "HEAD"],
                     directory, name + "-bundle")
        verify_git_source(name, identity["source"])
    require(source_snapshot(root)["root"] == expected_source, "MMC_PLATFORM_SOURCE_CHANGED")
    manifest = rooted({"schema": "mmc.platform-handoff.v1", "source_root": expected_source,
        "source_archive_sha256": sha(source), "wheel": wheel_name, "wheel_sha256": sha(wheel),
        "runner_sha256": sha((directory / "RUNNER.py").read_bytes()), "subject_archive_sha256": sha(immutable_subject),
        "pippi": {"archive_sha256": sha(pippi_archive),
                  "source_manifest_root": pippi_source_manifest_root},
        "dependency_profile": lock["profile"], "dependency_lock_root": dependency_lock_root,
        "integrations": {name: {key: value for key, value in identity.items() if key != "source"} for name, identity in identities.items()},
        "files": inventory(directory), "qualification": "NOT_EXECUTED", "authority_effect": "NONE",
        "launch": "python -I -S -B RUNNER.py run --handoff . --expected-handoff ROOT --out FRESH_OUTSIDE_DIRECTORY"})
    (directory / "HANDOFF.json").write_bytes(canonical(manifest))
    verify_handoff(directory, manifest["receipt_root"])
    return manifest


def _extract(raw, destination):
    # This is used only after the outer envelope hash is admitted. The source
    # verifier then checks its own canonical inventory before import/execution.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.infolist()) <= 5000 and sum(item.file_size for item in archive.infolist()) <= 64 * 1024 * 1024,
                "MMC_PLATFORM_ARCHIVE_BUDGET")
        folded = set()
        for item in archive.infolist():
            pieces = item.filename.split("/")
            require(all(re.fullmatch(r"[A-Za-z0-9_.-]+", piece) and piece not in {".", ".."} for piece in pieces) and
                    item.filename.lower() not in folded and stat.S_ISREG(item.external_attr >> 16) and not item.flag_bits & 1,
                    "MMC_PLATFORM_ARCHIVE_PATH")
            folded.add(item.filename.lower())
            path = destination.joinpath(*pieces)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(item))


def run(directory, expected_handoff, output, *, preflight=False):
    directory, output = Path(directory).absolute(), Path(os.path.abspath(output))
    require(not output.exists() and not output.is_relative_to(directory), "MMC_PLATFORM_RUN_CUSTODY_EXISTS")
    output.mkdir(parents=True)
    terminal = {"schema": "mmc.platform-execution.v1", "status": "RUNNING", "handoff_root": expected_handoff,
        "host": {"system": platform.system(), "machine": platform.machine(), "release": platform.release(),
                 "python": platform.python_version(), "implementation": sys.implementation.name,
                 "interpreter": sys.executable}, "authority_effect": "NONE", "public_release": "NOT_CLEARED"}
    (output / "PLATFORM-EXECUTION.json").write_bytes(canonical(rooted(terminal)))
    try:
        manifest = verify_handoff(directory, expected_handoff)
        require(sha(Path(__file__).read_bytes()) == manifest["runner_sha256"], "MMC_PLATFORM_LAUNCHED_RUNNER_MISMATCH")
        terminal.update(source_root=manifest["source_root"], dependency_profile=manifest["dependency_profile"],
                        dependency_lock_root=manifest["dependency_lock_root"])
        require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "MMC_PLATFORM_ISOLATED_NO_SITE_BOOT_REQUIRED")
        source = output / "source"; pippi = output / "pippi"; subject = output / "subject"
        _extract((directory / "MMC-SOURCE.zip").read_bytes(), source)
        _extract((directory / "PIPPI-SOURCE.zip").read_bytes(), pippi)
        _extract((directory / "SUBJECT.zip").read_bytes(), subject)
        sys.path[:0] = [str(source), str(source / "src")]
        from tools_t7.package import build_source, build_wheel, verify_source_archive
        from tools.common import source_snapshot
        from tools_t7.dependencies import verify_wheelhouse
        verify_source_archive((directory / "MMC-SOURCE.zip").read_bytes())
        verify_source_archive((directory / "SUBJECT.zip").read_bytes())
        require(source_snapshot(source)["root"] == manifest["source_root"] and
                build_source(source) == (directory / "MMC-SOURCE.zip").read_bytes() and
                build_wheel(source) == (directory / manifest["wheel"]).read_bytes(), "MMC_PLATFORM_INNER_ARTIFACT_BINDING")
        rebuilt_pippi, pippi_source_manifest_root = _pippi_source_archive(pippi)
        require(rebuilt_pippi == (directory / "PIPPI-SOURCE.zip").read_bytes() and
                pippi_source_manifest_root == manifest["pippi"]["source_manifest_root"],
                "MMC_PLATFORM_PIPPI_INNER_BINDING")
        verify_wheelhouse(source, dependency_bundle=directory / "dependencies", dependency_lock_root=manifest["dependency_lock_root"])
        for name, identity in manifest["integrations"].items():
            destination = output / name
            for operation, command in (("clone", ["git", "-c", "core.autocrlf=false", "clone", "--no-hardlinks", str(directory / (name + ".bundle")), str(destination)]),
                                       ("checkout", ["git", "-c", "core.autocrlf=false", "-C", str(destination), "checkout", "--detach", identity["git_commit"]])):
                _capture_git(command, output, name + "-" + operation)
        # Execute the admitted repository runner directly, preserving its complete
        # source/installed custody and its independent failure terminal.
        command = [sys.executable, "-I", "-S", "-B", str(source / "tools_t7/release_verify.py"), "--out", str(output / "release"),
            "--expected-source", manifest["source_root"], "--ucm-source", str(output / "ucm"),
            "--pippi-source", str(pippi), "--semcrys-source", str(output / "semcrys"),
            "--subject", str(subject), "--dependency-bundle", str(directory / "dependencies"), "--dependency-lock-root", manifest["dependency_lock_root"],
            "--cmba-a4-wheel", str(directory / "native-inputs" / NATIVE_INPUTS["cmba_a4"]["filename"]),
            "--cmba-a7-wheel", str(directory / "native-inputs" / NATIVE_INPUTS["cmba_a7"]["filename"]),
            "--dkn-rc5-wheel", str(directory / "native-inputs" / NATIVE_INPUTS["dkn_rc5"]["filename"])]
        if preflight:
            command.append("--preflight")
        (output / "command.json").write_bytes(canonical(command))
        with (output / "release.stdout").open("wb") as stdout, (output / "release.stderr").open("wb") as stderr:
            executed = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=output, start_new_session=os.name != "nt",
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                executed.wait(timeout=5400)
            except BaseException:
                if os.name == "nt":
                    subprocess.run([str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"),
                                    "/PID", str(executed.pid), "/T", "/F"], capture_output=True, timeout=15,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    try:
                        os.killpg(executed.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if executed.poll() is None:
                    executed.kill()
                executed.wait(timeout=15)
                terminal["exit_code"] = executed.returncode
                raise
        terminal["exit_code"] = executed.returncode
        require(executed.returncode == 0, "MMC_PLATFORM_RELEASE_COMMAND_FAILED")
        release = load(output / "release/RELEASE-VERIFICATION.json")
        require(release == rooted({key: value for key, value in release.items() if key != "receipt_root"}) and
                release.get("source_root") == manifest["source_root"] and release.get("platform") == platform.system(), "MMC_PLATFORM_RELEASE_BINDING")
        expected_status = "PASS_PREFLIGHT_ONLY" if preflight else "PASS_SCOPED_ALPHA_CANDIDATE"
        require(release.get("status") == expected_status and release["wheel"]["sha256"] == manifest["wheel_sha256"] and
                release["source_archive"]["sha256"] == manifest["source_archive_sha256"] and
                release["offline_dependencies"]["lock_root"] == manifest["dependency_lock_root"], "MMC_PLATFORM_RELEASE_STATUS")
        limitations = [] if preflight else load(output / "release/qualification/T7-QUALIFICATION.json")["host_limitations"]
        terminal.update(status="PASS_PREFLIGHT_ONLY" if preflight else "PASS_EXECUTED_SCOPED_PLATFORM",
            release_root=release["receipt_root"], host_limitations=limitations,
            qualification="PREFLIGHT_NOT_FULL" if preflight else "FULL_SOURCE_AND_INSTALLED_ARTIFACT_EXECUTED",
            evidence_scope="SAME_AUTHOR_ENGINEERING_NOT_INDEPENDENT_ACCEPTANCE")
        verify_handoff(directory, expected_handoff)
    except BaseException as error:
        terminal.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        terminal = rooted(terminal)
        (output / "PLATFORM-EXECUTION.json").write_bytes(canonical(terminal))
    return terminal


def audit_executions(outputs, expected_source):
    """Verify actual full-run artifacts before reporting observed platform legs."""
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / "src")]
    from tools.common import source_snapshot
    from tools_t7.release_verify import verify_qualification, verify_source_archive, verify_wheel, verify_target_receipt
    auditor_source_root = source_snapshot(root)["root"]
    rows = []
    for location in outputs:
        location = Path(location).absolute()
        execution = load(location / "PLATFORM-EXECUTION.json")
        require(execution == rooted({key: value for key, value in execution.items() if key != "receipt_root"}) and
                execution.get("schema") == "mmc.platform-execution.v1" and
                execution.get("status") == "PASS_EXECUTED_SCOPED_PLATFORM" and
                execution.get("source_root") == expected_source and
                execution.get("qualification") == "FULL_SOURCE_AND_INSTALLED_ARTIFACT_EXECUTED" and
                execution.get("exit_code") == 0, "MMC_PLATFORM_AUDIT_FULL_EXECUTION_REQUIRED")
        release_directory = location / "release"
        release = load(release_directory / "RELEASE-VERIFICATION.json")
        require(release == rooted({key: value for key, value in release.items() if key != "receipt_root"}) and
                release.get("receipt_root") == execution["release_root"] and
                release.get("source_root") == expected_source and release.get("status") == "PASS_SCOPED_ALPHA_CANDIDATE" and
                release.get("platform") == execution["host"]["system"], "MMC_PLATFORM_AUDIT_RELEASE")
        qualification = verify_qualification(
            release_directory / "qualification/T7-QUALIFICATION.json",
            expected_source,
            subject_root=location / "source",
        )
        require(qualification["receipt_root"] == release["qualification_root"] and
                qualification["environment"]["platform"] == execution["host"]["system"] and
                qualification["host_limitations"] == execution["host_limitations"], "MMC_PLATFORM_AUDIT_QUALIFICATION")
        require(verify_source_archive((release_directory / "MMC-SOURCE.zip").read_bytes()) == release["source_archive"],
                "MMC_PLATFORM_AUDIT_SOURCE_ARCHIVE")
        wheel = verify_wheel((release_directory / "mosaic_migration_compiler-0.1.0a9-py3-none-any.whl").read_bytes())
        require({key: value for key, value in wheel.items() if key != "files"} == release["wheel"], "MMC_PLATFORM_AUDIT_WHEEL")
        commands = sorted(release_directory.glob("*.terminal.json"))
        verify_command_set([path.name.removesuffix(".terminal.json") for path in commands])
        for path in commands:
            verify_command_capture(release_directory, path)
        target = load(release_directory / "installed-target-migration.stdout")
        verify_target_receipt(target)
        require(target["receipt_root"] == release["installed"]["target_migration_receipt_root"] and
                release["offline_dependencies"]["lock_root"] == execution["dependency_lock_root"] and
                release["offline_dependencies"]["profile"] == execution["dependency_profile"], "MMC_PLATFORM_AUDIT_INSTALLED_BINDING")
        rows.append({"host": execution["host"], "execution_root": execution["receipt_root"],
            "release_root": release["receipt_root"], "qualification_root": qualification["receipt_root"],
            "dependency_profile": execution["dependency_profile"], "dependency_lock_root": execution["dependency_lock_root"],
            "host_limitations": execution["host_limitations"], "evidence_directory": str(location),
            **platform_applicability(qualification),
            "status": "ACTUALLY_EXECUTED_SCOPED_EVIDENCE"})
    observed = {row["host"]["system"] for row in rows}
    require(observed <= {"Windows", "Linux", "Darwin"}, "MMC_PLATFORM_AUDIT_HOST")
    return rooted({"schema": "mmc.platform-evidence-audit.v1", "source_root": expected_source,
        "auditor_source_root": auditor_source_root,
        "status": "PARTIAL_PLATFORM_COVERAGE" if observed != {"Windows", "Linux", "Darwin"} or any(row["actionable_host_limitations"] for row in rows)
                  else "PASS_SCOPED_THREE_PLATFORM_EXECUTION",
        "platform_applicability_policy": "EXACT_WINDOWS_POSIX_FIFO_ABSENCE_ONLY_NOT_APPLICABLE_NEVER_A_PASS",
        "executions": rows, "missing_platforms": sorted({"Windows", "Linux", "Darwin"} - observed),
        "authority_effect": "NONE", "public_release": "NOT_CLEARED",
        "evidence_scope": "IDENTITY_BOUND_SAME_AUTHOR_ARTIFACTS_NOT_INDEPENDENT_ACCEPTANCE"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    prepare_parser = commands.add_parser("prepare")
    for name in ("out", "expected-source", "ucm-source", "pippi-source", "semcrys-source", "subject", "dependency-bundle", "dependency-lock-root",
                 "cmba-a4-wheel", "cmba-a7-wheel", "dkn-rc5-wheel"):
        prepare_parser.add_argument("--" + name, required=True)
    verify_parser = commands.add_parser("verify")
    run_parser = commands.add_parser("run")
    for command in (verify_parser, run_parser):
        command.add_argument("--handoff", required=True)
        command.add_argument("--expected-handoff", required=True)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--preflight", action="store_true")
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--expected-source", required=True)
    audit_parser.add_argument("--execution", action="append", default=[])
    audit_parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.operation == "prepare":
        result = prepare(args.out, args.expected_source, args.ucm_source, args.pippi_source, args.semcrys_source, args.subject,
                         args.dependency_bundle, args.dependency_lock_root,
                         args.cmba_a4_wheel, args.cmba_a7_wheel, args.dkn_rc5_wheel)
    elif args.operation == "audit":
        target = Path(args.out).absolute()
        require(not target.exists(), "MMC_PLATFORM_AUDIT_CUSTODY_EXISTS")
        result = audit_executions(args.execution, args.expected_source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical(result))
    elif args.operation == "verify":
        result = verify_handoff(args.handoff, args.expected_handoff)
    else:
        result = run(args.handoff, args.expected_handoff, args.out, preflight=args.preflight)
    # Never print the full manifest or installed file inventories.
    print(canonical({key: result[key] for key in ("schema", "receipt_root", "source_root", "status") if key in result}).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
