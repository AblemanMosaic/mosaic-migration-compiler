"""MMC release-content commitments and DKN self-certification metadata.

The embedded records describe logical archive contents.  The SHA-256 of the
complete ZIP remains an external transport commitment so no record attempts to
contain the hash of the bytes that contain that record.

This module is an MMC specialization of the Apache-2.0-licensed UCM r036
release-certification implementation.  The DKN records remain public material;
private signing keys are accepted only as ephemeral in-memory objects by callers.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Iterable


BOUNDARY = {"standing": "INFORMATION_ONLY", "authority_effect": "NONE",
            "real_a5": False, "g0": "CLOSED"}
META_NAMES = (
    "META/STATE-MANIFEST.json",
    "META/DKN-BINDING.json",
    "META/THR-MANIFEST.json",
    "META/SELF-CERTIFICATE.json",
)


class ReleaseCertificationRefusal(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReleaseCertificationRefusal(code)


def _sha(value: Any, code: str) -> str:
    _require(isinstance(value, str) and len(value) == 64, code)
    try:
        bytes.fromhex(value)
    except ValueError as error:
        raise ReleaseCertificationRefusal(code) from error
    return value


def _rows(payload_rows: Iterable[tuple[str, bytes]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, data in sorted(payload_rows):
        _require(isinstance(path, str) and path and not path.startswith("META/")
                 and path != "MANIFEST.json" and "\\" not in path,
                 "RELEASE_CERTIFICATION_PAYLOAD_PATH_INVALID")
        _require(path.casefold() not in seen and isinstance(data, bytes),
                 "RELEASE_CERTIFICATION_PAYLOAD_INVALID")
        seen.add(path.casefold())
        rows.append({"path": path, "sha256": hashlib.sha256(data).hexdigest(),
                     "bytes": len(data)})
    _require(bool(rows), "RELEASE_CERTIFICATION_PAYLOAD_EMPTY")
    return rows


def build_dkn_binding(*, public_namespace: str,
                      authority_public_key_hex: str | None = None,
                      namespace_id: str | None = None,
                      namespace_binding_hash: str | None = None,
                      passport_root: str | None = None) -> dict[str, Any]:
    _require(isinstance(public_namespace, str) and public_namespace.strip()
             == public_namespace
             and re.fullmatch(r"[a-z0-9](?:[a-z0-9._-]{0,253}[a-z0-9])?",
                              public_namespace) is not None,
             "RELEASE_DKN_NAMESPACE_INVALID")
    supplied = [authority_public_key_hex, namespace_id,
                namespace_binding_hash, passport_root]
    if all(value is None for value in supplied):
        status = "DECLARED_UNBOUND"
    else:
        _require(all(value is not None for value in supplied),
                 "RELEASE_DKN_BINDING_INCOMPLETE")
        _require(isinstance(namespace_id, str)
                 and namespace_id.startswith("dkn:v0.1:b3:")
                 and len(namespace_id) == len("dkn:v0.1:b3:") + 64,
                 "RELEASE_DKN_NAMESPACE_ID_INVALID")
        _sha(namespace_id.removeprefix("dkn:v0.1:b3:"),
             "RELEASE_DKN_NAMESPACE_ID_INVALID")
        _sha(namespace_binding_hash, "RELEASE_DKN_NAMESPACE_BINDING_INVALID")
        _sha(passport_root, "RELEASE_DKN_PASSPORT_ROOT_INVALID")
        _require(isinstance(authority_public_key_hex, str)
                 and len(authority_public_key_hex) == 64,
                 "RELEASE_DKN_PUBLIC_KEY_INVALID")
        try:
            key = bytes.fromhex(authority_public_key_hex)
        except ValueError as error:
            raise ReleaseCertificationRefusal("RELEASE_DKN_PUBLIC_KEY_INVALID") from error
        _require(len(key) == 32, "RELEASE_DKN_PUBLIC_KEY_INVALID")
        status = "BOUND_DKN_CORE_V0_1"
    body = {
        "schema": "mosaic.mmc.release-dkn-binding.v0.1",
        "public_namespace": public_namespace,
        "status": status,
        "authority_public_key_hex": authority_public_key_hex,
        "namespace_id": namespace_id,
        "namespace_binding_hash": namespace_binding_hash,
        "passport_root": passport_root,
        "permission_granted": False,
        "non_claims": ["IDENTITY_IS_NOT_AUTHORITY", "LOCATION_IS_NOT_IDENTITY"],
        **BOUNDARY,
    }
    return {**body, "dkn_binding_root": root(body)}


def build_embedded_metadata(*, payload_rows: Iterable[tuple[str, bytes]],
                            artifact: str, completeness: str,
                            version: str, engineering_revision: str,
                            source_manifest_root: str,
                            release_identity_root: str,
                            publisher: str = "Adam Mazurk",
                            public_namespace: str = "mosaic.migration-compilation.v0.1",
                            dkn_binding: dict[str, Any] | None = None,
                            signature_hex: str | None = None) -> dict[str, bytes]:
    state_rows = _rows(payload_rows)
    _sha(source_manifest_root, "RELEASE_SOURCE_MANIFEST_ROOT_INVALID")
    _sha(release_identity_root, "RELEASE_IDENTITY_ROOT_INVALID")
    _require(version == "v0.1" and isinstance(engineering_revision, str)
             and len(engineering_revision) == 4
             and engineering_revision.startswith("r")
             and engineering_revision[1:].isdigit(),
             "RELEASE_VERSION_IDENTITY_INVALID")
    state_body = {
        "schema": "mosaic.mmc.release-state-manifest.v0.1",
        "artifact": artifact, "version": version,
        "engineering_revision": engineering_revision,
        "members": state_rows, "member_count": len(state_rows),
        "logical_bytes": sum(row["bytes"] for row in state_rows),
        "scope": "LOGICAL_PAYLOAD_EXCLUDING_META_AND_TRANSPORT_CONTAINER",
        **BOUNDARY,
    }
    state = {**state_body, "state_root": root(state_body)}
    dkn = deepcopy(dkn_binding) if dkn_binding is not None else build_dkn_binding(
        public_namespace=public_namespace)
    validate_dkn_binding(dkn)
    meaning = {
        "schema": "mosaic.mmc.thr.meaning.v0.1", "product": "Mosaic Migration Compiler",
        "artifact_role": artifact, "completeness": completeness,
        "version": version, "engineering_revision": engineering_revision,
        "publisher": publisher,
    }
    admissibility = {
        "schema": "mosaic.mmc.thr.admissibility.v0.1",
        "source_manifest_root": source_manifest_root,
        "release_identity_root": release_identity_root,
        "authority_ceiling": deepcopy(BOUNDARY),
        "publication_requires_explicit_human_authorization": True,
    }
    locality = {
        "schema": "mosaic.mmc.thr.locality.v0.1",
        "dkn_binding_root": dkn["dkn_binding_root"],
        "public_namespace": dkn["public_namespace"],
        "dkn_status": dkn["status"], "storage_location": "UNBOUND",
    }
    receipts = {
        "schema": "mosaic.mmc.thr.receipt-identity.v0.1",
        "qualification_receipt": "EXTERNAL_TRANSPORT_BOUND_RECEIPT",
        "operator_tier1_evidence": "EXTERNAL_EXACT_ARTIFACT_EVIDENCE",
        "self_certificate_status": ("PENDING_DKN_BINDING" if dkn["status"] == "DECLARED_UNBOUND"
                                    else "PENDING_SIGNATURE"),
    }
    state_section = {
        "schema": "mosaic.mmc.thr.state.v0.1", "state_root": state["state_root"],
        "member_count": state["member_count"], "logical_bytes": state["logical_bytes"],
    }
    commitments = {"H_s": root(state_section), "H_c": root(admissibility),
                   "H_m": root(meaning), "H_j": root(locality), "H_r": root(receipts)}
    thr_body = {
        "schema": "mosaic.mmc.release-thr-manifest.v0.1",
        "artifact": artifact,
        "semantic_mapping": {"H_s": "state", "H_c": "admissibility",
                             "H_m": "meaning", "H_j": "locality",
                             "H_r": "receipt_identity", "h_body": "whole_body_integrity"},
        "state": state_section, "admissibility": admissibility,
        "meaning": meaning, "locality": locality,
        "receipt_identity": receipts, "commitments": commitments, **BOUNDARY,
    }
    thr = {**thr_body, "h_body": root(thr_body)}
    signing_body = {
        "schema": "mosaic.mmc.release-self-certificate-signing-body.v0.1",
        "artifact": artifact, "version": version,
        "engineering_revision": engineering_revision,
        "state_root": state["state_root"], "thr_body_root": thr["h_body"],
        "dkn_binding_root": dkn["dkn_binding_root"],
        "source_manifest_root": source_manifest_root,
        "release_identity_root": release_identity_root,
    }
    if dkn["status"] == "DECLARED_UNBOUND":
        _require(signature_hex is None, "RELEASE_SELF_CERTIFICATE_UNBOUND_SIGNATURE_REFUSED")
        cert_status = "READY_FOR_EXTERNAL_DKN_CERTIFICATION"
        signature_suite = None
    else:
        if signature_hex is None:
            cert_status = "READY_FOR_DKN_SIGNATURE"
            signature_suite = None
        else:
            _require(isinstance(signature_hex, str) and len(signature_hex) == 128,
                     "RELEASE_SELF_CERTIFICATE_SIGNATURE_REQUIRED")
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(dkn["authority_public_key_hex"])).verify(
                        bytes.fromhex(signature_hex), canonical(signing_body))
            except Exception as error:
                raise ReleaseCertificationRefusal("RELEASE_SELF_CERTIFICATE_SIGNATURE_INVALID") from error
            cert_status = "PASS_DKN_SELF_CERTIFIED"
            signature_suite = "ED25519_CANONICAL_JSON_V1"
    cert_body = {
        **signing_body, "certificate_status": cert_status,
        "signature_suite": signature_suite, "signature_hex": signature_hex,
        "transport_sha256_scope": "EXTERNAL_COMPLETE_ARCHIVE_BYTES",
        "storage_location_bound": False,
        "non_claims": ["SELF_CERTIFICATION_IS_NOT_PUBLICATION_AUTHORITY",
                       "SELF_CERTIFICATION_IS_NOT_INDEPENDENT_REVIEW"],
        **BOUNDARY,
    }
    certificate = {**cert_body, "certificate_root": root(cert_body)}
    return {
        META_NAMES[0]: canonical(state) + b"\n",
        META_NAMES[1]: canonical(dkn) + b"\n",
        META_NAMES[2]: canonical(thr) + b"\n",
        META_NAMES[3]: canonical(certificate) + b"\n",
    }


def validate_dkn_binding(value: Any) -> dict[str, Any]:
    _require(isinstance(value, dict), "RELEASE_DKN_BINDING_INVALID")
    body = {key: deepcopy(row) for key, row in value.items()
            if key != "dkn_binding_root"}
    _require(value.get("dkn_binding_root") == root(body), "RELEASE_DKN_BINDING_INVALID")
    expected = build_dkn_binding(
        public_namespace=value.get("public_namespace"),
        authority_public_key_hex=value.get("authority_public_key_hex"),
        namespace_id=value.get("namespace_id"),
        namespace_binding_hash=value.get("namespace_binding_hash"),
        passport_root=value.get("passport_root"))
    _require(value == expected, "RELEASE_DKN_BINDING_INVALID")
    return deepcopy(value)


def certificate_signing_body(metadata: dict[str, bytes]) -> dict[str, Any]:
    """Return the exact Ed25519 preimage object without accepting caller fields."""
    _require(set(metadata) == set(META_NAMES), "RELEASE_CERTIFICATION_META_SET_INVALID")
    certificate = json.loads(metadata[META_NAMES[3]])
    keys = (
        "schema", "artifact", "version", "engineering_revision", "state_root",
        "thr_body_root", "dkn_binding_root", "source_manifest_root",
        "release_identity_root",
    )
    body = {key: certificate.get(key) for key in keys}
    _require(all(value is not None for value in body.values()),
             "RELEASE_SELF_CERTIFICATE_SIGNING_BODY_INVALID")
    return body


def verify_embedded_metadata(*, payload_rows: Iterable[tuple[str, bytes]],
                             metadata: dict[str, bytes], artifact: str,
                             completeness: str, version: str,
                             engineering_revision: str,
                             source_manifest_root: str,
                             release_identity_root: str) -> dict[str, Any]:
    _require(set(metadata) == set(META_NAMES), "RELEASE_CERTIFICATION_META_SET_INVALID")
    parsed = {name: json.loads(metadata[name]) for name in META_NAMES}
    dkn = validate_dkn_binding(parsed[META_NAMES[1]])
    expected = build_embedded_metadata(
        payload_rows=payload_rows, artifact=artifact, completeness=completeness,
        version=version, engineering_revision=engineering_revision,
        source_manifest_root=source_manifest_root,
        release_identity_root=release_identity_root,
        dkn_binding=dkn,
        signature_hex=parsed[META_NAMES[3]].get("signature_hex"))
    _require(metadata == expected, "RELEASE_CERTIFICATION_META_INVALID")
    return {
        "status": "PASS", "state_root": parsed[META_NAMES[0]]["state_root"],
        "thr_body_root": parsed[META_NAMES[2]]["h_body"],
        "dkn_binding_root": dkn["dkn_binding_root"],
        "dkn_status": dkn["status"],
        "certificate_root": parsed[META_NAMES[3]]["certificate_root"],
        "certificate_status": parsed[META_NAMES[3]]["certificate_status"],
        **BOUNDARY,
    }


__all__ = ["META_NAMES", "ReleaseCertificationRefusal", "build_dkn_binding",
           "build_embedded_metadata", "validate_dkn_binding",
           "certificate_signing_body", "verify_embedded_metadata"]
