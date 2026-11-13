"""Verify and install exact, explicitly admitted offline CPython 3.12 closures.

This bootstrap and installed observer import only the standard library. PEP 440,
508 and wheel-tag interpretation runs in isolated Python using packaging vendored
inside the hash-verified bundled pip wheel. No host pip/packaging code is imported.
"""
from __future__ import annotations

import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import sysconfig
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "windows-cpython312-amd64-qualification.v1"
LOCK_ROOT = "3f86a8ea5d8720353873bcae8077d01fd8e2f43d6a8cb08e9b365cb1b4240d99"
PINS = {"pip": "26.0.1", "cryptography": "46.0.3", "cffi": "2.0.0", "pycparser": "3.0",
        "jsonschema": "4.26.0", "attrs": "25.4.0", "jsonschema-specifications": "2025.9.1",
        "referencing": "0.37.0", "rpds-py": "0.30.0", "typing-extensions": "4.15.0",
        "blake3": "1.0.7", "pyyaml": "6.0.2"}
ROOTS = ["cryptography", "jsonschema", "blake3", "pyyaml", "pip"]
FULL_PINS = {**PINS, "pip": "26.3", "cryptography": "50.0.2", "pillow": "13.0.0"}
FULL_ROOTS = [*ROOTS, "pillow"]
PROFILES = {
    PROFILE: ("Windows", {"AMD64", "X86_64"}, PINS, ROOTS),
    "windows-cpython312-amd64-full-qualification.v2": ("Windows", {"AMD64", "X86_64"}, FULL_PINS, FULL_ROOTS),
    "linux-cpython312-x86_64-full-qualification.v2": ("Linux", {"AMD64", "X86_64"}, FULL_PINS, FULL_ROOTS),
    "macos-cpython312-arm64-full-qualification.v2": ("Darwin", {"ARM64", "AARCH64"}, FULL_PINS, FULL_ROOTS),
}
CURRENT_FULL_PROFILES = frozenset(PROFILES) - {PROFILE}
UNAVAILABLE_PROFILES = {"macos-cpython312-x86_64-full-qualification.v2": "BLOCKED_UPSTREAM_PATCHED_WHEEL_UNAVAILABLE"}
BOOTSTRAP_PIP = {"filename": "pip-26.3-py3-none-any.whl", "version": "26.3", "bytes": 1950951,
    "sha256": "f3b60b20ffaadd4415ed7957212a38ac63fa4c5fa375bd0f4a797777940fad13",
    "url": "https://files.pythonhosted.org/packages/07/25/ee8c38ae72d66b844ce8eb9711ba905dba21ca1a8a0c960057c41cd23337/pip-26.3-py3-none-any.whl"}


def require(condition, code, detail=""):
    if not condition:
        raise ValueError(code + (":" + str(detail) if detail else ""))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rooted(body):
    return {**body, "receipt_root": sha(canonical(body))}


