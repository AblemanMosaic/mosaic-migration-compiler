# Exact acceptance and evidence gates

The 100 mandatory cases below were frozen before runtime implementation. Each case has a fixed intent and oracle. T1 has 29 due cases; all later cases remain NOT_RUN regardless of how many foundation tests pass.

Current results live in signed-or-unsigned-as-labeled evidence, not by rewriting this catalogue. The present records are unsigned. A local PASS cannot confer native admission or independent approval.

## MODEL

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-MODEL-01 | T1 | all twelve primitives: Validate a fixture containing each of the twelve primitive kinds; missing/unknown kind refuses. |
| AC-MODEL-02 | T1 | exact field types: Boolean cannot substitute for integer; unknown/missing fields and wrong collection kinds refuse. |
| AC-MODEL-03 | T1 | unique names: Duplicate object IDs, duplicate set entries and aliases are rejected. |
| AC-MODEL-04 | T1 | typed references: Dangling and wrong-kind references refuse with field/ID diagnostics. |
| AC-MODEL-05 | T1 | cohort scope: Affected targets and effects must belong to the selected declared cohort scope. |
| AC-MODEL-06 | T1 | unknown coverage: Unknown or partial observation coverage survives normalization and lowering. |
| AC-MODEL-07 | T1 | source provenance: Every object has source_ref, exact digest, declared time, epistemic class and note; omission refuses. |
| AC-MODEL-08 | T1 | finite limits: Oversized source, strings, nesting, object count and expression depth refuse with typed limits. |
| AC-MODEL-09 | T1 | set normalization: Reordered objects and declared set fields normalize identically; meaningful sequence order is preserved. |
| AC-MODEL-10 | T1 | no coercion: Floats, NaN, duplicate JSON keys, invalid Unicode, negative revisions and unsupported forms refuse. |
| AC-MODEL-11 | T1 | four domain examples: Identity, storage, policy and workload models all validate under foundation semantics; no domain validation claimed. |
| AC-MODEL-12 | T1 | policy and evidence shapes: Authority/policy/evidence/observation relationships and declared intervals validate exactly. |

## COMPILER

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-COMPILER-01 | T1 | repeat determinism: Repeated compile of identical input yields exact canonical bytes and roots. |
| AC-COMPILER-02 | T1 | stable lowering: Independent input permutation produces the same canonical model/IR and deterministic transition ordering. |
| AC-COMPILER-03 | T1 | profile pin: Unknown or substituted profile/version/hash refuses; no automatic interpretation fallback. |
| AC-COMPILER-04 | T1 | DAG order: Every explicit predecessor precedes its dependent; independent ties are lexicographic, not safety claims. |
| AC-COMPILER-05 | T1 | cycle diagnostic: Order cycle yields typed refusal with the exact remaining cyclic/blocking nodes; no fabricated sequence. |
| AC-COMPILER-06 | T1 | state compatibility: Unordered overlapping targets, missing initial state and mismatched state chains refuse. |
| AC-COMPILER-07 | T1 | obligation derivation: Source requirements and all applicable policy/authority/evidence/effect needs lower into traceable guards. |
| AC-COMPILER-08 | T1 | unknown is not ready: Unknown observations compile to RUNTIME_REQUIRED, never permission or current safety. |
| AC-COMPILER-09 | T1 | static contradiction: A false constant guard yields an explicit static blocker and non-executable claim ceiling. |
| AC-COMPILER-10 | T1 | tampered IR: Mutation and self-rehashing of IR/receipt fail recompilation comparison against the pinned source and compiler. |
| AC-COMPILER-11 | T1 | change sensitivity: Relevant model/profile/compiler changes alter their committed identities; caller mutation cannot change saved results. |
| AC-COMPILER-12 | T1 | pure and inspectable: Compile makes no network/process/effect/clock call; read-only ABI/CLI matches library and refuses execute. |

## PROFILE

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-PROFILE-01 | T2 | identity flow: Actual issuer/audience/scope compatibility accepts a correct flow and refuses a substituted authority. |
| AC-PROFILE-02 | T2 | key lifecycle: Actual rotation and revocation models distinguish historical validation from current admission. |
| AC-PROFILE-03 | T2 | storage inventory: Actual source/destination inventories reconcile and expose missing persisted state. |
| AC-PROFILE-04 | T2 | retention residency: Actual storage obligations block forbidden deletion or location change. |
| AC-PROFILE-05 | T2 | policy widening: Actual policy transition detects widening and requires corresponding authorization. |
| AC-PROFILE-06 | T2 | purpose consent: Actual purpose/consent changes expose incompatible conditions rather than coerced merge. |
| AC-PROFILE-07 | T2 | workload resume: Actual suspended-worker model preserves its future legacy write potential. |
| AC-PROFILE-08 | T2 | workload checkpoint: Actual checkpoint/version compatibility and drainage dispositions checked. |
| AC-PROFILE-09 | T2 | conditional order: Planner evaluates declared conditional order without inventing observations. |
| AC-PROFILE-10 | T2 | coexistence exclusion: Planner distinguishes supported coexistence from forbidden version overlap. |
| AC-PROFILE-11 | T2 | fixable versus impossible: Planner distinguishes phase-resolvable graph cycles from unsatisfiable constraints. |
| AC-PROFILE-12 | T2 | profile isolation: A new qualified domain profile composes without redefining kernel primitives. |

