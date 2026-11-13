# T5-Q1 qualification protocol

The preimplementation contract is `model/qualification-t5/CONTRACT.json`. Its root commits
to the ten case identities, oracles, expected milestones, finite limits and nonclaims.
The immutable original acceptance catalogue governs their intended meaning. This document
explains the finite realization, not a silent amendment to T1–T4.

## Finite inputs and execution

`run_scenario(name, seed=0)` accepts one of ten installed names and an exact integer 0..31
(boolean is not an integer here). The seed controls bounded delivery ordering, not an
external random process. The caller authorizes temporary test files/database writes.
Paths, keys, arbitrary handlers, URLs and shell commands cannot be supplied by scenario data.
All private scalars in the foundry are public test fixtures, never production credentials.

The source inventory is generated from the finite fixture, captured using the actual T4
JsonFileCollector, and can be read through an exact-resource ReadSession during the agent
cycle. It is explicitly not exhaustive discovery of a real organization. Models are generated
from retained T2 domain examples, with seven explicit transitions and associated Effects:
prepare; canary; coexistence; fence; data reconciliation; cutover; retire. Every control effect
runs through T3 prepare/approve/commit. Required observations and both jurisdictional approvals
are signed with the actual deterministic ECDSA P-256 implementation. The native predicates,
not the scheduler, decide admission. Compiler, court, plan and request identities are retained.

The target is the existing T3 SQLite simulated adapter: labels/versions/floors and idempotency
records, not real tokens, storage transports, training processes or production services.
Independent domain cases use the actual identity, inventory, policy and workload evaluators.
Reported residency, custody and coverage are recognized fixture testimony, not physical facts.

## Replay and identity

Trace steps bind index, predecessor, kind and exact value under `MMC/T5/step` plus NUL.
The result binds scenario, seed, semantic contract, foundry realization, native evaluator,
checks, milestones, trace, full journal, final target view and effect count under `MMC/T5/trace`
plus NUL. No elapsed wall time, temp directory or PID is part of this semantic trace.
Runtime source identity is a separate hash of installed foundry code/data files.

`inspect_result(candidate, expected_root=...)` verifies exact shapes, boundaries, trace linkage,
contract/version, completed path and native journal reconstruction. It checks the supplied
expected root; obtaining that root from the same untrusted candidate authenticates nothing.
Inspection does NOT prove the original execution occurred or that its final target view was
physically witnessed. `replay_scenario(name,candidate,seed=...)` reruns the entire scenario in
fresh temporary stores and compares exact canonical bytes, including results, not just hashes.
That establishes repeatability in this environment, not independent review or production truth.
Pure `journal_view` replay is also tested to make no target invocation.

## Correctness oracles

`interop/t5-known-answers.json` has ten manually authored outcome projections: exact final
primary states, completed transition count, target effect count and required milestones. The
oracle is separate from code-derived trace roots. A deliberately rehashed false trace must fail
full replay. Replaying reference code is not an independent implementation of that code.

All data/output are finite; input/output canonical byte cap 8 MiB, 256 trace steps, 64 adapter
operations; native compiler/journal/observation budgets still apply. Negative tests assert no
target-byte/version/effect-count change unless the scenario explicitly exercises partial or
ambiguous outcomes. No benchmark time, human-effort or zero-risk conclusion is inferred.