def _security_module():
    # Keep direct -I -S script startup independent of cwd/PYTHONPATH. This
    # sibling module is part of the admitted source envelope and uses stdlib.
    name = "mmc_dependency_security_bootstrap"
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("dependency_security.py"))
    require(spec is not None and spec.loader is not None, "MMC_DEPENDENCY_SECURITY_MODULE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def regular(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        require(not part.is_symlink() and not (hasattr(part, "is_junction") and part.is_junction()), "MMC_DEPENDENCY_LINK")
    require(path.is_file() and path.stat().st_size <= 32 * 1024 * 1024, "MMC_DEPENDENCY_FILE", path.name)
    return path.resolve(strict=True)


def load(path):
    def pairs(rows):
        result = {}
        for name, value in rows:
            require(name not in result, "MMC_DEPENDENCY_DUPLICATE_JSON")
            result[name] = value
        return result
    return json.loads(regular(path).read_bytes(), object_pairs_hook=pairs)


def _members(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= 10000 and len(infos) == len({i.filename for i in infos}), "MMC_DEPENDENCY_WHEEL_MEMBERS")
        require(sum(i.file_size for i in infos) <= 64 * 1024 * 1024, "MMC_DEPENDENCY_EXPANDED_LIMIT")
        result = {}
        folded = set()
        for info in infos:
            name = info.filename
            directory = info.is_dir()
            normalized_path = name[:-1] if directory else name
            pieces = normalized_path.split("/")
            require(all(re.fullmatch(r"[A-Za-z0-9_.+-]+", item) and item not in (".", "..")
                        and not item.endswith(".") for item in pieces), "MMC_DEPENDENCY_WHEEL_PATH", name)
            require(normalized_path.lower() not in folded and not info.flag_bits & 1 and
                    stat.S_IFMT(info.external_attr >> 16) in ((0, stat.S_IFDIR) if directory else (0, stat.S_IFREG)),
                    "MMC_DEPENDENCY_WHEEL_KIND")
            require(info.file_size <= 32 * 1024 * 1024, "MMC_DEPENDENCY_MEMBER_LIMIT")
            folded.add(normalized_path.lower())
            if directory:
                require(info.file_size == 0 and archive.read(info) == b"", "MMC_DEPENDENCY_WHEEL_DIRECTORY_CONTENT")
                continue
            result[name] = archive.read(info)
        require(not any(".data/" in name for name in result), "MMC_DEPENDENCY_INSTALL_SCHEME_UNSUPPORTED")
        file_names = {path.lower() for path in result}
        require(not any(any("/".join(name.split("/")[:index]).lower() in file_names
                            for index in range(1, len(name.split("/")))) for name in result),
                "MMC_DEPENDENCY_WHEEL_PATH_PREFIX")
    return result


def wheel_facts(path):
    members = _members(path)
    metadata_names = [name for name in members if name.endswith(".dist-info/METADATA")]
    require(len(metadata_names) == 1, "MMC_DEPENDENCY_METADATA")
    metadata_name = metadata_names[0]
    directory = metadata_name.rsplit("/", 1)[0]
    metadata = BytesParser().parsebytes(members[metadata_name])
    record_name = directory + "/RECORD"
    require(record_name in members and directory + "/WHEEL" in members, "MMC_DEPENDENCY_RECORD")
    rows = list(csv.reader(io.StringIO(members[record_name].decode("utf-8"))))
    require(all(len(row) == 3 for row in rows), "MMC_DEPENDENCY_RECORD_ROW")
    require(len(rows) == len({row[0] for row in rows}) and {row[0] for row in rows} == set(members),
            "MMC_DEPENDENCY_RECORD_CLOSURE")
    for name, encoded, length in rows:
        if name == record_name:
            require(encoded == length == "", "MMC_DEPENDENCY_RECORD_SELF")
        else:
            expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(members[name]).digest()).rstrip(b"=").decode()
            require(encoded == expected and length == str(len(members[name])), "MMC_DEPENDENCY_RECORD_HASH", name)
    license_names = sorted(name for name in members if name.startswith(directory + "/") and
                           ("license" in name.lower() or "copying" in name.lower() or "notice" in name.lower()))
    imports = set()
    for name in members:
        if name.endswith("/__init__.py") and name.count("/") == 1:
            imports.add(name.split("/", 1)[0])
        elif "/" not in name and name.endswith((".py", ".pyd", ".so")):
            imports.add(name.split(".", 1)[0])
    return {"filename": path.name, "name": normalized(metadata["Name"]), "version": metadata["Version"],
            "sha256": sha(path.read_bytes()), "bytes": path.stat().st_size,
            "requires_python": metadata.get("Requires-Python", ""),
            "requires_dist": metadata.get_all("Requires-Dist", []),
            "license_expression": metadata.get("License-Expression", "NOASSERTION"),
            "license_classifiers": sorted(value for value in metadata.get_all("Classifier", []) if value.startswith("License ::")),
            "license_files": [{"path": name, "sha256": sha(members[name]), "bytes": len(members[name])} for name in license_names],
            "import_modules": sorted(imports)}


def _profile(profile=PROFILE):
    require(profile not in UNAVAILABLE_PROFILES, UNAVAILABLE_PROFILES.get(profile, "MMC_DEPENDENCY_PROFILE_UNKNOWN"))
    require(profile in PROFILES, "MMC_DEPENDENCY_PROFILE_UNKNOWN")
    system, machines, _, _ = PROFILES[profile]
    require(platform.system() == system and platform.machine().upper() in machines
            and sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12),
            "MMC_DEPENDENCY_PROFILE_UNSUPPORTED")


def _cross_target(profile):
    require(profile not in UNAVAILABLE_PROFILES, UNAVAILABLE_PROFILES.get(profile, "MMC_DEPENDENCY_PROFILE_UNKNOWN"))
    require(profile in PROFILES and profile.startswith("macos-cpython312-"), "MMC_DEPENDENCY_CROSS_TARGET_UNSUPPORTED")
    machine = "arm64" if "-arm64-" in profile else "x86_64"
    formats = ["arm64", "universal2"] if machine == "arm64" else ["x86_64", "intel", "fat64", "fat32", "universal2", "universal"]
    platforms = ["macosx_11_0_" + form for form in formats]
    for minor in range(16, 3, -1):
        platforms.extend("macosx_10_" + str(minor) + "_" + form
                         for form in (["universal2"] if machine == "arm64" else formats))
    return {"platforms": platforms, "environment": {"implementation_name": "cpython", "implementation_version": "3.12.0",
        "os_name": "posix", "platform_machine": machine, "platform_release": "", "platform_system": "Darwin", "platform_version": "",
        "python_full_version": "3.12.0", "platform_python_implementation": "CPython", "python_version": "3.12", "sys_platform": "darwin"}}


