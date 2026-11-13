"""Exact integration checks with isolated dependency imports and temporary caches."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import zipfile
from contextlib import contextmanager

from mosaic_mmc import canonical, decode, MMCError
from mosaic_mmc.errors import require
from .product import _pins

AMCAS_CONTRACT_ROOT = "414b4f74e9f9ece12566ff6e28de0ffa48330e61e4b424cf84bf4f12bbf8b4d5"


def _regular(path: str | os.PathLike[str], code: str) -> Path:
    item = Path(path).absolute()
    for part in (item, *item.parents):
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()), code)
    try:
        mode = item.stat().st_mode
    except OSError as error:
        raise MMCError(code, "$", type(error).__name__) from error
    require(stat.S_ISREG(mode), code)
    return item


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_cmba_wheel(path: str | os.PathLike[str]) -> dict:
    pin = _pins()["integrations"]["cmba"]
    wheel = _regular(path, "MMC_T7_CMBA_WHEEL_PATH")
    require(_sha256(wheel) == pin["wheel_sha256"], "MMC_T7_CMBA_WHEEL_HASH")
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            require(len(names) == len(set(names)), "MMC_T7_CMBA_WHEEL_DUPLICATE")
            require(all(name and not name.startswith(("/", "\\")) and ".." not in Path(name).parts for name in names), "MMC_T7_CMBA_WHEEL_MEMBER")
            metadata = archive.read("cmba_core-0.1.0a7.dist-info/METADATA").replace(b"\r\n", b"\n")
            require(b"Name: cmba-core\n" in metadata and b"Version: 0.1.0a7\n" in metadata, "MMC_T7_CMBA_METADATA")
            require("cmba_agent/protocol.py" in names, "MMC_T7_CMBA_AGENT_PROTOCOL")
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise MMCError("MMC_T7_CMBA_WHEEL_FORMAT", "$", type(error).__name__) from error
    return {
        "schema": "mmc.cmba-wheel-verification.v1",
        "status": "PASS_EXACT_WHEEL",
        "version": pin["version"],
        "sha256": pin["wheel_sha256"],
        "operation": "AGENT_PROTOCOL_AND_BINDING_EVIDENCE",
        "authority_effect": "NONE",
    }


def probe_cmba_agent(path: str | os.PathLike[str]) -> dict:
    verification = verify_cmba_wheel(path)
    wheel = Path(path).absolute()
    # Isolated Python excludes the working directory, user site and ambient
    # PYTHONPATH.  Only the verified wheel is added as the dependency root.
    prefix = f"import sys\nsys.path.insert(0, {str(wheel)!r})\n"
    origin_check = f'''\nfor name, module in list(sys.modules.items()):
    if name == "cmba_core" or name.startswith("cmba_core.") or name == "cmba_agent" or name.startswith("cmba_agent."):
        origin = getattr(module, "__file__", "").replace("\\\\", "/")
        if not origin.startswith({str(wheel).replace(chr(92), '/')!r} + "/"):
            raise RuntimeError("MMC_T7_CMBA_IMPORT_ORIGIN")
'''
    manifest_program = prefix + "from cmba_agent.cli import main\n" + origin_check + "raise SystemExit(main(['manifest']))\n"
    manifest = _run_json([sys.executable, "-I", "-B", "-c", manifest_program], cwd=wheel.parent)
    require(manifest.get("distribution_version") == "0.1.0a7", "MMC_T7_CMBA_AGENT_VERSION")
    require(manifest.get("authority_effect") == "NONE", "MMC_T7_CMBA_AGENT_AUTHORITY")
    # Exercise the installed protocol over an MMC-specific binding.  This is not
    # a manifest-presence proxy: CMBA itself constructs, validates, and inspects
    # the binding in the exact wheel subprocess.
    program = r'''import sys
from cmba_core.bindings import bind, dimension, inspect, profile_reference
from cmba_core.codec import canonical, decode
values=decode(sys.stdin.buffer.read())
profile={"profile_id":"mmc.integration","profile_version":"v1","dimensions":["effect-executor","semantic-authority","subject-root"]}
reference=profile_reference(profile)
dims=[dimension(key,"integration-commitment","mmc.integration-value.v1",values[key]) for key in sorted(values)]
binding=bind(reference,dims)
result=inspect(binding,values,expected_root=binding["binding_root"])
sys.stdout.buffer.write(canonical({"schema":"mmc.cmba-executed-binding.v1","binding":binding,"inspection":result,"authority_effect":"NONE"})+b"\n")
'''
    values = {
        "effect-executor": "MMC_NATIVE_CONTROLLER",
        "semantic-authority": "MMC_NATIVE",
        "subject-root": _pins()["mmc_subject"]["source_root"],
    }
    program = prefix + program.replace("values=decode", origin_check + "\nvalues=decode", 1)
    executed = _run_json([sys.executable, "-I", "-B", "-c", program], cwd=wheel.parent,
                         input_raw=canonical(values))
    inspection = executed.get("inspection", {})
    require(inspection.get("status") == "BINDING_STRUCTURE_VALID", "MMC_T7_CMBA_BINDING_STATUS")
    require(inspection.get("external_anchor") == "MATCHED_CALLER_EXPECTATION", "MMC_T7_CMBA_BINDING_ANCHOR")
    dimensions = inspection.get("dimensions", [])
    require(type(dimensions) is list and len(dimensions) == len(values) and
            all(type(row) is dict for row in dimensions) and
            {row.get("dimension_id") for row in dimensions} == set(values),
            "MMC_T7_CMBA_BINDING_DIMENSIONS")
    require(all(row.get("commitment") == "MATCH" for row in dimensions),
            "MMC_T7_CMBA_BINDING_COMMITMENT")
    return {
        **verification,
        "schema": "mmc.cmba-agent-conformance.v1",
        "status": "PASS_EXACT_WHEEL_EXECUTED_BINDING",
        "manifest_root": hashlib.sha256(canonical(manifest)).hexdigest(),
        "binding_root": executed["binding"]["binding_root"],
        "inspection_root": hashlib.sha256(canonical(inspection)).hexdigest(),
        "dimensions": [row["dimension_id"] for row in inspection["dimensions"]],
    }


def _run_json(arguments: list[str], *, cwd: Path, env: dict[str, str] | None = None,
              input_raw: bytes | None = None) -> dict:
    completed = _run_command(arguments, cwd=cwd, env=env,
                               stdin=subprocess.DEVNULL if input_raw is None else None,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               input=input_raw, timeout=90, check=False)
    require(completed.returncode == 0, "MMC_T7_INTEGRATION_COMMAND", detail=completed.stderr.decode("utf-8", "replace")[:512])
    result = decode(completed.stdout, limit=16 * 1024 * 1024)
    require(type(result) is dict, "MMC_T7_INTEGRATION_RESPONSE")
    return result


def _run_command(arguments: list[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(arguments, **kwargs)
    except subprocess.TimeoutExpired as error:
        raise MMCError("MMC_T7_INTEGRATION_TIMEOUT", detail="Dependency command exceeded its time limit") from error
    except OSError as error:
        raise MMCError("MMC_T7_INTEGRATION_UNAVAILABLE", detail=type(error).__name__) from error


def _verify_worktree(root: Path, command: list[str], commit: str) -> None:
    """Compare working bytes to committed blobs, independently of index flags."""
    listing = _run_command(command + ["ls-tree", "-rz", "--full-tree", commit],
                           capture_output=True, timeout=30, check=False)
    require(listing.returncode == 0, "MMC_T7_GIT_OBSERVATION")
    tracked: set[str] = set()
    checked_directories: set[Path] = set()
    try:
        for record in listing.stdout.split(b"\0"):
            if not record:
                continue
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, object_id = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            parts = PurePosixPath(relative).parts
            require(mode in {"100644", "100755"} and kind == "blob" and
                    len(object_id) in {40, 64} and set(object_id) <= set("0123456789abcdef") and
                    relative and not relative.startswith("/") and "\\" not in relative and
                    ":" not in relative and all(part not in {".", ".."} for part in parts),
                    "MMC_T7_SOURCE_TREE_ENTRY")
            tracked.add(relative)
            path = root.joinpath(*parts)
            for directory in path.parents:
                if directory == root:
                    break
                if directory not in checked_directories:
                    require(not directory.is_symlink() and not (hasattr(directory, "is_junction") and directory.is_junction()),
                            "MMC_T7_SOURCE_PATH")
                    checked_directories.add(directory)
            require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                    "MMC_T7_SOURCE_PATH")
            info = path.stat()
            require(stat.S_ISREG(info.st_mode), "MMC_T7_SOURCE_PATH")
            digest = hashlib.sha1(usedforsecurity=False) if len(object_id) == 40 else hashlib.sha256()
            digest.update(f"blob {info.st_size}\0".encode("ascii"))
            observed_bytes = 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    observed_bytes += len(chunk)
            require(observed_bytes == info.st_size and digest.hexdigest() == object_id,
                    "MMC_T7_SOURCE_BYTES", detail=relative)

        # Ignored source/data can still participate in imports even when Git
        # reports a clean checkout.  Cached bytecode is excluded from execution
        # separately through a fresh pycache_prefix for every probe.
        import_suffixes = {".py", ".pyw", ".json", ".pyc", ".pyo", ".pyd", ".so", ".dll"}
        for directory_name in ("src", "tools"):
            directory = root / directory_name
            if not directory.exists():
                continue
            for parent, directories, files in os.walk(directory, followlinks=False):
                for child_name in directories:
                    child = Path(parent) / child_name
                    require(not child.is_symlink() and not (hasattr(child, "is_junction") and child.is_junction()),
                            "MMC_T7_SOURCE_PATH")
                for filename in files:
                    path = Path(parent) / filename
                    suffix = path.suffix.lower()
                    if suffix not in import_suffixes:
                        continue
                    if suffix in {".pyc", ".pyo"} and "__pycache__" in path.parts:
                        continue
                    require(path.relative_to(root).as_posix() in tracked,
                            "MMC_T7_SOURCE_EXTRA_IMPORT", detail=path.relative_to(root).as_posix())
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, MMCError):
            raise
        raise MMCError("MMC_T7_SOURCE_BYTES", detail=type(error).__name__) from error


@contextmanager
def _source_python():
    # -B prevents writes but does not prevent reads of existing bytecode.  A
    # fresh prefix prevents an ignored __pycache__ from changing executed code.
    directory = Path(os.environ.get("MMC_INTEGRATION_TEMP_ROOT", Path.cwd()))
    try:
        with tempfile.TemporaryDirectory(prefix="mmc-integration-cache-", dir=directory) as cache:
            yield [sys.executable, "-I", "-B", "-X", "pycache_prefix=" + cache]
    except OSError as error:
        raise MMCError("MMC_T7_INTEGRATION_TEMP_UNAVAILABLE", detail=type(error).__name__) from error


def verify_git_source(name: str, source: str | os.PathLike[str]) -> dict:
    require(name in {"ucm", "semcrys"}, "MMC_T7_INTEGRATION_NAME")
    pin = _pins()["integrations"][name]
    root = Path(source).absolute()
    require(root.is_dir(), "MMC_T7_SOURCE_PATH")
    for part in (root, *root.parents):
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()),
                "MMC_T7_SOURCE_PATH")
    command = ["git", "-C", str(root)]
    head = _run_command(command + ["rev-parse", "HEAD"], capture_output=True, text=True, timeout=30, check=False)
    tree = _run_command(command + ["rev-parse", "HEAD^{tree}"], capture_output=True, text=True, timeout=30, check=False)
    status = _run_command(command + ["status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True, timeout=30, check=False)
    require(head.returncode == tree.returncode == status.returncode == 0, "MMC_T7_GIT_OBSERVATION")
    require(head.stdout.strip() == pin["git_commit"] and tree.stdout.strip() == pin["git_tree"], "MMC_T7_GIT_IDENTITY")
    require(status.stdout == "", "MMC_T7_GIT_DIRTY")
    _verify_worktree(root, command, pin["git_commit"])
    return {"source": root, "git_commit": pin["git_commit"], "git_tree": pin["git_tree"]}


def probe_ucm(source: str | os.PathLike[str], contract: str | os.PathLike[str]) -> dict:
    identity = verify_git_source("ucm", source)
    contract_path = _regular(contract, "MMC_T7_AMCAS_CONTRACT_PATH")
    contract_value = decode(contract_path.read_bytes())
    require(type(contract_value) is dict and contract_value.get("contract_root") == AMCAS_CONTRACT_ROOT,
            "MMC_T7_AMCAS_CONTRACT_IDENTITY")
    tool = identity["source"] / "tools" / "ucm.py"
    require(tool.is_file(), "MMC_T7_UCM_TOOL")
    with _source_python() as python:
        orient = _run_json(python + [str(tool), "orient"], cwd=identity["source"])
        caps = _run_json(python + [str(tool), "capabilities"], cwd=identity["source"])
        validated = _run_json(python + [str(tool), "validate-amcas", str(contract_path)], cwd=identity["source"])
        compiled = _run_json(python + [str(tool), "compile-amcas", str(contract_path)], cwd=identity["source"])
    verify_git_source("ucm", source)
    require(validated.get("contract_root") == compiled.get("contract_root") == AMCAS_CONTRACT_ROOT,
            "MMC_T7_AMCAS_CONTRACT_IDENTITY")
    return {
        "schema": "mmc.ucm-conformance.v1",
        "status": "PASS_SHADOW_CONTRACT",
        "git_commit": identity["git_commit"],
        "git_tree": identity["git_tree"],
        "orientation_root": hashlib.sha256(canonical(orient)).hexdigest(),
        "capabilities_root": hashlib.sha256(canonical(caps)).hexdigest(),
        "contract_root": validated["contract_root"],
        "ir_root": compiled["ir_root"],
        "native_semantic_authority": "MMC_NATIVE",
        "effect_executor": "MMC_NATIVE_CONTROLLER",
        "identity_binding": "UNBOUND",
        "authority_effect": "NONE",
    }


def probe_semcrys(source: str | os.PathLike[str]) -> dict:
    identity = verify_git_source("semcrys", source)
    program = (f"import sys; sys.path.insert(0, {str(identity['source'] / 'src')!r}); "
               "from semcrys_core.cli import main; raise SystemExit(main())")
    with _source_python() as python:
        capabilities = _run_json(python + ["-c", program, "capabilities"], cwd=identity["source"])
        native = _run_json(python + ["-c", program, "native-status"], cwd=identity["source"])
    verify_git_source("semcrys", source)
    return {
        "schema": "mmc.semcrys-conformance.v1",
        "status": "PASS_OPTIONAL_CAPABILITY_PROBE",
        "git_commit": identity["git_commit"],
        "git_tree": identity["git_tree"],
        "capabilities_root": hashlib.sha256(canonical(capabilities)).hexdigest(),
        "native_status_root": hashlib.sha256(canonical(native)).hexdigest(),
        "role": "OPTIONAL_ARCHIVE_AND_CUSTODY_TRANSPORT",
        "migration_eligibility_source": False,
        "self_verification": "HELD_ULTRA_ASSET_MISSING",
        "authority_effect": "NONE",
    }
