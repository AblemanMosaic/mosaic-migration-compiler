# Exact offline dependency closure

Historical profile: `windows-cpython312-amd64-qualification.v1`. This profile covers the observed
Windows x64 CPython 3.12 runtime. It does not qualify Linux, macOS, other architectures
or other Python minor versions. The CPython interpreter and Windows runtime are platform
inputs, not vendored dependencies.

This preserved twelve-wheel closure includes subsequently reported vulnerabilities and is
retained for exact historical replay. It is not admitted by current release verification.
Use an explicitly pinned current `.v2` full bundle for a current release attempt.

The source includes twelve genuine distribution wheels under `baseline/offline/wheels`,
`LOCK.json`, and a hash-required `requirements.lock`. No source distribution is admitted.
The lock binds the official PyPI release metadata URL, download URL, SHA-256, file length,
wheel identity, metadata requirements, import roots, and supplied license/notice files.
Each acquired wheel hash was checked against official PyPI release JSON. Hashes establish
artifact custody; they do not establish author approval, absence of vulnerabilities, or
license clearance.

| Distribution | Exact version | Role |
|---|---|---|
| pip | 26.0.1 | Pinned, offline installer and vendored requirement/tag parser |
| cryptography | 46.0.3 | Native statement signing and verification |
| cffi | 2.0.0 | cryptography dependency |
| pycparser | 3.0 | cffi dependency and declared UCM qualification range |
| jsonschema | 4.26.0 | Structural qualification |
| attrs | 25.4.0 | jsonschema/referencing dependency |
| jsonschema-specifications | 2025.9.1 | jsonschema dependency |
| referencing | 0.37.0 | jsonschema dependency |
| rpds-py | 0.30.0 | jsonschema/referencing dependency |
| typing-extensions | 4.15.0 | Active referencing dependency on Python 3.12 |
| blake3 | 1.0.7 | Declared UCM qualification dependency |
| PyYAML | 6.0.2 | Declared UCM qualification dependency |

`tools_t7/dependencies.py` is the repository-native verifier, installer command generator,
and installed observer. Its bootstrap is standard-library-only. It verifies the embedded
lock root, exact file set, every wheel hash, wheel `RECORD` closure, package identities,
wheel tags, `Requires-Python`, active PEP 508 markers and transitive requirement edges.
PEP interpretation uses only packaging vendored in the verified pip wheel in isolated
Python with `-I -S`: installed `.pth` files and `sitecustomize` are not loaded
before verification. It never imports an ambient pip or packaging installation.

`installation_command(target_python, source_root)` emits a bounded argument list that
rehashes all locked inputs before importing pip from the bundled wheel. The target must
be a fresh venv created with `--without-pip`, without system-site packages. Installation
starts with `-I -S`, derives the venv from its executable and `pyvenv.cfg`, and refuses
a nonempty site-packages directory before importing the hash-verified pip wheel. On
CPython 3.12 it restores the venv prefix directly, without importing `site`. Installation
uses `--isolated --no-index --only-binary=:all: --require-hashes --ignore-installed
--no-compile`. Both installer code and application dependencies are supplied offline.
No dependency resolution or wheel build requires network access at verification time.
The runner invokes the bootstrap directly as an argument list; no shell parses its code.

`observation_command(target_python, source_root)` verifies an exact twelve-distribution
environment, all immutable wheel members, and every import origin inside that venv's
site-packages. The observer also starts with `-I -S` and adds site-packages to the import
path only after the complete file set and immutable hashes have passed. Direct calls from
an interpreter with `site` already enabled are refused. It rejects duplicate distribution
identities and undeclared files, including
`.pth`, Python/native modules and bytecode. Only constrained pip-generated metadata is
admitted. `RECORD` is mutable installation metadata, never its own integrity proof. When
MMC is installed, pass both `allow_mmc_version` and `mmc_wheel`; the observer then verifies
the MMC wheel members and the complete combined site-packages file set. Install MMC with
`--no-compile` and run qualification/installed commands with bytecode writes disabled.

These are owned, newly created local environments. File verification is an integrity
observation, not an operating-system sandbox against a hostile process or administrator.
The release verifier records the closure and installed receipts separately from migration
and integration receipts.

Useful commands:

```text
python -B tools_t7/dependencies.py
TARGET_PYTHON -I -S -B tools_t7/dependencies.py --root SOURCE_ROOT --observe-installed
```

`--author-lock` is a separately explicit network acquisition command for maintainers.
It reads official PyPI release JSON and authors the lock for the listed pins. A changed
lock requires review and an explicit successor update to the embedded `LOCK_ROOT`; a
self-rehashed file is not admitted automatically. No runtime verification command renews
or repairs a mismatching lock.

License expressions/classifiers and exact license-file hashes are inventoried without
changing their standing. Redistribution/legal review and vulnerability review remain
separate release gates. This closure covers the selected MMC and UCM/SemCrys probe and
qualification dependencies; it does not install every optional upstream feature extra.

Full native profiles and handoffs are described in [platform qualification](PLATFORM-QUALIFICATION.md).
They use explicit external `--dependency-bundle` and independently retained
`--dependency-lock-root` arguments. Qualification never selects a trust root from environment.
Current `.v2` full profiles pin pip 26.3, cryptography 50.0.2 and Pillow 13.0.0, retaining
the other ten pins. The exact dated OSV request/response snapshot is part of each lock and
must verify offline with no matched advisories for those exact versions. This is a dated
query disposition, not blanket security clearance or an automatic age policy. `author-lock`
performs the explicit network scan; qualification never repairs or refreshes that evidence.
Current acquisition obtains the patched pip wheel using only the standard library and checks
official PyPI metadata plus its independently embedded SHA-256 before import. Mac Intel lacks
a patched upstream cryptography wheel and remains explicitly blocked. Safe zero-byte ZIP directory
entries are checked as directories and excluded from the RECORD file set. Dependency files
and members are bounded at 32 MiB to accommodate the 21.4 MB universal2 cryptography extension;
the 64 MiB expanded-wheel limit and exact file/hash closure remain enforced.