def _packaging_check(wheelhouse, rows, *, roots=ROOTS, target_profile=None):
    pip = next(row for row in rows if row["name"] == "pip")
    path = wheelhouse / pip["filename"]
    program = """import hashlib,json,sys
from pathlib import Path
def check(condition, message):
 if not condition: raise ValueError(message)
p=Path(sys.argv[1]); check(hashlib.sha256(p.read_bytes()).hexdigest()==sys.argv[2], 'PIP_WHEEL_HASH')
sys.path.insert(0,str(p))
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import sys_tags,cpython_tags,compatible_tags
from pip._vendor.packaging.utils import parse_wheel_filename,canonicalize_name
from pip._vendor.packaging.markers import default_environment
for name,module in list(sys.modules.items()):
 if name=='pip' or name.startswith('pip.'):
  check(str(getattr(module,'__file__','')).replace('\\\\','/').startswith(str(p).replace('\\\\','/')+'/'), 'PIP_IMPORT_ORIGIN')
rows=json.load(sys.stdin); names={r['name']:r for r in rows}; target=json.loads(sys.argv[3]); env=default_environment()
if target:
 env.update(target['environment']); tags=set(cpython_tags((3,12),['cp312'],target['platforms']))|set(compatible_tags((3,12),'cp312',target['platforms']))
else: tags=set(sys_tags())
env['extra']=''
edges=[]
for row in rows:
 name,version,build,wheel_tags=parse_wheel_filename(row['filename'])
 check(canonicalize_name(name)==row['name'] and str(version)==row['version'] and tags.intersection(wheel_tags), 'WHEEL_TAG_OR_IDENTITY')
 check(not row['requires_python'] or SpecifierSet(row['requires_python']).contains(env['python_full_version']), 'REQUIRES_PYTHON')
 for raw in row['requires_dist']:
  req=Requirement(raw)
  if req.marker and not req.marker.evaluate(env): continue
  target=canonicalize_name(req.name)
  check(req.url is None and not req.extras and target in names and req.specifier.contains(names[target]['version']), 'MISSING_OR_INCOMPATIBLE_DEPENDENCY:'+raw)
  edges.append({'provider':target,'consumer':row['name'],'requirement':raw})
print(json.dumps({'edges':edges,'environment':env},sort_keys=True,separators=(',',':')))
"""
    target = None if target_profile is None else _cross_target(target_profile)
    run = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", program, str(path), pip["sha256"], json.dumps(target)],
                         input=canonical(rows), capture_output=True, timeout=90)
    require(run.returncode == 0, "MMC_DEPENDENCY_METADATA_CLOSURE", run.stderr.decode("utf-8", "replace")[-2000:])
    require(len(run.stdout) <= 1024 * 1024, "MMC_DEPENDENCY_OUTPUT_LIMIT")
    result = json.loads(run.stdout)
    reachable = set(roots)
    while True:
        expanded = reachable | {edge["provider"] for edge in result["edges"] if edge["consumer"] in reachable}
        if expanded == reachable:
            break
        reachable = expanded
    require(reachable == {row["name"] for row in rows}, "MMC_DEPENDENCY_UNREACHABLE_DISTRIBUTION")
    return result


def requirements(rows):
    return "".join(f"{row['name']}=={row['version']} --hash=sha256:{row['sha256']}\n" for row in sorted(rows, key=lambda row: row["name"])).encode("ascii")


def _bundle(root, dependency_bundle=None, dependency_lock_root=None):
    require((dependency_bundle is None) == (dependency_lock_root is None), "MMC_DEPENDENCY_BUNDLE_PIN_REQUIRED")
    if dependency_bundle is None:
        return Path(root).absolute() / "baseline/offline", LOCK_ROOT
    require(type(dependency_lock_root) is str and re.fullmatch(r"[0-9a-f]{64}", dependency_lock_root),
            "MMC_DEPENDENCY_BUNDLE_PIN_REQUIRED")
    return Path(dependency_bundle).absolute(), dependency_lock_root


