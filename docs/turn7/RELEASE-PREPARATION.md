# Release Convergence r013 release preparation

The release channel is `PUBLIC_ALPHA_V0_1`. Apache-2.0 source publication is owner-authorized;
DKN-certified downloadable assets remain pending the owner-local signing ceremony.
This revision adds authenticated local adapter process transport, a configurable adapter for
existing SQLite customer tables, and exact offline dependency installation. The original
requirements and acceptance oracles remain frozen.

## Repeatable commands

Run from the source root with supported native CPython 3.12. Current full qualification uses an
explicit `.v2` external dependency bundle on Windows x64, Linux x64 or macOS ARM64. The embedded
twelve-wheel Windows profile is preserved for historical replay and is refused for current release
verification. Acquire the current bundle through the explicit network command documented in
`PLATFORM-QUALIFICATION.md`; subsequent release verification is offline.
Obtain the root with `python -B -c "from tools.common import source_snapshot; print(source_snapshot()['root'])"`.
The registry command pins source before importing test modules, discovers the complete dynamic
test set without running test methods, and checks that discovery did not change source. A registry
update creates a new source root and requires review before qualification.

```text
QUALIFIER_PYTHON -B tools_t7/registry_refresh.py --expected-source ROOT --write
QUALIFIER_PYTHON -B tools_t7/registry_refresh.py --expected-source NEW_ROOT
python -I -S -B tools_t7/release_verify.py --preflight --expected-source NEW_ROOT --out FRESH_PREFLIGHT_DIRECTORY --ucm-source UCM_R036_ROOT --pippi-source PIPPI_R038_ROOT --semcrys-source SEMCRYS_ROOT --subject IMMUTABLE_T6_SUBJECT --dependency-bundle FULL_BUNDLE --dependency-lock-root LOCK_ROOT --cmba-a4-wheel CMBA_A4_WHEEL --cmba-a7-wheel CMBA_A7_WHEEL --dkn-rc5-wheel DKN_RC5_WHEEL
python -I -S -B tools_t7/release_verify.py --expected-source NEW_ROOT --out FRESH_DIRECTORY --ucm-source UCM_R036_ROOT --pippi-source PIPPI_R038_ROOT --semcrys-source SEMCRYS_ROOT --subject IMMUTABLE_T6_SUBJECT --dependency-bundle FULL_BUNDLE --dependency-lock-root LOCK_ROOT --cmba-a4-wheel CMBA_A4_WHEEL --cmba-a7-wheel CMBA_A7_WHEEL --dkn-rc5-wheel DKN_RC5_WHEEL
```

Registry discovery requires the complete environment declared by
`profiles/TEST-SYSTEM.json`; a dependency-free discovery is a typed refusal, never a smaller
registry. Use `tools_t7/test_runner.py --lane preflight` for bounded fail-fast iteration and the
complete release verifier for the release-qualifying `full` denominator.

`release_verify` runs full source-bound qualification, verifies exact test identities and raw
logs, recomputes exception classifications and receipt roots, verifies the UCM Stage-I1 archive,
builds source and wheel twice, installs the wheel offline, verifies installed member hashes,
and executes protocol discovery, schema export, an agent request, protocol conformance, and both
the original disposable migration and authenticated enrolled-target migration from the installed
package. Each command captures stdout, stderr, exit status and
a rooted terminal receipt. A failed attempt keeps its evidence; an existing output directory
is refused. Fresh Python cache prefixes prevent preexisting ignored bytecode from substituting
for admitted source. Separate clean qualification and installed environments receive only the
hash-locked wheels; installed dependency versions, origins and complete file closure are checked.
The exact source archive is written before tests so failed candidates retain their source.
Progress on stderr is explicitly nonsemantic and does not substitute for terminal receipts.
`QUALIFIER_PYTHON` means an already verified dependency environment for maintenance. The sealed
platform runner creates its own fresh environments, installs and observes their complete closure,
then performs registry discovery; the base interpreter needs no ambient third-party modules.
`--preflight` executes current Release Convergence tests and installed checks before the longer full run; its
`PASS_PREFLIGHT_ONLY` status is never accepted as full qualification.

The output includes an SPDX file inventory and locked dependency packages with metadata-declared
license expressions and wheel acquisition provenance. `NOASSERTION` conclusions preserve the
outstanding owner/license review; this is not vulnerability or redistribution clearance.
No publication, signing key, installation outside the disposable environment, or live migration
is part of the command.

`tools_t7/export_agent_schemas.py` checks that the installed schema graph matches the repository
schemas; `--refresh` rebuilds it deterministically. `tools_t7/renew_bindings.py --expected-source ROOT`
renews realization roots and existing implementation-bound fixtures after review. Every newly changed
predecessor path needs an explicit `--reviewed-path PATH=REASON`; unlisted changes fail the complete
preservation audit. These are mechanical binding operations and do not establish semantic equivalence
or independent approval. Recompute the source root and refresh/check the registry afterward.

