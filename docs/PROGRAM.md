# Frozen MMC v0.1 construction program

This is the complete six-capability-layer program, not a claim that every workstream is delivered.
The original construction began with Capability Layer T1; the current public alpha contains bounded
realizations through T6 plus a separate Release Convergence line. Requirements below explicate the
agreed program; they are not a verbatim replacement for its history. See the canonical
[capability-layer model](architecture/CAPABILITY-LAYERS.md).

Program root: `abf1559fdede121a573335243b91dfa38014c6c825218ff2a6273656e593c7b7`.

## Six capability layers

### T1 — Foundation
Program, all requirements and exact gates; initial metamodel and deterministic compiler.
Workstreams: W00, W01, W02.

### T2 — Domain intelligence
Four executable profiles, richer planning and lifecycle/retirement semantics.
Workstreams: W03, W04, W05.

### T3 — Operational spine
Durable controller, actual courts and simulated/restricted effect mediation.
Workstreams: W06, W07, W08.

### T4 — Integration surfaces
Agent/CLI/UI/SDK and actually available native interfaces.
Workstreams: W09, W10, W11.

### T5 — Qualification
Multi-domain end-to-end simulations, failure cases and complete replay.
Workstreams: W12.

### T6 — Delivery and research handoff
Consolidated installable review candidate and independent study packets.
Workstreams: W13.

## Full requirements by workstream

### W00 — Program constitution and acceptance machinery (Capability Layer T1)

**MMC-W00-R01** — Preserve the complete W00-W13 six-capability-layer work program and stable requirement identities, including future and externally blocked work.

**MMC-W00-R02** — Bind every mandatory acceptance case to explicit requirements, an oracle, expected failure behavior and a scheduled gate; test totals cannot replace missing obligations.

**MMC-W00-R03** — Freeze governing semantics and expected results before implementation; amendments preserve predecessors, reasons and authorization posture.

**MMC-W00-R04** — Keep scope, authority, observations, simulations, native admission, approval and comparative research conclusions separate.

**MMC-W00-R05** — Produce cumulative decisions, dependency/risk registers, source custody, reproducible archives and independently invokable qualification.

**MMC-W00-R06** — Reject incomplete or inflated completion claims; native P/PPI admission requires real selected schema/interpreter/host evidence, not locally invented substitutes.

### W01 — Universal migration metamodel (Capability Layer T1)

**MMC-W01-R01** — Represent Asset, Actor, Flow, Dependency, Policy, Cohort, Observation, Obligation, Transition, Effect, Authority and Evidence as typed objects.

**MMC-W01-R02** — Represent old persisted data, new-data producers, consumers, resumable workloads, attached policies and old/new use-case/cohort mappings.

**MMC-W01-R03** — Carry source identity, declared time, version, jurisdiction, evidence references, uncertainty and scope explicitly.

**MMC-W01-R04** — Validate closed shapes, exact types, unique identifiers and reference-kind compatibility; refuse unsupported semantic inputs.

**MMC-W01-R05** — Preserve incomplete discovery and observation coverage as unknown or partial, never as proof of exhaustive absence.

**MMC-W01-R06** — Represent identity, storage, policy and workload examples using the same kernel primitives; deeper domain semantics are separate profiles.

### W02 — Canonical IR and deterministic compiler (Capability Layer T1)

**MMC-W02-R01** — Define a bounded, unambiguous canonical encoding, hash domains, model identity, profile identity, compiler identity and separate IR/receipt identities.

**MMC-W02-R02** — Compile accepted finite models without network, wall-clock, randomness, agent calls, untrusted code loading or external effects.

**MMC-W02-R03** — Resolve exact profile versions, references, target/cohort scopes and state transitions; reject unsupported operators and ambiguous interpretation.

**MMC-W02-R04** — Derive a deterministic dependency order, obligation instructions and evidence/authority/adapter requirements with source traceability.

**MMC-W02-R05** — Detect explicit order cycles, conflicting or unordered target changes, initial-state mismatches and literal contradictions without hiding them.

**MMC-W02-R06** — Allow unknown runtime facts to compile into unresolved obligations; compilation does not prove eligibility, completeness, admission or operational safety.

**MMC-W02-R07** — Replay compilation against the original model and pinned compiler; a rehashed forged IR or receipt must not pass.

**MMC-W02-R08** — Enforce finite byte, depth, node, object, expression, reference and transition budgets; machine-readable diagnostic and refusal codes are stable.

### W03 — Migration domain profiles (Capability Layer T2)

**MMC-W03-R01** — Qualify identity/delegation predicates for issuer, audience, scope, token flows, expiration, key changes and revocation.

**MMC-W03-R02** — Qualify storage/data predicates for schemas, replicas, custody, readers/writers, consistency, retention, residency and inventory reconciliation.

**MMC-W03-R03** — Qualify policy predicates for purpose, consent, authority, access, retention, widening and incompatibility.

**MMC-W03-R04** — Qualify long-running workload predicates for suspension/resume, checkpoints, delayed writes, version coexistence and drainage.