def verify_wheelhouse(root: Path = ROOT, *, dependency_bundle=None, dependency_lock_root=None):
    root = Path(root).absolute()
    directory, expected_lock = _bundle(root, dependency_bundle, dependency_lock_root)
    lock = load(directory / "LOCK.json")
    profile = lock.get("profile")
    # Profiles are a closed implementation-supported set. An external caller
    # admits exact bytes by a separate lock-root argument, never by self-rehash.
    require(profile in PROFILES, "MMC_DEPENDENCY_PROFILE_UNKNOWN")
    _profile(profile)
    _, _, pins, roots = PROFILES[profile]
    body = {key: value for key, value in lock.items() if key != "lock_root"}
    require(lock.get("lock_root") == expected_lock == sha(canonical(body)) and lock.get("schema") == "mmc.offline-dependencies.v1"
            and lock.get("pins") == pins and lock.get("roots") == roots,
            "MMC_DEPENDENCY_LOCK")
    wheelhouse = directory / "wheels"
    require(wheelhouse.is_dir() and not wheelhouse.is_symlink(), "MMC_DEPENDENCY_DIRECTORY")
    expected = {row["filename"] for row in lock["wheels"]}
    actual = {path.name for path in wheelhouse.iterdir()}
    require(actual == expected and len(expected) == len(pins), "MMC_DEPENDENCY_FILE_CLOSURE")
    rows = []
    for row in lock["wheels"]:
        require(type(row.get("filename")) is str and row["filename"] == Path(row["filename"]).name,
                "MMC_DEPENDENCY_FILENAME")
        path = regular(wheelhouse / row["filename"])
        require(path.stat().st_size == row["bytes"] and sha(path.read_bytes()) == row["sha256"],
                "MMC_DEPENDENCY_WHEEL_HASH", path.name)
        facts = wheel_facts(path)
        require(facts == {key: value for key, value in row.items() if key != "acquisition"}, "MMC_DEPENDENCY_METADATA_PIN")
        require(row["name"] in pins and pins[row["name"]] == row["version"] and
                row["acquisition"]["sha256"] == row["sha256"] and
                row["acquisition"]["url"].startswith("https://files.pythonhosted.org/") and
                row["acquisition"]["filename"] == row["filename"], "MMC_DEPENDENCY_ACQUISITION_PIN")
        rows.append(facts)
    require({row["name"] for row in rows} == set(pins), "MMC_DEPENDENCY_DISTRIBUTIONS")
    require(regular(directory / "requirements.lock").read_bytes() == requirements(rows), "MMC_DEPENDENCY_REQUIREMENTS_HASHES")
    closure = _packaging_check(wheelhouse, rows, roots=roots)
    require(closure["edges"] == lock["dependency_edges"], "MMC_DEPENDENCY_EDGE_DRIFT")
    security = None
    if profile in CURRENT_FULL_PROFILES:
        security = _security_module().verify_snapshot(lock.get("dependency_security"), pins)
    return rooted({"schema": "mmc.offline-closure-verification.v1", "status": "PASS_EXACT_OFFLINE_CLOSURE",
                   "profile": profile, "lock_root": lock["lock_root"], "wheels": lock["wheels"],
                   "dependency_edges": closure["edges"], "environment": closure["environment"],
                   "dependency_security": {"status": "HISTORICAL_PROFILE_NOT_CLEARED"} if security is None else {
                       "status": security["status"], "security_root": security["receipt_root"],
                       "security_as_of": security["scan_timestamp_utc"], "claim": "DATED_QUERY_NO_MATCHES_NOT_ABSENCE_OF_VULNERABILITIES"},
                   "requirements_sha256": sha(requirements(rows)), "authority_effect": "NONE"})


