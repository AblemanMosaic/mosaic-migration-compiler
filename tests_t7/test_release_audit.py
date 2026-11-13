from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from mosaic_mmc import canonical
from mosaic_mmc.errors import MMCError
from tools.common import ROOT, source_snapshot
from tools_t7.release_audit import CORE_FILES, build_audit


def rooted(body: dict, field: str = "root") -> dict:
    return {**body, field: hashlib.sha256(canonical(body)).hexdigest()}


class ReleaseAuditTests(unittest.TestCase):
    def fixture(self, directory: Path) -> dict:
        source = source_snapshot(ROOT)["root"]
        index = rooted({"schema": "mosaic.mmc.qualification-index.v0.1",
                        "source_root": source, "authority_effect": "NONE"})
        index_raw = canonical(index) + b"\n"
        (directory / "MMC-v0.1-qualification-index.json").write_bytes(index_raw)
        artifacts = []
        for artifact, name in (("MMC_SOURCE", "MMC-v0.1-source.zip"),
                               ("MMC_RUNTIME", "MMC-v0.1-runtime.zip")):
            raw = artifact.encode()
            (directory / name).write_bytes(raw)
            artifacts.append({"artifact": artifact, "path": name, "bytes": len(raw),
                              "sha256": hashlib.sha256(raw).hexdigest(),
                              "certificate_status": "PASS_DKN_SELF_CERTIFIED",
                              "certificate_root": artifact.lower().ljust(64, "0")})
        identity = rooted({"schema": "mosaic.mmc.public-release-identity.v0.1",
                           "source_manifest_root": "1" * 64})
        release = rooted({"schema": "mosaic.mmc.public-release.v0.1",
                          "engineering_revision": "r013", "release_identity": identity,
                          "source_manifest": {"root": "1" * 64}, "artifacts": artifacts,
                          "qualification_index": {"root": index["root"],
                              "sha256": hashlib.sha256(index_raw).hexdigest(),
                              "source_root": source}})
        (directory / "MMC-v0.1-release.json").write_bytes(canonical(release) + b"\n")
        names = CORE_FILES - {"SHA256SUMS"}
        (directory / "SHA256SUMS").write_text("".join(
            f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}\n"
            for name in sorted(names)), encoding="ascii")
        registry = json.loads((ROOT / "provenance/turn7/TEST-REGISTRY.json").read_text())
        denominator = sum(len(values) for values in registry["groups"].values())
        outcomes = {f"test.{index}": "PASS" for index in range(denominator)}
        qualification = rooted({
            "status": "PASS_CURRENT_SUCCESSOR_WITH_DECLARED_HOST_AND_LEGACY_LIMITATIONS",
            "source_root": source,
            "tests": {"all": {"test_outcomes": outcomes, "unexpected": []}},
            "host_limitations": [], "successor_superseded_assertions": [],
            "evidence_scope": {"external_closure": "COMPLETE", "profile_root": "2" * 64,
                               "claim_map_root": "3" * 64},
        }, "receipt_root")
        verification = rooted({
            "status": "PASS_SCOPED_ALPHA_CANDIDATE", "platform": "Windows",
            "stage_i1_verified": True, "source_root": source,
            "qualification_root": qualification["receipt_root"],
            "source_archive": {"sha256": "4" * 64}, "wheel": {"sha256": "5" * 64},
            "installed": {"all_wheel_members_verified": True, "conformance_cases": 78,
                          "migration_receipt_root": "6" * 64,
                          "target_migration_receipt_root": "7" * 64},
        }, "receipt_root")
        ci = {"status": "PASS_WITH_DECLARED_NONPASSES", "source_after": source,
              "plan": {"source_root": source, "plan_root": "8" * 64}, "unexpected": [],
              "counts": {"PASS": 1, "SKIP": 1}, "admitted_nonpasses": ["test.skip"],
              "source_pin_origin": "SELF_OBSERVED_DIAGNOSTIC"}
        paths = {}
        for name, value in (("windows-q.json", qualification), ("linux-q.json", qualification),
                            ("windows-v.json", verification), ("ci.json", ci)):
            path = directory.parent / name; path.write_bytes(canonical(value) + b"\n"); paths[name] = path
        linux = {**verification, "platform": "Linux"}
        linux = rooted({key: value for key, value in linux.items() if key != "receipt_root"}, "receipt_root")
        paths["linux-v.json"] = directory.parent / "linux-v.json"
        paths["linux-v.json"].write_bytes(canonical(linux) + b"\n")
        return {"source": source, "paths": paths}

    def test_exact_release_and_platform_records_build_rooted_audit(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary:
            root = Path(temporary); release = root / "release"; release.mkdir()
            fixture = self.fixture(release); paths = fixture["paths"]
            result = build_audit(
                release_dir=release, windows_verification=paths["windows-v.json"],
                windows_qualification=paths["windows-q.json"],
                linux_verification=paths["linux-v.json"], linux_qualification=paths["linux-q.json"],
                public_ci=paths["ci.json"], expected_source=fixture["source"])
            self.assertEqual(result["status"], "PASS_ALPHA_CANDIDATE_WITH_DISCLOSED_LIMITATIONS")
            registry = json.loads((ROOT / "provenance" / "turn7" / "TEST-REGISTRY.json").read_text(encoding="utf-8"))
            expected_denominator = sum(len(values) for values in registry["groups"].values())
            self.assertEqual(result["candidate"]["test_denominator"], expected_denominator)
            self.assertEqual(result["disclosed_limits"]["macos"], "NOT_EXECUTED_NO_MAC_AVAILABLE")
            self.assertEqual(result["audit_root"], hashlib.sha256(canonical(
                {key: value for key, value in result.items() if key != "audit_root"})).hexdigest())

    def test_substituted_platform_source_refuses(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary:
            root = Path(temporary); release = root / "release"; release.mkdir()
            fixture = self.fixture(release); paths = fixture["paths"]
            with self.assertRaises(MMCError) as caught:
                build_audit(
                    release_dir=release, windows_verification=paths["windows-v.json"],
                    windows_qualification=paths["windows-q.json"],
                    linux_verification=paths["linux-v.json"], linux_qualification=paths["linux-q.json"],
                    public_ci=paths["ci.json"], expected_source="f" * 64)
            self.assertEqual(caught.exception.code, "MMC_RELEASE_AUDIT_INDEX_LINK")
