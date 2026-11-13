# Version selection, migration and rollback

This release preserves every installed runtime/data byte from 0.1.0a5. Only distribution metadata,
qualification and documentation change. It does not automatically open, mutate or migrate a controller,
target store, trust configuration, accepted profile or namespace. Earlier versions remain selectable.

Prepare a separate virtual environment for a6. Verify source/wheel against an independently accepted
expected hash, install deliberately, then run capabilities and bounded fixtures. Keep the previous
environment and accepted policies until the replacement is separately accepted. Do not silently
replace old expected roots or regenerate old receipts to make new code appear equivalent.

Downgrading a package is NOT a migration compensation. Existing database schemas are unchanged,
but controller and simulated target form an operational pair. Restoring one file can lose knowledge
of committed effects; restoring both can lose idempotency history and internal floors. Retain a
separately protected external checkpoint when the deployment requires rollback resistance.

Use actual Controller recovery APIs documented in the T3 guide. UNKNOWN/DISPATCHED requires
reconciliation against the same admitted target; do not retry by guessing the effect failed.
PARTIAL stays RECOVERY_REQUIRED with the reservation retained. Compensation requires newly scoped
approvals, applies only to selected cohorts, and cannot erase raised floors/revocations.

No automatic backup daemon, database downgrade, general partial repair, guardian/key recovery
service or production rollout procedure is introduced in T6. Operator credentials and decisions
remain outside the portable source package.