def installation_command(python: Path, root: Path = ROOT, *, dependency_bundle=None, dependency_lock_root=None):
    receipt = verify_wheelhouse(root, dependency_bundle=dependency_bundle, dependency_lock_root=dependency_lock_root)
    directory, _ = _bundle(root, dependency_bundle, dependency_lock_root)
    paths = {str(directory / "wheels" / row["filename"]): row["sha256"] for row in receipt["wheels"]}
    paths[str(directory / "requirements.lock")] = receipt["requirements_sha256"]
    pip = next(row for row in receipt["wheels"] if row["name"] == "pip")
    code = ("import hashlib,sys\nfrom pathlib import Path\n"
            "prefix=Path(sys.executable).absolute().parent.parent\n"
            "config=prefix/'pyvenv.cfg'\n"
            "if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (config,*config.parents)): raise RuntimeError('MMC_DEPENDENCY_LINK')\n"
            "if not config.is_file() or prefix.resolve()==Path(sys.base_prefix).resolve(): raise RuntimeError('MMC_DEPENDENCY_NOT_ISOLATED_VENV')\n"
            "settings=dict(line.split('=',1) for line in config.read_text(encoding='utf-8').splitlines() if '=' in line)\n"
            "if {k.strip().lower():v.strip().lower() for k,v in settings.items()}.get('include-system-site-packages')!='false': raise RuntimeError('MMC_DEPENDENCY_SYSTEM_SITE_FORBIDDEN')\n"
            "sys.prefix=sys.exec_prefix=str(prefix)\nimport sysconfig\n"
            "purelib=Path(sysconfig.get_path('purelib',scheme='venv',vars={'base':str(prefix),'platbase':str(prefix)}))\n"
            "if not purelib.resolve().is_relative_to(prefix.resolve()) or any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (purelib,*purelib.parents)): raise RuntimeError('MMC_DEPENDENCY_LINK')\n"
            "checks=" + repr(paths) + "\n"
            "if not all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in checks.items()): raise RuntimeError('MMC_DEPENDENCY_BOOTSTRAP_HASH')\n"
            "if not purelib.is_dir() or any(purelib.iterdir()): raise RuntimeError('MMC_DEPENDENCY_INSTALL_TARGET_NOT_EMPTY')\n"
            "sys.path.insert(0," + repr(str(directory / "wheels" / pip["filename"])) + ")\n"
            "from pip._internal.cli.main import main\nraise SystemExit(main(sys.argv[1:]))")
    return [str(python), "-I", "-S", "-B", "-c", code, "--isolated", "install", "--ignore-installed",
            "--no-index", "--only-binary=:all:", "--require-hashes", "--disable-pip-version-check", "--no-compile",
            "--find-links", str(directory / "wheels"), "-r", str(directory / "requirements.lock")]


def observation_command(python: Path, root: Path = ROOT, *, allow_mmc_version: str | None = None,
                        mmc_wheel: Path | None = None, dependency_bundle=None, dependency_lock_root=None):
    command = [str(python), "-I", "-S", "-B", str(Path(__file__).resolve()), "--root", str(Path(root).absolute()), "--observe-installed"]
    if allow_mmc_version is not None:
        command += ["--allow-mmc-version", allow_mmc_version]
    if mmc_wheel is not None:
        command += ["--mmc-wheel", str(Path(mmc_wheel).absolute())]
    if dependency_bundle is not None or dependency_lock_root is not None:
        directory, expected_lock = _bundle(root, dependency_bundle, dependency_lock_root)
        command += ["--dependency-bundle", str(directory), "--dependency-lock-root", expected_lock]
    return command


