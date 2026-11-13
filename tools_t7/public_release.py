"""Build and verify deterministic Apache-2.0 MMC public-release archives.

The builder never publishes and never writes a private key. When signing is requested,
the encrypted DKN key path is public routing metadata and the passphrase is read through
an interactive, non-echoing prompt. Generated output must be outside the source tree.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require
from mosaic_mmc_product.release_certification import (
    META_NAMES,
    build_dkn_binding,
    build_embedded_metadata,
    certificate_signing_body,
    verify_embedded_metadata,
)
from tools.common import regular_files
from tools_t7.package import build_wheel
from tools_t7.qualification_index import build_index, summary as qualification_summary

PUBLIC_VERSION = "v0.1"
ENGINEERING_REVISION = "r013"
PUBLIC_NAMESPACE = "mosaic.migration-compilation.v0.1"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rooted(body: dict) -> dict:
    return {**body, "root": sha(canonical(body))}


def source_rows() -> list[tuple[str, bytes]]:
    rows = [(path, file.read_bytes()) for path, file in regular_files(ROOT)]
    require(rows and len({path.casefold() for path, _ in rows}) == len(rows),
            "MMC_PUBLIC_SOURCE_ALIAS")
    return rows


def source_manifest(rows: list[tuple[str, bytes]]) -> dict:
    body = {
        "schema": "mosaic.mmc.public-source-manifest.v0.1",
        "version": PUBLIC_VERSION,
        "engineering_revision": ENGINEERING_REVISION,
        "members": [{"path": path, "bytes": len(raw), "sha256": sha(raw)}
                    for path, raw in rows],
        "member_count": len(rows),
        "logical_bytes": sum(len(raw) for _, raw in rows),
        "license": "Apache-2.0",
        "authority_effect": "NONE",
    }
    return rooted(body)


def release_identity(manifest: dict) -> dict:
    body = {
        "schema": "mosaic.mmc.public-release-identity.v0.1",
        "product": "Mosaic Migration Compiler",
        "version": PUBLIC_VERSION,
        "python_distribution_version": "0.1.0a9",
        "engineering_revision": ENGINEERING_REVISION,
        "publisher": "Adam Mazurk",
        "copyright": "Copyright 2026 Adam Mazurk",
        "license": "Apache-2.0",
        "public_namespace": PUBLIC_NAMESPACE,
        "source_manifest_root": manifest["root"],
        "production_effect_adapter": "NOT_SHIPPED",
        "native_pippi_host": "NOT_BOUND",
        "macos_execution": "NOT_QUALIFIED",
        "authority_effect": "NONE",
    }
    return rooted(body)


def _load_dkn(passport_path: Path, namespace_path: Path) -> tuple[dict, dict, dict]:
    try:
        from dkn_core.namespace import verify_namespace
        from dkn_core.passport import verify_passport
    except ImportError as error:
        raise SystemExit("MMC_PUBLIC_DKN_CORE_REQUIRED") from error
    namespace = verify_namespace(decode(namespace_path.read_bytes(), limit=1024 * 1024))
    passport = verify_passport(decode(passport_path.read_bytes(), limit=1024 * 1024))
    require(namespace["material"]["semantic_namespace"] == PUBLIC_NAMESPACE,
            "MMC_PUBLIC_DKN_NAMESPACE_MISMATCH")
    require(passport["namespace"] == namespace
            and passport["public_key_hex"] == namespace["material"]["public_key_hex"],
            "MMC_PUBLIC_DKN_PASSPORT_MISMATCH")
    binding = build_dkn_binding(
        public_namespace=PUBLIC_NAMESPACE,
        authority_public_key_hex=passport["public_key_hex"],
        namespace_id=namespace["namespace_id"],
        namespace_binding_hash=namespace["namespace_binding_hash"],
        passport_root=passport["passport_hash"],
    )
    return namespace, passport, binding


def _signature(*, private_key_path: Path, signing_body: dict,
               expected_public_key_hex: str) -> str:
    try:
        from dkn_core.ceremony import load_encrypted_private_key
        from dkn_core.crypto import public_key_hex
    except ImportError as error:
        raise SystemExit("MMC_PUBLIC_DKN_CORE_REQUIRED") from error
    passphrase = getpass.getpass("DKN publisher-key passphrase: ").encode("utf-8")
    key = load_encrypted_private_key(private_key_path, passphrase)
    require(public_key_hex(key) == expected_public_key_hex,
            "MMC_PUBLIC_DKN_PRIVATE_KEY_MISMATCH")
    return key.sign(canonical(signing_body)).hex()


def archive_manifest(*, artifact: str, completeness: str,
                     rows: list[tuple[str, bytes]], metadata: dict[str, bytes]) -> dict:
    members = [{"path": path, "bytes": len(raw), "sha256": sha(raw)}
               for path, raw in sorted([*rows, *metadata.items()])]
    state = json.loads(metadata[META_NAMES[0]])
    dkn = json.loads(metadata[META_NAMES[1]])
    thr = json.loads(metadata[META_NAMES[2]])
    certificate = json.loads(metadata[META_NAMES[3]])
    body = {
        "schema": "mosaic.mmc.public-artifact-manifest.v0.1",
        "artifact": artifact,
        "completeness": completeness,
        "version": PUBLIC_VERSION,
        "engineering_revision": ENGINEERING_REVISION,
        "members": members,
        "member_count": len(members),
        "state_root": state["state_root"],
        "H_s": thr["commitments"]["H_s"],
        "H_c": thr["commitments"]["H_c"],
        "H_m": thr["commitments"]["H_m"],
        "H_j": thr["commitments"]["H_j"],
        "H_r": thr["commitments"]["H_r"],
        "thr_body_root": thr["h_body"],
        "dkn_binding_root": dkn["dkn_binding_root"],
        "certificate_root": certificate["certificate_root"],
        "certificate_status": certificate["certificate_status"],
        "transport_sha256_scope": "EXTERNAL_COMPLETE_ARCHIVE_BYTES",
        "authority_effect": "NONE",
    }
    return rooted(body)


def write_archive(path: Path, *, artifact: str, completeness: str,
                  rows: list[tuple[str, bytes]], source_manifest_root: str,
                  release_identity_root: str, dkn_binding: dict | None,
                  private_key: Path | None) -> dict:
    metadata = build_embedded_metadata(
        payload_rows=rows, artifact=artifact, completeness=completeness,
        version=PUBLIC_VERSION, engineering_revision=ENGINEERING_REVISION,
        source_manifest_root=source_manifest_root,
        release_identity_root=release_identity_root,
        public_namespace=PUBLIC_NAMESPACE, dkn_binding=dkn_binding,
    )
    if private_key is not None:
        require(dkn_binding is not None, "MMC_PUBLIC_DKN_BINDING_REQUIRED")
        signature = _signature(
            private_key_path=private_key,
            signing_body=certificate_signing_body(metadata),
            expected_public_key_hex=dkn_binding["authority_public_key_hex"],
        )
        metadata = build_embedded_metadata(
            payload_rows=rows, artifact=artifact, completeness=completeness,
            version=PUBLIC_VERSION, engineering_revision=ENGINEERING_REVISION,
            source_manifest_root=source_manifest_root,
            release_identity_root=release_identity_root,
            public_namespace=PUBLIC_NAMESPACE, dkn_binding=dkn_binding,
            signature_hex=signature,
        )
    manifest = archive_manifest(artifact=artifact, completeness=completeness,
                                rows=rows, metadata=metadata)
    entries = [("MANIFEST.json", canonical(manifest) + b"\n"),
               *rows, *metadata.items()]
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED,
                         allowZip64=False) as archive:
        for name, raw in sorted(entries):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, raw)
    verified = verify_archive(path, source_manifest_root=source_manifest_root,
                              release_identity_root=release_identity_root)
    require(verified["manifest_root"] == manifest["root"],
            "MMC_PUBLIC_ARCHIVE_POSTWRITE_MISMATCH")
    return {
        "path": path.name, "artifact": artifact, "bytes": path.stat().st_size,
        "sha256": sha(path.read_bytes()), "manifest_root": manifest["root"],
        "state_root": manifest["state_root"],
        "thr_body_root": manifest["thr_body_root"],
        "dkn_binding_root": manifest["dkn_binding_root"],
        "certificate_root": manifest["certificate_root"],
        "certificate_status": manifest["certificate_status"],
    }


def verify_archive(path: Path, *, source_manifest_root: str,
                   release_identity_root: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        require(len(names) == len(set(names)) and names == sorted(names)
                and names.count("MANIFEST.json") == 1,
                "MMC_PUBLIC_ARCHIVE_SET_INVALID")
        require(all(row.date_time == FIXED_TIME and not row.is_dir()
                    and stat.S_ISREG(row.external_attr >> 16)
                    and row.compress_type == zipfile.ZIP_STORED
                    for row in infos), "MMC_PUBLIC_ARCHIVE_MEMBER_INVALID")
        manifest = json.loads(archive.read("MANIFEST.json"))
        body = {key: value for key, value in manifest.items() if key != "root"}
        require(manifest.get("root") == sha(canonical(body)),
                "MMC_PUBLIC_MANIFEST_ROOT_INVALID")
        expected = {row["path"]: row for row in manifest["members"]}
        require(set(names) == {"MANIFEST.json", *expected},
                "MMC_PUBLIC_ARCHIVE_CLOSURE_INVALID")
        for name, row in expected.items():
            raw = archive.read(name)
            require(len(raw) == row["bytes"] and sha(raw) == row["sha256"],
                    "MMC_PUBLIC_ARCHIVE_HASH_INVALID", name)
        payload = [(name, archive.read(name)) for name in names
                   if name != "MANIFEST.json" and not name.startswith("META/")]
        metadata = {name: archive.read(name) for name in META_NAMES}
        result = verify_embedded_metadata(
            payload_rows=payload, metadata=metadata,
            artifact=manifest["artifact"], completeness=manifest["completeness"],
            version=PUBLIC_VERSION, engineering_revision=ENGINEERING_REVISION,
            source_manifest_root=source_manifest_root,
            release_identity_root=release_identity_root,
        )
        require(manifest["state_root"] == result["state_root"]
                and manifest["thr_body_root"] == result["thr_body_root"]
                and manifest["dkn_binding_root"] == result["dkn_binding_root"]
                and manifest["certificate_root"] == result["certificate_root"]
                and manifest["certificate_status"] == result["certificate_status"],
                "MMC_PUBLIC_MANIFEST_CERTIFICATION_MISMATCH")
    return {"status": "PASS", "manifest_root": manifest["root"],
            "certificate_status": manifest["certificate_status"],
            "authority_effect": "NONE"}


def build(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    require(not output.exists(), "MMC_PUBLIC_OUTPUT_EXISTS")
    require(ROOT not in output.parents and output != ROOT,
            "MMC_PUBLIC_OUTPUT_INSIDE_SOURCE")
    output.mkdir(parents=True)
    rows = source_rows()
    manifest = source_manifest(rows)
    identity = release_identity(manifest)
    qualification_index = build_index(ROOT)
    qualification_path = output / "MMC-v0.1-qualification-index.json"
    qualification_raw = canonical(qualification_index) + b"\n"
    qualification_path.write_bytes(qualification_raw)
    dkn_binding = None
    if args.passport is not None or args.namespace is not None or args.private_key is not None:
        require(args.passport is not None and args.namespace is not None,
                "MMC_PUBLIC_DKN_INPUTS_INCOMPLETE")
        namespace, passport, dkn_binding = _load_dkn(args.passport, args.namespace)
        rows = [*rows,
                ("IDENTITY/DKN-NAMESPACE.json", canonical(namespace) + b"\n"),
                ("IDENTITY/DKN-PASSPORT.json", canonical(passport) + b"\n")]
    source = write_archive(
        output / "MMC-v0.1-source.zip", artifact="MMC_SOURCE",
        completeness="COMPLETE_PUBLIC_SOURCE_PRIVATE_HISTORY_AND_THIRD_PARTY_BINARIES_EXCLUDED",
        rows=rows, source_manifest_root=manifest["root"],
        release_identity_root=identity["root"], dkn_binding=dkn_binding,
        private_key=args.private_key,
    )
    wheel = build_wheel(ROOT)
    runtime_rows = [
        ("mosaic_migration_compiler-0.1.0a9-py3-none-any.whl", wheel),
        ("README.md", (ROOT / "README.md").read_bytes()),
        ("LICENSE", (ROOT / "LICENSE").read_bytes()),
        ("NOTICE", (ROOT / "NOTICE").read_bytes()),
        ("THIRD-PARTY-NOTICES.md", (ROOT / "THIRD-PARTY-NOTICES.md").read_bytes()),
    ]
    if dkn_binding is not None:
        runtime_rows.extend([
            ("IDENTITY/DKN-NAMESPACE.json", canonical(namespace) + b"\n"),
            ("IDENTITY/DKN-PASSPORT.json", canonical(passport) + b"\n"),
        ])
    runtime = write_archive(
        output / "MMC-v0.1-runtime.zip", artifact="MMC_RUNTIME",
        completeness="CORE_RUNTIME_WHEEL_NO_PLATFORM_DEPENDENCIES",
        rows=runtime_rows, source_manifest_root=manifest["root"],
        release_identity_root=identity["root"], dkn_binding=dkn_binding,
        private_key=args.private_key,
    )
    release_body = {
        "schema": "mosaic.mmc.public-release.v0.1",
        "product": "Mosaic Migration Compiler",
        "version": PUBLIC_VERSION,
        "python_distribution_version": "0.1.0a9",
        "engineering_revision": ENGINEERING_REVISION,
        "publisher": "Adam Mazurk",
        "license": "Apache-2.0",
        "public_namespace": PUBLIC_NAMESPACE,
        "source_manifest": manifest,
        "release_identity": identity,
        "qualification_index": {
            **qualification_summary(qualification_index),
            "path": qualification_path.name,
            "sha256": sha(qualification_raw),
        },
        "artifacts": [source, runtime],
        "platform_dependencies": "SEPARATE_ONLY_WHEN_REDISTRIBUTION_AUTHORIZED",
        "qualification_evidence": "SEPARATE_REDACTED_RELEASE_ASSET",
        "developer_qualification_kit": "SEPARATE_PRIVATE_OR_REDACTED_ASSET",
        "publication_performed": False,
        "authority_effect": "NONE",
    }
    release = rooted(release_body)
    release_path = output / "MMC-v0.1-release.json"
    release_raw = canonical(release) + b"\n"
    release_path.write_bytes(release_raw)
    checksums = [
        {"path": release_path.name, "sha256": sha(release_raw)},
        {"path": qualification_path.name, "sha256": sha(qualification_raw)},
        *release["artifacts"],
    ]
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in checksums)
    (output / "SHA256SUMS").write_text(sums, encoding="ascii", newline="\n")
    return release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--namespace", type=Path)
    build_parser.add_argument("--passport", type=Path)
    build_parser.add_argument("--private-key", type=Path)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("archive", type=Path)
    verify_parser.add_argument("--source-manifest-root", required=True)
    verify_parser.add_argument("--release-identity-root", required=True)
    args = parser.parse_args()
    if args.operation == "build":
        result = build(args)
    else:
        result = verify_archive(args.archive,
                                source_manifest_root=args.source_manifest_root,
                                release_identity_root=args.release_identity_root)
    print(canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