## Audit repairs

- Agent malformed IDs and argument types must produce schema-valid refusals.
- Legacy worker FENCE and UPGRADE dispositions must be supported by actual declared worker state.
- The disposable write fence covers insert, update, delete, and cohort movement.
- Cutover and retirement recheck source/destination contents transactionally.
- Adapter paths and database identity are checked again for each connection.
- Unsupported compensation is refused; this adapter qualifies the cutover recovery route only.
- Concurrent and uncertain effects use atomic ledger reconciliation.
- Invalid adapter responses cannot corrupt the controller journal or imply a failed effect was absent.
- Aggregate journal admission is replay-checked in the same SQLite transaction. An unresolved
  effect retains capacity for a bounded partial/uncertain outcome and terminal reconciliation;
  capacity exhaustion refuses before adapter invocation.
- Public CI has distinct source and installed-wheel jobs. The installed job builds the exact wheel,
  installs it into a fresh environment outside the checkout, rejects source-tree module origins,
  runs protocol conformance, and performs the disposable migration lifecycle.
- Release verification reclassifies exact nonpass witnesses, rejects fabricated exemptions,
  and verifies the underlying artifacts rather than trusting aggregate labels.

## Release gates

| Gate | Current disposition | Evidence required to close |
|---|---|---|
| Local alpha engineering verification | Evaluated by release command | Exact source, tests, logs, wheel and installed run |
| Public license | CLOSED_OWNER_SELECTED_APACHE_2_0 | `LICENSE`, `NOTICE`, owner decision; dependency redistribution remains separately reviewed |
| Independent security review | Not performed | Review by a separate qualified reviewer and repair dispositions |
| Platform qualification | Windows 11 and Ubuntu 24.04 under WSL2 executed on one physical host; macOS unexecuted; Windows file-symlink privilege limitations retained | Native macOS ARM64 execution and a Windows account with file-link creation privilege |
| Native integration acceptance | Missing | Accepted native UCM integration and deployment bindings |
| Production adapter and identity | Scoped SQLite implementation; production deployment unqualified | Deployment-specific credentials, external authority and recovery drills |
| Out-of-process adapter transport | Authenticated local private-pipe transport implemented | Independent security review; remote transport is a separate future profile |
| Comparative operator study | Not performed | Isolated participants, error/supervision observations and measured effort |

Power-loss, disk-full, hostile-host and distributed exactly-once claims remain unqualified.
Same-system parallel review adds engineering coverage and does not close the independent review gate.

Revision r007 was reviewed in separate sessions without the builder transcript. The reviewed
startup and SQLite conflict-handling findings have local failing witnesses and successor
regressions. This remains same-system engineering review. Actual independent external review
requires a separately qualified reviewer and their artifact-bound disposition.

Native full qualification uses thirteen locked distributions, including Pillow for the actual
GUI screenshot. The preserved twelve-wheel Windows profile can replay its historical scope;
it does not supply the complete GUI dependency set. Use the explicit full profile and retain
all platform runner terminal records. A Windows junction test is additional coverage, not a
replacement pass for a file-symlink test that could not create its fixture.

Revision r013 retains the r008-r012 active installer/cryptography/Pillow pins at 26.3/50.0.2/13.0.0.
Every current full-profile lock includes an exact-pin, dated OSV query/response snapshot checked
offline before installation. Zero matches is an observation at the scan time, not proof that the
dependencies or host are vulnerability-free. The upstream cryptography wheel set no longer offers
a patched Intel macOS build; current Intel macOS qualification is explicitly blocked until a
suitable native wheel is separately built and admitted. No affected legacy pin is silently used.

## Institutionalization

The worker, authenticated transport, enrolled target and qualification driver are installed MMC
modules. Dependency acquisition/verification/installation/observation is `tools_t7/dependencies.py`;
the preflight and full release workflow is `tools_t7/release_verify.py`. Registry refresh, schema
bundling and binding renewal remain repository commands. `tools_t7/release_audit.py` assembles the
CMBA publisher's exact audit input from the signed core release, Windows and Linux terminal records,
full qualifications, and public-CI receipt. No hidden bespoke runner or hand-authored audit is required.
Read [adapter transport](ADAPTER-TRANSPORT.md), [SQLite target](SQLITE-TARGET.md), and
[offline dependencies](OFFLINE-DEPENDENCIES.md) for their exact contracts and limits.

`tools_t7/evidence_scope_adapter.py` is the product-owned mapping into UCM r038. It classifies every
admitted source file, binds external dependency/integration identities, and refuses reuse whenever
an evidence-relevant component changes or a file is unclassified. Full qualification writes the
exact index beside its receipt; release verification recomputes it from source. Reuse is inherited
engineering evidence, not new execution, authority, or independent approval. See
[component-rooted qualification](QUALIFICATION-INDEX.md).