def observe_installed(root: Path = ROOT, *, allow_mmc_version: str | None = None,
                      mmc_wheel: Path | None = None, dependency_bundle=None, dependency_lock_root=None):
    # -I alone still runs site, which can execute .pth/sitecustomize before
    # this function. Require a site-disabled interpreter for the observation.
    require(sys.flags.isolated and sys.flags.no_site, "MMC_DEPENDENCY_SAFE_STARTUP_REQUIRED")
    receipt = verify_wheelhouse(root, dependency_bundle=dependency_bundle, dependency_lock_root=dependency_lock_root)
    # On CPython 3.12 -S leaves sys.prefix at the base interpreter. Identify
    # the venv from its executable without invoking site to repair the prefix.
    prefix = Path(sys.executable).absolute().parent.parent
    config_path = regular(prefix / "pyvenv.cfg")
    prefix = prefix.resolve()
    require(prefix != Path(sys.base_prefix).resolve(), "MMC_DEPENDENCY_NOT_ISOLATED_VENV")
    config = config_path.read_text(encoding="utf-8")
    settings = {}
    for line in config.splitlines():
        if "=" in line:
            key, value = (item.strip().lower() for item in line.split("=", 1))
            require(key not in settings, "MMC_DEPENDENCY_VENV_CONFIG_DUPLICATE")
            settings[key] = value
    require(settings.get("include-system-site-packages") == "false", "MMC_DEPENDENCY_SYSTEM_SITE_FORBIDDEN")
    purelib = Path(sysconfig.get_path("purelib", scheme="venv", vars={"base": str(prefix), "platbase": str(prefix)})).resolve()
    require(purelib.is_relative_to(prefix), "MMC_DEPENDENCY_NOT_ISOLATED_VENV")
    distributions = list(importlib.metadata.distributions(path=[str(purelib)]))
    actual = {normalized(dist.metadata["Name"]): dist.version for dist in distributions}
    require(len(actual) == len(distributions), "MMC_DEPENDENCY_DUPLICATE_INSTALLED_DISTRIBUTION")
    expected = dict(PROFILES[receipt["profile"]][2])
    require((allow_mmc_version is None) == (mmc_wheel is None), "MMC_DEPENDENCY_MMC_WHEEL_REQUIRED")
    directory, _ = _bundle(root, dependency_bundle, dependency_lock_root)
    wheel_rows = [(row, directory / "wheels" / row["filename"]) for row in receipt["wheels"]]
    if allow_mmc_version is not None:
        expected["mosaic-migration-compiler"] = allow_mmc_version
        mmc_wheel = regular(mmc_wheel)
        facts = wheel_facts(mmc_wheel)
        require(facts["name"] == "mosaic-migration-compiler" and facts["version"] == allow_mmc_version,
                "MMC_DEPENDENCY_MMC_WHEEL_IDENTITY")
        wheel_rows.append((facts, mmc_wheel))
    require(actual == expected, "MMC_DEPENDENCY_INSTALLED_DISTRIBUTIONS", actual)
    checked = 0
    modules = {}
    expected_paths = set()
    for row, wheel_path in wheel_rows:
        members = _members(wheel_path)
        expected_paths.update(members)
        metadata_dir = next(name.rsplit("/", 1)[0] for name in members if name.endswith(".dist-info/METADATA"))
        for name, value in ((metadata_dir + "/INSTALLER", b"pip\n"), (metadata_dir + "/REQUESTED", b"")):
            require(regular(purelib / name).read_bytes() == value, "MMC_DEPENDENCY_GENERATED_METADATA", name)
            expected_paths.add(name)
        if row["name"] == "mosaic-migration-compiler":
            name = metadata_dir + "/direct_url.json"
            direct = load(purelib / name)
            require(set(direct) == {"archive_info", "url"} and direct["url"] == wheel_path.absolute().as_uri() and
                    direct["archive_info"].get("hashes") == {"sha256": row["sha256"]} and
                    set(direct["archive_info"]) <= {"hash", "hashes"} and
                    direct["archive_info"].get("hash", "sha256=" + row["sha256"]) == "sha256=" + row["sha256"],
                    "MMC_DEPENDENCY_MMC_DIRECT_URL")
            expected_paths.add(name)
        for name, raw in members.items():
            if name.endswith(".dist-info/RECORD"):
                continue
            installed = regular(purelib / name)
            require(installed.is_relative_to(purelib) and sha(installed.read_bytes()) == sha(raw),
                    "MMC_DEPENDENCY_INSTALLED_FILE_HASH", name)
            checked += 1
    installed_paths = set()
    for path in purelib.rglob("*"):
        require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                "MMC_DEPENDENCY_INSTALLED_LINK")
        if path.is_file():
            installed_paths.add(path.relative_to(purelib).as_posix())
        else:
            require(path.is_dir(), "MMC_DEPENDENCY_INSTALLED_KIND")
    require(installed_paths == expected_paths, "MMC_DEPENDENCY_UNDECLARED_INSTALLED_FILES",
            sorted(installed_paths ^ expected_paths)[:10])
    # Import only after all immutable dependency code has been checked.
    # Do not invoke site/addsitedir: .pth processing is never needed here.
    sys.path.insert(0, str(purelib))
    for row, _ in wheel_rows:
        for name in row["import_modules"]:
            module = importlib.import_module(name)
            origin = Path(module.__file__).resolve()
            require(origin.is_relative_to(purelib), "MMC_DEPENDENCY_IMPORT_ORIGIN", name)
            modules[name] = str(origin)
    return rooted({"schema": "mmc.installed-dependencies.v1", "status": "PASS_ISOLATED_LOCKED_DEPENDENCIES",
                   "profile": receipt["profile"], "lock_root": receipt["lock_root"], "purelib": str(purelib),
                   "distributions": actual, "immutable_files_verified": checked, "module_origins": modules,
                   "complete_file_count": len(installed_paths),
                   "mmc_wheel_sha256": None if mmc_wheel is None else sha(mmc_wheel.read_bytes()),
                   "system_site_packages": False, "authority_effect": "NONE"})


