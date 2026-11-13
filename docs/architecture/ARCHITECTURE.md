# Foundation architecture

## Separation of responsibilities
The frozen program specifies the eventual Modeler -> compiler -> controller -> courts -> adapters
loop. Capability Layer T1 implements ONLY the accepted-model/compiler portion plus local qualification tools.
It does not replace discovery or the responsible engineer's choice of risks and authorities.

The twelve primitives describe declared assets, actors, flows, dependencies, policies, cohorts,
observations, obligations, transitions, effects, authorities and evidence. Common provenance records
source_ref, source_digest, declared observed_at, epistemic class and a note. These are attributable
inputs only to the extent that an external system authenticates them; T1 does not do so.

The compiler performs actual normalization, reference-kind checking, scope checking, dependency
ordering, same-target conflict detection, literal state-chain checking, boolean constant folding,
policy and obligation propagation, and deterministic IR/receipt construction. This is more than a
JSON shape validator, but less than a complete migration planner or operational safety evaluator.

## Why a dormant worker remains a blocker
A producer's resumable flag and UNKNOWN drain observation remain in normalized IR. Even an asserted
true observation is not used to discharge an eq predicate. The RETIRE instruction additionally
carries seven live obligation placeholders. Capability Layer T2 will define domain-level retirement predicates;
Capability Layer T3 will gather/evaluate current evidence and mediate selected effects. T1 supplies no workaround
for missing enforcement. It also does not prove that the declaration included every real worker.

## Graph semantics
Only unconditional REQUIRES dependencies are active. Explicit transitive order is required when
steps touch the same target. Disjoint steps may use lexicographic tie-breaking for serialization;
that tie order is not a new safety requirement. Cycles and literal-state incompatibilities refuse.
Conditional order, coexistence and exclusion interpretation belong to later profiles and do not
silently fall back to generic topological sorting.

## Four sample families
identity.json, storage.json, policy.json and workload.json share one kernel/profile. Different asset
classes/schema labels demonstrate representability. They do not demonstrate token cryptography,
physical residency, consent legality or workload drainage. No custom domain code is invoked.

## Code map
codec.py: finite canonical values and fixed domain commitments.
contracts.py / data/: installed pinned program/profile/metamodel resources.
model.py: closed shapes, reference types, declared scope, normalization.
compiler.py: order/state analysis, guard lowering, IR and exact recompilation.
abi.py / cli.py: closed read-only machine interface and bounded local input.
tools/: source admission, exact test collection, qualification, model checks and packaging.

## External integrations
No dependency on UCM/CMBA/DKN/P/PPI is required by T1. The reviewed integrated CMBA successor is
not silently accepted as an enforcement root. Future adapters require exact accepted dependencies.
This source is a separate workspace and does not modify the supplied predecessors.