**MMC-W03-R05** — Each installed profile supplies versioned schema, predicates, transitions, diagnostics, fixtures and qualifications without changing kernel meanings.

### W04 — Dependency and migration planner (Capability Layer T2)

**MMC-W04-R01** — Distinguish unconditional order, conditional order, coexistence, exclusion, unknown and unsatisfiable constraints.

**MMC-W04-R02** — Analyze strongly connected components and distinguish an invalid order cycle from an explicitly supported coexistence phase.

**MMC-W04-R03** — Expose incompatible plans, unresolved blockers and affected cohorts with requirement-linked explanations.

**MMC-W04-R04** — Generate admissible plans under declared constraints; never treat an optimization ranking as a safety rule.

**MMC-W04-R05** — Reassess planning when declared dependencies, policy or coverage changes; no automatic discovery-completeness inference.

### W05 — Transition machines and retirement (Capability Layer T2)

**MMC-W05-R01** — Define allowed lifecycle and side states including blocked, paused, inconclusive, compensating and recovery-required; reject unrestricted reversal.

**MMC-W05-R02** — Derive transition prerequisites from declared profiles, cohort mappings and compatibility constraints.

**MMC-W05-R03** — Retirement requires legacy producer fencing, accepted outstanding-work and stored-state dispositions, consumer readiness and adequate fresh coverage.

**MMC-W05-R04** — Require scoped current authorization and a recovery plan that preserves security floors before retirement.

**MMC-W05-R05** — Dormant/resumable legacy workers block premature retirement; legitimate satisfaction must permit progress.

**MMC-W05-R06** — Targeted rollback affects only authorized cohorts and cannot silently revive revoked authority or discard newer security knowledge.

### W06 — Durable migration controller (Capability Layer T3)

**MMC-W06-R01** — Implement submit, compile, observe, assess, plan, prepare, approve, commit, verify, pause, resume, compensate, retire and replay with versioned state.

**MMC-W06-R02** — Use a durable event journal and recoverable projections; recorded observations, clocks and nondeterministic outcomes are explicit inputs.

**MMC-W06-R03** — Reconcile current observations with compiled obligations and report eligible or blocked transitions with exact scope.

**MMC-W06-R04** — Replay decisions without reissuing effects; restart at consequential stages reconstructs the accepted state.

**MMC-W06-R05** — Handle concurrency, idempotency, duplicate observations, divergence, stale plans and bounded retries.

**MMC-W06-R06** — Keep persistence/transport replaceable behind a tested contract; an initial SQLite implementation has explicit host and power-loss assumptions.

### W07 — Evidence courts and commitments (Capability Layer T3)

**MMC-W07-R01** — Define typed evidence for models, observations, coverage, policy assessments, approvals, effects and replay.

**MMC-W07-R02** — Qualify coverage, compatibility, temporal-safety, authority, cutover, retirement and replay courts with declared assumptions and limits.

**MMC-W07-R03** — Distinguish asserted, computed, replayed, witnessed and recognized evidence; no status promotion by declaration.

**MMC-W07-R04** — Reject fabricated PASS results, missing provenance, stale evidence and expired or out-of-scope approvals.

**MMC-W07-R05** — Bind exact models, plans, evidence, evaluator identities and receipts; CMBA/DKN integration is explicit and uses qualified pinned versions.

**MMC-W07-R06** — Court success is scoped admissibility evidence, not self-authorizing operational permission or universal truth.

### W08 — Effects authorization and recovery (Capability Layer T3)

**MMC-W08-R01** — Effects follow prepare-authorize-commit-observe through restricted adapters; simulations/read-only modes do not acquire production rights.

**MMC-W08-R02** — Bind migration, plan, target, cohort, pre/post-state, policy/evidence, idempotency key, principal, expiry, retries and recovery requirements.

**MMC-W08-R03** — Validate the relevant preconditions again at the point of effect; advertise any lack of atomic precondition enforcement.

**MMC-W08-R04** — Handle lost acknowledgments and partial/uncertain effects by reconciliation before retry, not presumed failure.

**MMC-W08-R05** — Consume approvals at most as specified and refuse target substitution, scope widening and replay.

**MMC-W08-R06** — Compensation and rollback preserve security floors; unknown irreversible outcomes require explicit recovery disposition.

**MMC-W08-R07** — Adapter capabilities, idempotency, effects, preconditions, time/resource limits and compensation boundaries are inspectable.

### W09 — Agent ABI CLI and adaptive orchestration (Capability Layer T4)

**MMC-W09-R01** — Agents receive bounded unresolved-obligation work orders with necessary context and no implicit effect authority.

**MMC-W09-R02** — Expose documented JSON ABI and CLI for actual implemented operations with parity and typed results.

**MMC-W09-R03** — Accept agent observations/proposals through validation; they cannot silently amend accepted rules, drop blockers or approve their own effects.

**MMC-W09-R04** — Refuse commit unless a qualified adapter and valid authority context are bound; process success is not permission.