def author_lock(root: Path = ROOT, *, dependency_bundle=None, profile=PROFILE, cross_target=False):
    """Explicit acquisition-time network action, never called by verification."""
    import urllib.request
    if cross_target:
        _cross_target(profile)
        require(dependency_bundle is not None, "MMC_DEPENDENCY_CROSS_TARGET_BUNDLE_REQUIRED")
    else:
        _profile(profile)
    _, _, pins, roots = PROFILES[profile]
    directory = Path(dependency_bundle).absolute() if dependency_bundle is not None else Path(root).absolute() / "baseline/offline"
    rows = []
    for path in sorted((directory / "wheels").iterdir(), key=lambda item: item.name):
        facts = wheel_facts(regular(path))
        require(pins.get(facts["name"]) == facts["version"], "MMC_DEPENDENCY_AUTHOR_PIN")
        url = "https://pypi.org/pypi/" + facts["name"] + "/" + facts["version"] + "/json"
        with urllib.request.urlopen(url, timeout=20) as response:
            release = json.load(response)
        selected = [row for row in release["urls"] if row["filename"] == path.name]
        require(len(selected) == 1 and selected[0]["digests"]["sha256"] == facts["sha256"] and
                selected[0]["packagetype"] == "bdist_wheel", "MMC_DEPENDENCY_PYPI_DIGEST")
        facts["acquisition"] = {"index_metadata": url, "filename": path.name,
                                "url": selected[0]["url"], "sha256": selected[0]["digests"]["sha256"],
                                "upload_time": selected[0]["upload_time_iso_8601"]}
        rows.append(facts)
    require({row["name"] for row in rows} == set(pins), "MMC_DEPENDENCY_AUTHOR_CLOSURE")
    closure = _packaging_check(directory / "wheels", rows, roots=roots, target_profile=profile if cross_target else None)
    body = {"schema": "mmc.offline-dependencies.v1", "profile": profile,
            "pins": pins, "roots": roots, "wheels": rows, "dependency_edges": closure["edges"],
            "acquisition": "EXACT_WHEELS_FROM_PYPI_RELEASE_JSON_SHA256_CHECKED", "authority_effect": "NONE"}
    if profile in CURRENT_FULL_PROFILES:
        body["dependency_security"] = _security_module().audit(pins)
    (directory / "LOCK.json").write_bytes(canonical({**body, "lock_root": sha(canonical(body))}))
    (directory / "requirements.lock").write_bytes(requirements(rows))
    if cross_target:
        return rooted({"schema": "mmc.offline-acquisition-target-check.v1", "status": "ACQUIRED_PENDING_NATIVE_VERIFICATION",
                       "profile": profile, "lock_root": sha(canonical(body)), "platform_qualification": "NOT_PERFORMED", "authority_effect": "NONE"})
    return verify_wheelhouse(root, **({"dependency_bundle": directory, "dependency_lock_root": sha(canonical(body))}
                                    if dependency_bundle is not None else {}))


