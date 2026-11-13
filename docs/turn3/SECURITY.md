# T3 security and trust boundary

Same-author experimental candidate. No independent approval, native P/PPI or production operation.
The operational key format is separate from T1/T2 and all native CMBA/DKN protocols. This package
uses no unqualified CMBA integrated-composition report and does not impersonate a P/PPI interpreter.

## What is checked

Exact plan/policy/target/cohort identity; admitted P-256 points and signatures; recognized source,
method and evidence class; fresh whole uncertainty interval; observed stream high-water marks;
negative evidence; recomputed finite predicates; every required jurisdiction; target version CAS;
operation identity; monotone security state; full-event replay and optional external checkpoint.

## What remains trusted or unestablished

- Host interpreter, crypto backend, filesystem, controller code and supplied clock.
- Legitimacy/custody of configured keys and actual truth of signed observations.
- Completeness of the model roster. A recognized observer can lie; independent keys can collude.
- External checkpoint protection; an internal hash chain alone cannot prevent whole-state rollback.
- Physical power failure, network filesystems, hostile admins, machine compromise and cross-host atomicity.
- Live production adapters, automatic revocation feeds, guardian/key custody and native orchestration.

A final simulated precondition check is atomic only inside the qualified local adapter. A real adapter
must independently qualify its CAS, idempotency and compensation contracts. A controller journal and
an external effect cannot generally be committed atomically here: durable intent + reconcile handles
that gap for the supported adapter. Never infer a universal exactly-once claim.

Faults before target commit and after target commit were exercised with actual subprocess exits.
Those tests are process-failure evidence, not physical-durability evidence. Concurrent threads use
separate controller objects and SQLite connections under a cooperating-host assumption.

PARTIAL retains facts and blocks normal advancement. No automated partial repair or arbitrary external
command runner is delivered. Standard-library-only core use remains available. No signing or effects
are reachable through the closed data ABI. Inputs containing instructions remain data.
