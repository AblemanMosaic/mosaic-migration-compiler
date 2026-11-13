# Public requirements summary

This non-identifying summary records the product requirements extracted from
owner-supplied design discussions. The source conversations are deliberately
excluded from the public repository because they were not authored for public
distribution and are not executable authority.

MMC must model heterogeneous migrations as explicit finite systems. A model
names persisted state, producers, consumers, dependency order, use cases,
cohorts, coexistence rules, uncertainty, evidence, authority prerequisites,
adapter requirements, retirement conditions, and recovery floors. Compilation
must turn those declarations into traceable obligations rather than treating a
high-level migration goal as permission to act.

The product must support investigation and execution by agents through stable,
machine-readable ABI, IR, schema, CLI, and request/response surfaces. Agents may
collect missing facts and propose work, while deterministic evaluators preserve
settled rules and explicit capability limits. Receipt-before-effect gating,
point-of-effect rechecks, typed refusals, idempotency, reconciliation after
ambiguous outcomes, and bounded recovery are required wherever an adapter can
cause a change.

Migration is a lifecycle, not a copy operation. It includes preparation,
coexistence, cohort movement, cutover, retirement, and recovery. Retirement
requires evidence that old production has ceased, outstanding work is resolved,
consumers are ready, required state is dispositioned, and legacy writes are
blocked. Dormant or scheduled workloads must be represented even when they do
not run in ordinary continuous-integration windows.

The compiler and its local disposable adapters do not grant production
authority. Real deployments require owner-selected adapters, identity and
jurisdiction bindings, recognized evidence, scoped approval, and target-host
qualification. A passing signature, hash, test, or conformance report proves
only the claim stated by that artifact.
