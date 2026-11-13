"""Assemble the exact MMC release-audit input consumed by the CMBA publisher."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from mosaic_mmc import canonical, decode
from mosaic_mmc.errors import require


CORE_FILES = {
    "MMC-v0.1-qualification-index.json",
    "MMC-v0.1-release.json",
    "MMC-v0.1-runtime.zip",
    "MMC-v0.1-source.zip",
    "SHA256SUMS",
}


def _load(path: Path) -> dict:
    value = decode(path.read_bytes().rstrip(b"\r\n"), limit=16 * 1024 * 1024)
    require(isinstance(value, dict), "MMC_RELEASE_AUDIT_JSON", path.name)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(value: dict, field: str) -> bool:
    body = {key: item for key, item in value.items() if key != field}
    return value.get(field) == hashlib.sha256(canonical(body)).hexdigest()


def _checksums(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        require(separator and len(digest) == 64 and name not in rows,
                "MMC_RELEASE_AUDIT_CHECKSUM_FORMAT")
        rows[name] = digest
    return rows


def _test_summary(qualification: dict) -> dict:
    groups = qualification.get("tests")
    require(isinstance(groups, dict) and groups, "MMC_RELEASE_AUDIT_TESTS")
    total = 0
    unexpected = []
    for group, record in groups.items():
        outcomes = record.get("test_outcomes")
        require(isinstance(outcomes, dict) and outcomes, "MMC_RELEASE_AUDIT_TESTS", group)
        total += len(outcomes)
        unexpected.extend(record.get("unexpected", []))
    return {"tests": total, "unexpected": len(unexpected),
            "host_limitations": len(qualification.get("host_limitations", [])),
            "successor_superseded_assertions":
                len(qualification.get("successor_superseded_assertions", []))}


def _platform(label: str, verification: dict, qualification: dict,
              expected_source: str, expected_tests: int) -> dict:
    require(verification.get("status") == "PASS_SCOPED_ALPHA_CANDIDATE",
            "MMC_RELEASE_AUDIT_VERIFICATION_STATUS", label)
    require(verification.get("platform") == label and verification.get("stage_i1_verified") is True,
            "MMC_RELEASE_AUDIT_PLATFORM", label)
    require(_rooted(verification, "receipt_root"), "MMC_RELEASE_AUDIT_VERIFICATION_ROOT", label)
    require(qualification.get("status") ==
            "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS"
            and _rooted(qualification, "receipt_root"),
            "MMC_RELEASE_AUDIT_QUALIFICATION_ROOT", label)
    require(verification.get("source_root") == qualification.get("source_root") == expected_source,
            "MMC_RELEASE_AUDIT_SOURCE", label)
    require(verification.get("qualification_root") == qualification.get("receipt_root"),
            "MMC_RELEASE_AUDIT_QUALIFICATION_LINK", label)
    tests = _test_summary(qualification)
    require(tests["tests"] == expected_tests and tests["unexpected"] == 0,
            "MMC_RELEASE_AUDIT_TEST_DENOMINATOR", label)
    installed = verification.get("installed", {})
    require(installed.get("all_wheel_members_verified") is True
            and installed.get("conformance_cases") == 78,
            "MMC_RELEASE_AUDIT_INSTALLED", label)
    evidence = qualification.get("evidence_scope", {})
    require(evidence.get("external_closure") == "COMPLETE",
            "MMC_RELEASE_AUDIT_EVIDENCE_SCOPE", label)
    return {
        "platform": label,
        **tests,
        "qualification_root": qualification["receipt_root"],
        "release_verification_root": verification["receipt_root"],
        "qualified_source_archive_sha256": verification["source_archive"]["sha256"],
        "wheel_sha256": verification["wheel"]["sha256"],
        "installed_migration_root": installed["migration_receipt_root"],
        "installed_target_migration_root": installed["target_migration_receipt_root"],
        "evidence_scope_profile_root": evidence["profile_root"],
        "claim_map_root": evidence["claim_map_root"],
    }


def build_audit(*, release_dir: Path, windows_verification: Path,
                windows_qualification: Path, linux_verification: Path,
                linux_qualification: Path, public_ci: Path,
                expected_source: str) -> dict:
    release_dir = release_dir.resolve()
    require({path.name for path in release_dir.iterdir()} == CORE_FILES,
            "MMC_RELEASE_AUDIT_CORE_CLOSURE")
    sums = _checksums(release_dir / "SHA256SUMS")
    require(set(sums) == CORE_FILES - {"SHA256SUMS"}, "MMC_RELEASE_AUDIT_CHECKSUM_CLOSURE")
    for name, digest in sums.items():
        require(_sha(release_dir / name) == digest, "MMC_RELEASE_AUDIT_CHECKSUM", name)
    release = _load(release_dir / "MMC-v0.1-release.json")
    index = _load(release_dir / "MMC-v0.1-qualification-index.json")
    require(_rooted(release, "root") and _rooted(release["release_identity"], "root")
            and _rooted(index, "root"), "MMC_RELEASE_AUDIT_PUBLIC_ROOT")
    require(index.get("source_root") == expected_source
            and release["qualification_index"]["root"] == index["root"]
            and release["qualification_index"]["sha256"] ==
                _sha(release_dir / "MMC-v0.1-qualification-index.json"),
            "MMC_RELEASE_AUDIT_INDEX_LINK")
    artifacts = {row["artifact"]: row for row in release.get("artifacts", [])}
    require(set(artifacts) == {"MMC_SOURCE", "MMC_RUNTIME"}, "MMC_RELEASE_AUDIT_ARTIFACTS")
    for row in artifacts.values():
        path = release_dir / row["path"]
        require(path.is_file() and path.stat().st_size == row["bytes"] and _sha(path) == row["sha256"],
                "MMC_RELEASE_AUDIT_ARTIFACT", row["path"])
        require(row.get("certificate_status") == "PASS_DKN_SELF_CERTIFIED",
                "MMC_RELEASE_AUDIT_DKN", row["path"])
    registry = _load(ROOT / "provenance/turn7/TEST-REGISTRY.json")
    expected_tests = sum(len(values) for values in registry["groups"].values())
    windows = _platform("Windows", _load(windows_verification),
                        _load(windows_qualification), expected_source, expected_tests)
    linux = _platform("Linux", _load(linux_verification),
                      _load(linux_qualification), expected_source, expected_tests)
    ci = _load(public_ci)
    require(ci.get("status") == "PASS_WITH_DECLARED_NONPASSES"
            and ci.get("source_after") == ci.get("plan", {}).get("source_root") == expected_source
            and ci.get("unexpected") == [], "MMC_RELEASE_AUDIT_PUBLIC_CI")
    body = {
        "schema": "mosaic.mmc.release-audit.v0.1",
        "status": "PASS_ALPHA_CANDIDATE_WITH_DISCLOSED_LIMITATIONS",
        "authority_effect": "NONE",
        "candidate": {
            "engineering_revision": release["engineering_revision"],
            "source_root": expected_source,
            "test_denominator": expected_tests,
            "wheel_sha256": windows["wheel_sha256"],
        },
        "platform_qualification": {"windows": windows, "linux": linux},
        "public_ci": {
            "status": ci["status"], "plan_root": ci["plan"]["plan_root"],
            "tests": sum(ci["counts"].values()),
            "admitted_nonpasses": ci["admitted_nonpasses"],
            "source_pin_origin": ci["source_pin_origin"],
        },
        "public_release": {
            "release_root": release["root"],
            "release_identity_root": release["release_identity"]["root"],
            "source_manifest_root": release["source_manifest"]["root"],
            "source_archive_sha256": artifacts["MMC_SOURCE"]["sha256"],
            "runtime_archive_sha256": artifacts["MMC_RUNTIME"]["sha256"],
            "source_certificate_root": artifacts["MMC_SOURCE"]["certificate_root"],
            "runtime_certificate_root": artifacts["MMC_RUNTIME"]["certificate_root"],
            "certificate_status": "PASS_DKN_SELF_CERTIFIED",
        },
        "disclosed_limits": {
            "windows_host_limitations": windows["host_limitations"],
            "linux_host_limitations": linux["host_limitations"],
            "macos": "NOT_EXECUTED_NO_MAC_AVAILABLE",
            "independent_security_review": "NOT_PERFORMED_FOR_RELEASE_CONVERGENCE_R013",
            "production_adapter_and_identity": "NOT_QUALIFIED",
            "dkn_asset_certification": "PASS_DKN_SELF_CERTIFIED",
            "publication_performed": False,
        },
        "publication_performed": False,
    }
    return {**body, "audit_root": hashlib.sha256(canonical(body)).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--windows-verification", type=Path, required=True)
    parser.add_argument("--windows-qualification", type=Path, required=True)
    parser.add_argument("--linux-verification", type=Path, required=True)
    parser.add_argument("--linux-qualification", type=Path, required=True)
    parser.add_argument("--public-ci", type=Path, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "MMC_RELEASE_AUDIT_OUTPUT_EXISTS")
    require(not args.out.resolve().is_relative_to(ROOT.resolve()), "MMC_RELEASE_AUDIT_OUTPUT_INSIDE_SOURCE")
    result = build_audit(
        release_dir=args.release_dir, windows_verification=args.windows_verification,
        windows_qualification=args.windows_qualification,
        linux_verification=args.linux_verification, linux_qualification=args.linux_qualification,
        public_ci=args.public_ci, expected_source=args.expected_source)
    args.out.write_bytes(canonical(result) + b"\n")
    print(canonical(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
