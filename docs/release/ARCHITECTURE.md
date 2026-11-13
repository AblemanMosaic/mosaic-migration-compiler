# Architecture and realized boundaries

The metamodel has twelve typed primitives: Asset, Actor, Flow, Dependency, Policy, Cohort,
Observation, Obligation, Transition, Effect, Authority and Evidence. T1 validates provenance,
references, scope and finite encodings; compiles stable IR; and retains unresolved runtime guards.
T2 adds identity, storage, policy and long-running workload predicates, a bounded planner, cohort
routing and retirement assessment. A quiet resumable producer remains capable of legacy writes.

T3 composes the actual T2 result with caller-selected observer/authority policy. P-256 signatures
bind scoped observations and approvals. Coverage is recognized testimony over the declared roster,
not proof that every real producer has been discovered. Freshness, revocation, highest observed
sequence and external floors matter independently of signature validity. Every required jurisdiction
must be satisfied. A submitted PASS is not a substitute for the signed source material.

The Controller journals intent before invoking SimulatedStore. The target commits row changes and
an idempotency record in one cooperative local SQLite transaction. Lost acknowledgment leaves UNKNOWN;
reconciliation checks the same target ledger. Partial writes remain RECOVERY_REQUIRED. Compensation
requires a new request and approvals; it cannot lower floors or alter unrelated cohorts. This is
not distributed exactly-once, physical power-loss proof or protection against an administrator
restoring both databases. Only sequential plans are executable; atomic phases need an unbound adapter.

T4 provides bounded investigation work orders, signed return review, explicit host admission,
read-only ABI, fixed SDK handlers, scoped collectors and an obligation-first native Tk workbench.
Data cannot register code or manufacture host permission. HTTP collection is an explicitly host-
selected bounded operation, not a consequence of opening a document. Collector snapshots are not
live Kubernetes/Git discovery. Native CMBA/DKN readers are limited pinned operations; P/PPI/UCM are not bound.

T5 runs ten finite migration scenarios using those actual components. It does not replace the
controller with a parallel simulator. One trace inspection checks supplied records; journal replay
reconstructs without effects; full scenario replay executes in new temporary stores. Keep these
three operations distinct. All demonstration keys are public fixtures.

T6 adds qualification tooling and current documents only. The same versioned runtime interfaces
remain selectable; it neither broadens authority nor changes stored namespace/model identities.