## LIFECYCLE

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-LIFECYCLE-01 | T2 | allowed lifecycle: Declared state machine accepts only allowed lifecycle transitions and preserves side states. |
| AC-LIFECYCLE-02 | T2 | cohort mapping: Phased old/new route mappings remain exact to their intended cohorts. |
| AC-LIFECYCLE-03 | T2 | producer fencing: Retirement blocks when a declared old producer remains able to create legacy state. |
| AC-LIFECYCLE-04 | T2 | dormant worker: A quiet but resumable legacy worker blocks retirement until disposed/fenced. |
| AC-LIFECYCLE-05 | T2 | persisted reader: Legacy reader removal blocks while persisted data lacks an accepted disposition. |
| AC-LIFECYCLE-06 | T2 | consumer readiness: Retirement requires evidence for all declared required consumers. |
| AC-LIFECYCLE-07 | T3 | stale coverage: Missing, stale or incomplete required telemetry is not zero activity. |
| AC-LIFECYCLE-08 | T3 | freshness windows: Eligible observation interval boundaries and clock uncertainty are explicit. |
| AC-LIFECYCLE-09 | T3 | targeted rollback: Only selected cohorts revert; other accepted migrations remain intact. |
| AC-LIFECYCLE-10 | T3 | security floor: Recovery does not restore revoked authority or discard newer protected knowledge. |
| AC-LIFECYCLE-11 | T2 | safe retirement: After all required dispositions and fences are established, legitimate retirement progresses. |
| AC-LIFECYCLE-12 | T3 | plan revision: Changing an accepted plan invalidates dependent approvals and requires new assessment. |

## AUTHORITY

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-AUTHORITY-01 | T3 | exact approval: Approval binds exact plan/action/target/cohort; any substitution refuses. |
| AC-AUTHORITY-02 | T3 | recognized principal: Valid signatures from unrecognized parties do not satisfy approval. |
| AC-AUTHORITY-03 | T3 | joint jurisdiction: One jurisdiction cannot mask another required missing or denying jurisdiction. |
| AC-AUTHORITY-04 | T3 | temporal approval: Expired/not-yet-valid approval cannot advance a transition. |
| AC-AUTHORITY-05 | T3 | asserted PASS: Submitted PASS reports must be recomputed or recognized under an explicit evidence rule. |
| AC-AUTHORITY-06 | T3 | evidence provenance: Missing/wrong provenance, observer or subject cannot satisfy an obligation. |
| AC-AUTHORITY-07 | T3 | duplicate signer: Duplicate signatures/keys do not increase threshold or independence. |
| AC-AUTHORITY-08 | T3 | contradictions: Applicable negative evidence remains visible and has declared precedence. |
| AC-AUTHORITY-09 | T3 | coverage court: Declared completeness is distinguished from actually qualified source coverage. |
| AC-AUTHORITY-10 | T3 | cutover court: Cutover checks source, destination and consumer consistency under declared scope. |
| AC-AUTHORITY-11 | T3 | replay court: Decision replay binds model, policy, evidence, time and evaluator without issuing effects. |
| AC-AUTHORITY-12 | T3 | no self-authorization: Court result alone never becomes effect authority or native admission. |

## EFFECT

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-EFFECT-01 | T3 | prepare pure: Preparing an effect changes no external target. |
| AC-EFFECT-02 | T3 | approval separate: An input document or agent result cannot manufacture a host authorization. |
| AC-EFFECT-03 | T3 | commit precondition: Relevant target/pre-state/expiry rechecked at effect point; lack of atomicity declared. |
| AC-EFFECT-04 | T3 | duplicate request: Duplicate idempotency key does not repeat an already confirmed effect in qualified adapter. |
| AC-EFFECT-05 | T3 | lost acknowledgement: An effect whose response was lost is reconciled before retry. |
| AC-EFFECT-06 | T3 | partial effect: Partial target mutation is reported with uncertainty, not no-effect refusal. |
| AC-EFFECT-07 | T3 | restart recovery: Restart at consequential journal boundaries restores the accepted projection. |
| AC-EFFECT-08 | T3 | replay non-effectful: Replaying a journal never reissues commands. |
| AC-EFFECT-09 | T3 | concurrent migration: Overlapping migrations cannot overwrite selected plan/state without conflict handling. |
| AC-EFFECT-10 | T3 | bounded retry: Retries stop at declared budget and preserve terminal/unknown outcomes. |
| AC-EFFECT-11 | T3 | approval consumption: Used, cancelled or superseded approval cannot be reused. |
| AC-EFFECT-12 | T3 | scope substitution: Different target/cohort/configuration after prepare refuses. |
| AC-EFFECT-13 | T3 | compensation: Compensation runs only its authorized scope and does not erase historical effects. |
| AC-EFFECT-14 | T3 | host limits: Unsupported adapters, hostile-host assumptions and physical durability remain explicit gates. |

