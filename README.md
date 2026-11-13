# Mosaic Migration Compiler

**Model the migration. Compile the obligations. Verify the transition.**

MMC compiles a finite migration model into explicit prerequisites, identifies unresolved
obligations, and mediates approved changes through a bounded local controller and explicitly
admitted local adapters. Agents investigate missing facts; deterministic evaluators preserve settled rules.

## What this alpha is

MMC v0.1 is a reference implementation and qualification surface for modeling a migration,
compiling its obligations, collecting scoped evidence, preparing separately approved effects,
and reconciling or compensating ambiguous outcomes. Its shipped end-to-end adapter targets a
disposable SQLite workload so the complete lifecycle can be inspected without touching production.

It is not a general migration orchestrator, a production adapter catalogue, an identity or
jurisdiction authority, or proof that an external environment is safe to migrate. A real deployment
must supply and qualify its own adapter, evidence sources, approval custody, rollback policy, and
platform execution record. Start with `mmc-product capabilities`, then `mmc-product protocol`, and
use `mmc-product verify-disposable-migration` before implementing a target adapter.

## Clean-checkout quick start

With CPython 3.12, create a virtual environment and install the operational extra from the checkout:

```sh
python -m venv .venv
# POSIX: .venv/bin/python ; Windows: .venv/Scripts/python.exe
.venv/bin/python -m pip install ".[operational]"
.venv/bin/mmc-product capabilities
.venv/bin/mmc-product verify-disposable-migration
```

On Windows, replace `.venv/bin/` with `.venv/Scripts/`. The final command creates only temporary
SQLite databases and child processes; it demonstrates evidence admission, separate approval,
effect dispatch, lost-acknowledgment reconciliation, compensation, re-cutover, and retirement.
For a smaller blocked-then-repaired fixture, run `mmc-foundry run late-revocation`: its milestones
show stale evidence and a delivered revocation blocking progress before an explicit replacement
plan is accepted. These fixtures use public test keys and do not authorize a real migration.

Current public alpha: **v0.1** (Python distribution **0.1.0a9**, Release Convergence r013). MMC's
six [capability layers](docs/architecture/CAPABILITY-LAYERS.md) retain the stable T1–T6 compatibility
identifiers without treating development turns as product architecture. This release repairs the T4 successor fixtures,
binds qualification to exact source bytes before and after execution, runs native/UCM
correspondence through a real hash-chained journal, exercises a real CMBA a7 binding, and
verifies one process-backed disposable SQLite migration through the native controller. That run
uses prepare/approve/commit, restart reconciliation after a lost acknowledgment, compensating
recovery, re-cutover, and retirement. The uniform `mmc.agent.v1` request/response
protocol exposes 47 operations, bundled nested schemas, compatibility negotiation, and a host-selected effect-adapter ABI.
The candidate includes mutually authenticated adapter processes and enrollment of existing SQLite
customer tables. Revision r007 hardens conflict handling at the write fence and verifies installed
files before Python site startup. Native full qualification profiles include the GUI screenshot
dependency, with exact offline handoff and receipt checking for Windows, Linux, and macOS.
Only completed host-bound execution receipts qualify a platform. Revisions r008-r013 select
patched installer, cryptography and image-library versions, embeds a dated OSV advisory
snapshot in the offline full-profile lock, and rejects the archived dependency profile
for current release verification. The public Git tree contains source only; exact third-party
wheels, offline closures, and raw qualification evidence remain separately licensed release or
owner-custody inputs. An unavailable patched macOS Intel wheel remains a declared profile gap.
The release runner qualifies source and installed code in separate clean environments without
system-site packages. See
[release preparation](docs/turn7/RELEASE-PREPARATION.md) for repeatable installed-wheel verification,
test-registry maintenance, audit repairs and outstanding release gates.
It retains strict qualification outcomes, full predecessor/obligation checks, isolated dependency
probes, the T1-T6 compatibility
surfaces, twelve example workflows, and ten replayable scenarios. It is not a production migration service.

Every controller write is admitted only if the resulting aggregate journal can still be replayed.
Before an adapter may run, the journal also reserves bounded space for an uncertain/partial outcome
and a terminal reconciliation. Capacity refusal therefore occurs before the target effect. Public CI
has separate source and installed-wheel jobs; the installed job runs outside the checkout and proves
module origins, protocol conformance, and a complete disposable migration.

```sh
python -m pip install ./mosaic_migration_compiler-0.1.0a9-py3-none-any.whl
mmc-product capabilities
mmc-product protocol
mmc-product schema all
mmc-product request request.json
mmc-product integrations
mmc-product probe-cmba ./cmba_core-0.1.0a7-py3-none-any.whl
mmc-product verify-disposable-migration
mmc capabilities
mmc-agent capabilities
mmc-foundry list
# Prepare genuine cryptography 50.x before running signed fixture scenarios:
mmc-foundry run safe-token
# Optional: Tk and a display are required.
mmc-workbench
```

The core has no third-party runtime dependencies. Operational signing uses the explicit optional
`cryptography>=50.0.2,<51` dependency. No command installs its own dependencies or trusts an embedded
sample key. Foundry runs use public fixtures and NEW temporary SQLite databases. They are not
production evidence. Journal replay is non-effectful; full foundry replay performs new simulation writes.

Read the [current Release Convergence dossier](docs/turn7/README.md),
[controller state machine](docs/architecture/CONTROLLER-STATE-MACHINE.md),
[release preparation](docs/turn7/RELEASE-PREPARATION.md), and
[product correspondence](docs/turn7/PRODUCT-CORRESPONDENCE.md). The preserved
[Capability Layer T6 dossier](docs/release/README.md), [historical user guide](docs/release/USER-AND-INTEGRATION.md),
and [historical claims](docs/release/CLAIMS-AND-ACCEPTANCE.md) retain predecessor context but do not
override current licensing, dependencies, or platform status. The [frozen program](docs/PROGRAM.md) and
[100 acceptance cases](docs/ACCEPTANCE.md) remain the governing construction requirements.

MMC-owned material is available under the [Apache License 2.0](LICENSE). Third-party
artifacts retain their own terms; see [third-party notices](THIRD-PARTY-NOTICES.md).

**Native identity/jurisdiction UNBOUND; production adapter NOT_SHIPPED; macOS execution NOT QUALIFIED; independent comparative study NOT_PERFORMED.**
Use owner-selected versions and accepted roots. No forced upgrade, live platform integration,
cloud data move, production token issuance or operational authority follows from installation.
Release identity and publication custody are described in
[the publication guide](docs/release/PUBLICATION.md). Full native qualification uses
[separately supplied exact inputs](docs/release/QUALIFICATION-INPUTS.md). Component-rooted
[evidence scope](docs/turn7/QUALIFICATION-INDEX.md) is fail-closed and never changes release identity.
MMC owns only its application mapping; UCM r038 computes dependency closure, freshness, and typed
requalification dispositions. An impact plan never grants effects, acceptance, or release authority.