def _capture_acquisition(command, directory, *, timeout=600):
    started = {"schema": "mmc.dependency-download.v1", "status": "STARTED", "command": command,
               "exit_code": None, "authority_effect": "NONE"}
    (directory / "acquisition.started.json").write_bytes(canonical(rooted(started)))
    stdout = b""; stderr = b""; terminal = dict(started)
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        stdout, stderr = result.stdout, result.stderr
        terminal.update(status="COMPLETED", exit_code=result.returncode)
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
        (directory / "acquisition.stdout").write_bytes(stdout)
        (directory / "acquisition.stderr").write_bytes(stderr)
        terminal.update(stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
        (directory / "acquisition.terminal.json").write_bytes(canonical(rooted(terminal)))


def acquire_bundle(directory: Path, profile: str, root: Path = ROOT, *, cross_target=False):
    """Explicit network acquisition on the intended native host; never qualification."""
    require(profile not in UNAVAILABLE_PROFILES, UNAVAILABLE_PROFILES.get(profile, "MMC_DEPENDENCY_PROFILE_UNKNOWN"))
    require(profile in CURRENT_FULL_PROFILES, "MMC_DEPENDENCY_CURRENT_ACQUISITION_PROFILE_REQUIRED")
    target = _cross_target(profile) if cross_target else None
    if not cross_target:
        _profile(profile)
    directory = Path(directory).absolute()
    require(not directory.exists(), "MMC_DEPENDENCY_ACQUISITION_CUSTODY_EXISTS")
    directory.mkdir(parents=True)
    terminal = {"schema": "mmc.dependency-acquisition.v1", "profile": profile,
                "status": "RUNNING", "cross_target_acquisition": cross_target,
                "authority_effect": "NONE", "platform_qualification": "NOT_PERFORMED"}
    (directory / "ACQUISITION.json").write_bytes(canonical(rooted(terminal)))
    try:
        wheels = directory / "wheels"; wheels.mkdir()
        # Acquire the reviewed patched installer with the standard library.
        # Never import the vulnerable historical baseline installer to obtain
        # its replacement. Official metadata and bytes must both match the
        # independently embedded acquisition pin before any pip import.
        pip = BOOTSTRAP_PIP
        import urllib.request
        metadata_url = "https://pypi.org/pypi/pip/" + pip["version"] + "/json"
        with urllib.request.urlopen(metadata_url, timeout=30) as response:
            raw_metadata = response.read(2 * 1024 * 1024 + 1)
        require(len(raw_metadata) <= 2 * 1024 * 1024, "MMC_DEPENDENCY_ACQUISITION_METADATA_LIMIT")
        (directory / "bootstrap-pip-metadata.json").write_bytes(raw_metadata)
        release = json.loads(raw_metadata)
        selected = [row for row in release["urls"] if row["filename"] == pip["filename"]]
        require(len(selected) == 1 and selected[0]["digests"]["sha256"] == pip["sha256"] and
                selected[0]["url"] == pip["url"] and selected[0]["size"] == pip["bytes"] and
                selected[0]["packagetype"] == "bdist_wheel" and not selected[0]["yanked"], "MMC_DEPENDENCY_PIP_ACQUISITION_PIN")
        with urllib.request.urlopen(pip["url"], timeout=30) as response:
            raw_installer = response.read(pip["bytes"] + 1)
        require(len(raw_installer) == pip["bytes"] and sha(raw_installer) == pip["sha256"], "MMC_DEPENDENCY_PIP_ACQUISITION_HASH")
        installer = wheels / pip["filename"]; installer.write_bytes(raw_installer)
        facts = wheel_facts(regular(installer))
        require(facts["name"] == "pip" and facts["version"] == pip["version"], "MMC_DEPENDENCY_PIP_ACQUISITION_IDENTITY")
        program = ("import hashlib,sys\nfrom pathlib import Path\np=Path(sys.argv.pop(1))\n"
                   "if hashlib.sha256(p.read_bytes()).hexdigest()!=sys.argv.pop(1): raise RuntimeError('MMC_DEPENDENCY_BOOTSTRAP_HASH')\n"
                   "sys.path.insert(0,str(p))\nfrom pip._internal.cli.main import main\nraise SystemExit(main(sys.argv[1:]))")
        pins = PROFILES[profile][2]
        command = [sys.executable, "-I", "-S", "-B", "-c", program, str(installer), pip["sha256"],
                   "--isolated", "download", "--only-binary=:all:", "--no-deps", "--disable-pip-version-check",
                   "--index-url", "https://pypi.org/simple", "--dest", str(wheels),
                   *[name + "==" + version for name, version in sorted(pins.items())]]
        if target is not None:
            command += ["--python-version", "312", "--implementation", "cp", "--abi", "cp312", "--abi", "abi3", "--abi", "none"]
            for platform_tag in target["platforms"]:
                command += ["--platform", platform_tag]
        run = _capture_acquisition(command, directory)
        terminal.update(exit_code=run.returncode, stdout_sha256=sha(run.stdout), stderr_sha256=sha(run.stderr))
        require(run.returncode == 0, "MMC_DEPENDENCY_ACQUISITION_FAILED")
        receipt = author_lock(root, dependency_bundle=directory, profile=profile, cross_target=cross_target)
        terminal.update(status="ACQUIRED_PENDING_REVIEW_NOT_QUALIFIED", lock_root=receipt["lock_root"])
    except BaseException as error:
        terminal.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        (directory / "ACQUISITION.json").write_bytes(canonical(rooted(terminal)))
    return rooted(terminal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--author-lock", action="store_true", help="explicitly contact PyPI and author a successor lock")
    parser.add_argument("--observe-installed", action="store_true")
    parser.add_argument("--allow-mmc-version")
    parser.add_argument("--mmc-wheel", type=Path)
    parser.add_argument("--dependency-bundle", type=Path)
    parser.add_argument("--dependency-lock-root")
    parser.add_argument("--profile", choices=sorted(set(PROFILES) | set(UNAVAILABLE_PROFILES)), default=PROFILE)
    parser.add_argument("--acquire-bundle", type=Path, help="explicit network acquisition into a fresh directory on this native host")
    parser.add_argument("--cross-target", action="store_true", help="macOS wheel acquisition only; never native verification or qualification")
    args = parser.parse_args()
    require(sum((args.author_lock, args.observe_installed, args.acquire_bundle is not None)) <= 1, "MMC_DEPENDENCY_ARGUMENTS")
    require(not args.cross_target or args.author_lock or args.acquire_bundle is not None, "MMC_DEPENDENCY_CROSS_TARGET_ACQUISITION_ONLY")
    options = {"dependency_bundle": args.dependency_bundle, "dependency_lock_root": args.dependency_lock_root}
    result = acquire_bundle(args.acquire_bundle, args.profile, args.root, cross_target=args.cross_target) if args.acquire_bundle is not None else (
        author_lock(args.root, dependency_bundle=args.dependency_bundle, profile=args.profile, cross_target=args.cross_target) if args.author_lock else (
        observe_installed(args.root, allow_mmc_version=args.allow_mmc_version, mmc_wheel=args.mmc_wheel, **options) if args.observe_installed
        else verify_wheelhouse(args.root, **options)))
    print(canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