## AGENT

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-AGENT-01 | T4 | bounded investigation: Work order contains unresolved obligation, allowed reads, return schema and no effect grant. |
| AC-AGENT-02 | T4 | submission validation: Malformed/injection-bearing proposals remain data and do not amend accepted semantics. |
| AC-AGENT-03 | T4 | CLI ABI parity: All advertised operations exist with exact versioned CLI/JSON/library parity. |
| AC-AGENT-04 | T4 | context economy: One full investigate/submit/reassess cycle uses bounded context and preserves source references. |
| AC-AGENT-05 | T4 | UI evidence labels: UI distinguishes sample/asserted/imported/recomputed/recognized states without a broad verified badge. |
| AC-AGENT-06 | T4 | UI headless parity: Workbench status and headless assessment are identical for the same admitted inputs. |
| AC-AGENT-07 | T4 | new adapter: A new observation adapter qualifies without changing compiler semantics or importing code from data. |
| AC-AGENT-08 | T4 | read isolation: Open/inspect/import cannot fetch, install, sign, alter trust or commit effects. |

## E2E

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-E2E-01 | T5 | full safe path: Complete primary token migration through discovery, canary, coexistence, fencing and retirement. |
| AC-E2E-02 | T5 | dormant interruption: Dormant worker reappears; retirement is refused then succeeds after valid disposition. |
| AC-E2E-03 | T5 | retained legacy object: Stored legacy data prevents removal until accepted transformation/retention/isolation. |
| AC-E2E-04 | T5 | wrong cohort: An authentic approval for another cohort cannot unlock this migration. |
| AC-E2E-05 | T5 | late revocation: Delivered revocation/stale required evidence interrupts eligibility without rewriting identity. |
| AC-E2E-06 | T5 | ambiguous external effect: Lost acknowledgement followed by restart does not duplicate the committed test effect. |
| AC-E2E-07 | T5 | rollback limits: Emergency cohort rollback preserves protected security state and unrelated progress. |
| AC-E2E-08 | T5 | storage migration: Independent storage family completes under its own obligations with same kernel. |
| AC-E2E-09 | T5 | long-running job: Independent workload family handles checkpoint/resume/drain with same kernel. |
| AC-E2E-10 | T5 | policy transition: Independent policy family exposes incompatibility and permits an authorized safe change. |

## REPRO

| Case | Due | Intent and exact oracle |
|---|---|---|
| AC-REPRO-01 | T1 | frozen constitution: All exact frozen contracts match an externally supplied expected program root; changed/missing/extra entries refuse. |
| AC-REPRO-02 | T1 | completion fidelity: Missing requirement/case, forged passing count, changed test identity or absent current evidence cannot satisfy gate. |
| AC-REPRO-03 | T1 | closed delivery: Complete source archive closure, portable paths, exact member hashes and repeat serialization verified. |
| AC-REPRO-04 | T1 | clean install replay: Fresh extraction and installed-wheel use outside source execute the scoped gate with no hidden dependencies. |
| AC-REPRO-05 | T6 | target platforms: Native Windows, POSIX/WSL and other claimed platforms produce their own exact qualification evidence. |
| AC-REPRO-06 | T4 | native P/PPI: Actual owner-selected native schema, validator, interpreter, work selection and host evidence bound; otherwise NOT_ESTABLISHED. |
| AC-REPRO-07 | T1 | research honesty: Same-author software checks cannot certify independent productivity, person-hours or economic savings. |
| AC-REPRO-08 | T6 | final release: Complete implemented program evidence and residual/external gates reconciled; no fabricated independent approval. |

## Mandatory T1 evidence legs

Freeze integrity; named unit/acceptance outcomes; model reference/test traceability; frozen known-answer vectors; executable examples; fresh-extraction replay; outside-source installed-wheel verification; exact archive closure. All must refer to the same admitted source and actual terminal outcomes.

The program matrix maps groups of cases to the requirements they jointly support; it is not a theorem that one passing test realizes every linked sentence. T1 realization bindings narrow this to current named symbols and tests. Native P/PPI, live effects, target environments and independent research need their own evidence.
