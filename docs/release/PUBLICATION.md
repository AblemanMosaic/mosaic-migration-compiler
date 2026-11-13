# Public release and GitHub publication

MMC public version `v0.1` is licensed under Apache-2.0. The Python distribution
identifier for this exact release is `0.1.0a9`. Every publicly distributed changed wheel receives
a distinct Python distribution version even while the public product version remains `v0.1`.
The version distinguishes normal package identities; exact hashes and signed manifests distinguish
the complete artifact bytes.

## Namespace and release commitments

The release namespace is `mosaic.migration-compilation.v0.1`. A certified release
contains four embedded records:

- `META/STATE-MANIFEST.json` inventories every logical payload byte, excluding
  `META/` and the container manifest.
- `META/THR-MANIFEST.json` preserves separate `H_s`, `H_c`, `H_m`, `H_j`, and
  `H_r` commitments and computes `h_body` over the complete THR record.
- `META/DKN-BINDING.json` binds the public namespace, DKN public key, namespace
  binding, and public passport without treating identity as authority.
- `META/SELF-CERTIFICATE.json` signs the state/THR/DKN/release-identity tuple with
  Ed25519. A passing signature proves publisher provenance, not correctness,
  operational permission, or independent review.

The SHA-256 of the complete archive is external because an archive cannot contain its
own final transport digest. GitHub URLs and release locations are replaceable custody
projections and are not semantic identity.

Outer public archives use uncompressed `ZIP_STORED` members with fixed ordering, timestamps,
permissions and paths. Their byte hashes therefore do not depend on a particular zlib build.
`SHA256SUMS` covers the release manifest, qualification index, source archive and runtime archive.
The checksum file is corruption evidence only until accepted through an independent trust anchor
or a completed DKN publisher-key ceremony.

## Publisher-key boundary

Create or select the publisher key through DKN's encrypted key ceremony. Keep the
encrypted private key and passphrase outside the repository, portable archives, logs,
and command-line arguments. The public passport and namespace record may be published.
The release builder refuses partial DKN bindings and refuses to label an unsigned
archive as self-certified.

## GitHub release shape

Commit the source tree, `LICENSE`, `NOTICE`, and `THIRD-PARTY-NOTICES.md`. Publish
large wheels, offline dependency closures, qualification evidence, and developer kits
as separately licensed release assets when redistribution is authorized. Do not commit generated
archives, raw private evidence, private conversations, or signing material. See
[external qualification inputs](QUALIFICATION-INPUTS.md).
The public source archive carries every committed source byte, including `FILE-MANIFEST.json`,
plus its separately rooted artifact metadata.
`MMC-v0.1-qualification-index.json` partitions the exact public source into runtime, fixture,
qualification, packaging, documentation, provenance, CI and source-projection roots. It permits
evidence reuse only under the policies documented in the current Release Convergence dossier; it never changes
the release archive identity or turns inherited evidence into new execution.

Before committing, run `python -B tools_t7/publication_projection.py`. After staging every file,
run it again with `--require-git`; this compares each working byte with the Git index and refuses
ignored, omitted, transformed, private-custody, or generated-binary material. Qualification and
release roots are valid only for the exact resulting Git projection.

Current qualification scope must stay explicit: Windows and Linux have executed
evidence from one physical machine; macOS ARM64 is packaged but has not been executed;
Intel macOS is outside the current patched dependency closure. The production-effect
adapter and enforced native Pippi host binding are not shipped.