**MMC-W09-R05** — Support a full investigation-submission-assessment cycle without requiring repeated reasoning over all settled history.

### W10 — Native workbench and visualization (Capability Layer T4)

**MMC-W10-R01** — Provide obligation-first graph, timeline, inventory, policy, evidence, court, effect-history and replay/diff views.

**MMC-W10-R02** — Display status by machine-readable assessment identity; imported/claimed reports remain unverified until checked.

**MMC-W10-R03** — The workbench and agents use the same headless decision semantics; presentation does not change eligibility.

**MMC-W10-R04** — Provide an optional dark-mode native UI while distinguishing sample data, observed data and actual host authority.

**MMC-W10-R05** — Keep local file effects explicit and scoped; viewing/importing evidence cannot install code, fetch data, sign or authorize deployment.

### W11 — Extensibility and interoperability (Capability Layer T4)

**MMC-W11-R01** — Provide profile and adapter SDK contracts, discovery, compatibility negotiation and conformance; unknown capabilities refuse.

**MMC-W11-R02** — Separate data-only capability discovery from trusted handler installation and effect authorization.

**MMC-W11-R03** — Qualify filesystem/SQLite fixtures and read-only repository, release, HTTP, deployment, job and storage observation interfaces with clear availability.

**MMC-W11-R04** — Bind actual P/PPI/UCM/CMBA/DKN/CHC integrations by exact version and source/native receipts; missing native artifacts remain blockers.

**MMC-W11-R05** — Demonstrate a new profile and observer without kernel modification; no data-supplied import path or arbitrary executable loader.

### W12 — Verification simulation and fidelity (Capability Layer T5)

**MMC-W12-R01** — Build finite simulations of delayed events, partitions, stale evidence, authority conflicts, crashes and partial effects.

**MMC-W12-R02** — Exercise compiler, graph, temporal, lifecycle, effect, recovery, agent and evidence failures with paired safe-progress cases.

**MMC-W12-R03** — Freeze requirements, fixtures, expected results and test identities; do not rewrite the oracle to fit the implementation.

**MMC-W12-R04** — Run exact-source clean extraction, selected reproducible rebuilds, corpus and current model-reference checks with terminal receipts.

**MMC-W12-R05** — Retain unsuccessful runs and interruptions; only complete admitted evidence can satisfy a gate.

**MMC-W12-R06** — Qualify actual target environments independently and keep simulations, same-author checks and independent reviews distinct.

**MMC-W12-R07** — The end-to-end scenario includes dormant worker, persisted legacy reader, wrong-cohort approval, stale revocation, lost acknowledgment and safe retirement.

**MMC-W12-R08** — Experimental-fidelity gates refuse productivity, economic or deployment conclusions lacking their own observed evidence.

### W13 — Packaging and comparative evaluation (Capability Layer T6)

**MMC-W13-R01** — Deliver source, installable library/CLI, optional controller/workbench, profile pack, schemas, docs, reproducible demo and closed evidence package.

**MMC-W13-R02** — Document binding versus semantic evaluation versus recognition versus enforcement versus observation; preserve residual limits.

**MMC-W13-R03** — Provide human/agent orientation, protocol/API, operations, threat model, qualification, migration/rollback, contributor and replay guidance.

**MMC-W13-R04** — Measure migration-design errors, safe progress and supervisory effort against a competent conventional system with equivalent inputs/tool access.

**MMC-W13-R05** — Count initial modeling, adaptation, debugging, review, AI use and human supervision; independent development and replication cannot be simulated by one author.

**MMC-W13-R06** — Keep release qualification and comparative research conclusions separate; preserve customer-selected versions and no forced updates.

## Governing invariants

Agents investigate; accepted models specify; compilers derive; only actually bound controllers/adapters can enforce.

Compilation is neither current eligibility nor permission. Evidence completeness, authenticity, truth and recognition are separate.

Unknown and stale data cannot be coerced to a positive observation; a quiet producer is not a fenced producer.

No effect follows from loading, compiling, verifying or inspecting a model.

Exact semantic/profile versions are reader-selected; no forced upgrades or silent root migration.

No trace, receipt, status string or test count supplies independent approval or native P/PPI admission.

Profiles are finite fixed semantics; untrusted input cannot import a handler or execute code.

Retirement and rollback must preserve stored-state, producer, consumer, cohort and security-floor obligations.

Every delivered guarantee needs a predicate, assumption, test and claim ceiling.

Requirements and oracles are frozen before realization; changes require explicit successor amendment with history.

Observe scope and coverage, not a claim of universal discovery or universal causality.

Product acceptance and independent comparative productivity evidence have different gates.

## External gates

native_pippi_binding, independent_review, native_windows_replay, deployment_key_clock_floor_custody, production_effect_adapter_approval, independent_participant_study

Capability-layer standing: frozen amended construction program, not ratified production authority.
The user retains version selection and authority over adoption. No pipeline action silently upgrades
customer software.
