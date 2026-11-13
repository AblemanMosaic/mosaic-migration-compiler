from __future__ import annotations

from argparse import Namespace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from mosaic_mmc_product.release_certification import (
    META_NAMES,
    ReleaseCertificationRefusal,
    build_dkn_binding,
    build_embedded_metadata,
    canonical,
    certificate_signing_body,
    verify_embedded_metadata,
)
from mosaic_mmc import MMCError
from tools_t7.publication_projection import audit_filesystem
from tools_t7.public_release import build as build_public_release, source_rows, write_archive
from tools_t7.package import build_wheel
from tools_t7 import build_backend


class PublicReleaseCertificationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [("LICENSE", b"license\n"), ("src/example.py", b"VALUE = 1\n")]
        self.args = {
            "payload_rows": self.rows,
            "artifact": "MMC_SOURCE",
            "completeness": "COMPLETE_PUBLIC_SOURCE_PRIVATE_HISTORY_AND_THIRD_PARTY_BINARIES_EXCLUDED",
            "version": "v0.1",
            "engineering_revision": "r013",
            "source_manifest_root": "1" * 64,
            "release_identity_root": "2" * 64,
        }

    def test_unbound_archive_is_explicitly_not_self_certified(self):
        metadata = build_embedded_metadata(**self.args)
        result = verify_embedded_metadata(metadata=metadata, **self.args)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["dkn_status"], "DECLARED_UNBOUND")
        self.assertEqual(result["certificate_status"],
                         "READY_FOR_EXTERNAL_DKN_CERTIFICATION")

    def test_bound_archive_requires_and_verifies_dkn_signature(self):
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        binding = build_dkn_binding(
            public_namespace="mosaic.migration-compilation.v0.1",
            authority_public_key_hex=public,
            namespace_id="dkn:v0.1:b3:" + "3" * 64,
            namespace_binding_hash="4" * 64,
            passport_root="5" * 64,
        )
        pending = build_embedded_metadata(**self.args, dkn_binding=binding)
        self.assertEqual(json.loads(pending[META_NAMES[3]])["certificate_status"],
                         "READY_FOR_DKN_SIGNATURE")
        signature = key.sign(canonical(certificate_signing_body(pending))).hex()
        signed = build_embedded_metadata(
            **self.args, dkn_binding=binding, signature_hex=signature)
        result = verify_embedded_metadata(metadata=signed, **self.args)
        self.assertEqual(result["certificate_status"], "PASS_DKN_SELF_CERTIFIED")

    def test_payload_tamper_refuses(self):
        metadata = build_embedded_metadata(**self.args)
        changed = {**self.args, "payload_rows": [("LICENSE", b"changed\n"),
                                                  ("src/example.py", b"VALUE = 1\n")]}
        with self.assertRaises(ReleaseCertificationRefusal):
            verify_embedded_metadata(metadata=metadata, **changed)

    def test_partial_dkn_binding_refuses(self):
        with self.assertRaisesRegex(ReleaseCertificationRefusal,
                                    "RELEASE_DKN_BINDING_INCOMPLETE"):
            build_dkn_binding(
                public_namespace="mosaic.migration-compilation.v0.1",
                authority_public_key_hex="0" * 64,
            )

    def test_public_filesystem_projection_is_closed(self):
        result = audit_filesystem(Path(__file__).resolve().parents[1])
        self.assertEqual(result["schema"], "mosaic.mmc.public-filesystem-projection.v0.1")
        self.assertGreater(len(result["files"]), 400)
        self.assertIn("FILE-MANIFEST.json", {path for path, _ in source_rows()})

    def test_public_projection_refuses_private_custody_directory(self):
        with tempfile.TemporaryDirectory(prefix="mmc-public-projection-",
                                         dir=Path(__file__).resolve().parents[2]) as directory:
            path = Path(directory) / "baseline"
            path.mkdir()
            (path / "private.zip").write_bytes(b"private")
            with self.assertRaisesRegex(MMCError, "MMC_PUBLIC_PRIVATE_CUSTODY"):
                audit_filesystem(Path(directory))

    def test_outer_archives_are_stored_and_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments = {
                "artifact": "MMC_SOURCE",
                "completeness": "TEST_COMPLETE",
                "rows": [("LICENSE", b"license\n"), ("src/example.py", b"VALUE = 1\n")],
                "source_manifest_root": "1" * 64,
                "release_identity_root": "2" * 64,
                "dkn_binding": None,
                "private_key": None,
            }
            first = root / "first.zip"
            second = root / "second.zip"
            write_archive(first, **arguments)
            write_archive(second, **arguments)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertTrue(all(row.compress_type == zipfile.ZIP_STORED
                                    for row in archive.infolist()))

    def test_pep517_backend_emits_canonical_wheel_and_metadata_24(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            name = build_backend.build_wheel(root)
            self.assertEqual((root / name).read_bytes(), build_wheel())
            metadata = root / "metadata"
            dist_info = build_backend.prepare_metadata_for_build_wheel(metadata)
            text = (metadata / dist_info / "METADATA").read_text(encoding="utf-8")
            self.assertIn("Metadata-Version: 2.4\n", text)
            self.assertIn("Summary: Migration compiler, bounded controller, agent workflows, and explicit integration conformance\n", text)
            self.assertIn("License-File: licenses/LICENSE\n", text)
            self.assertIn("License-File: licenses/NOTICE\n", text)

    def test_release_checksums_cover_manifest_index_and_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "release"
            build_public_release(Namespace(
                output=output, namespace=None, passport=None, private_key=None))
            rows = [line.split("  ", 1) for line in
                    (output / "SHA256SUMS").read_text(encoding="ascii").splitlines()]
            self.assertEqual([name for _, name in rows], [
                "MMC-v0.1-release.json",
                "MMC-v0.1-qualification-index.json",
                "MMC-v0.1-source.zip",
                "MMC-v0.1-runtime.zip",
            ])
            for expected, name in rows:
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
