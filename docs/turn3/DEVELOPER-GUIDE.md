# T3 developer and operator guide

The base distribution still runs without third-party runtime packages. Actual T3 signatures need
`cryptography>=46,<47`; its absence produces MMC_T3_SIGNING_DEPENDENCY. No fallback signature is used.
Use the supplied local wheel. Installing an unreleased name from a public registry is not assumed.

```python
from mosaic_mmc_t3 import Controller, SimulatedStore, make_plan, digest

# bundle is a valid T2 model bundle; policy is YOUR recognized observer/authority configuration.
plan = make_plan(bundle, policy)
controller = Controller.create("controller.sqlite", policy)
# expected root must be selected through your accepted configuration path.
controller.submit("migration.example", bundle, expected_plan_root=plan["root"])
```

The snippet is model construction, not a production recognition ceremony. Obtain pins independently
of untrusted packets. Create a target with `SimulatedStore.create(path,id,{target:state},floor=...,revoked=...)`.
Signed observations are made by `seal(body,key)` and ingested by `controller.observe(migration,record)`.
No method claims a fixture statement reflects an actual service.

## Core APIs

| API | Meaning |
|---|---|
| make_plan / validate_plan | Bind/recompute the exact T2 plan and selected T3 reader policy |
| seal / verify / public_hex | Explicit caller-held P-256 signing, admission and exact verification |
| evaluate_evidence / replay_evidence | Pure source, compatibility, temporal, coverage, cutover/retirement checks |
| assess_authority | Exact per-jurisdiction signature thresholds and scope/interval checks |
| Controller.create / constructor | Create local journal; reopen under expected policy and optional external checkpoint |
| submit / revise | Explicit model admission/revision under expected plan and optional current-head CAS |
| observe / assess | Record signed observation; recompute eligibility evidence |
| prepare / approve / commit | Separate host calls; only commit can invoke the simulated target |
| reconcile | Consult selected target ledger after ambiguous return; never retry automatically |
| raise_floor | Explicit host floor/revocation update, monotone and approval-invalidating |
| pause / resume | Pause/resume without silently reviving an old approval |
| cancel | Cancel only pre-effect or proven-not-applied work |
| replay | Rebuild and inspect journal projection without adapter execution |

Prepare signature: `prepare(migration,transition,adapter,time,operation_id=...,ttl=30,
direction='FORWARD',expected_head=None)`. Compensation uses direction='COMPENSATE'.
Approve accepts public signed records, never private-key material or a JSON PASS report.
Commit receives operation ID, fixed adapter and supplied clock. The optional fault argument exists
only on the trusted Python simulation surface; it is not an untrusted-request operation.

## Read-only interface

`mmc-t3 capabilities` or `mmc-t3 request REQUEST.json` (`-` reads stdin). Requests have exactly
schema `mmc.request.t3`, operation, arguments. Operations: capabilities, plan, verify-statement,
evidence, replay, authority. Exact keys are exported by `abi.OPERATIONS` and request.schema.json.
No submit, sign, approve, write, install, fetch or commit exists in this data ABI. Exit 0 means a
computation completed, including BLOCKED/INDETERMINATE. Typed refusals exit 2. Output is canonical
JSON plus newline. File reads are bounded and refuse symlink/junction ancestors.

## Run examples

`python examples/t3/operational_recovery.py`

`python examples/t3/compensation_and_floors.py`

These create temporary databases and use clearly marked PUBLIC FIXTURE scalars, sign evidence and
approvals, execute simulated row changes, reconstruct after lost acknowledgment, compensate one
cohort, and test an external checkpoint. They are not a production key ceremony or the complete T5
primary migration. Their fixture helper lives in tests_t3/helpers.py and is not included in the wheel.

## Recovery discipline

Always reopen with accepted policy root and, when required, a separately protected minimum journal
checkpoint. UNKNOWN or DISPATCHED is not failure: call reconcile against the SAME preserved adapter.
Do not restore one SQLite database without considering the controller/target pair and external floor.
An old target database can lose its idempotency history. No protocol here prevents a hostile operator
from restoring or rewriting both databases. PARTIAL remains RECOVERY_REQUIRED with its target lock.
