# Frozen end-to-end case catalogue

The original 100-case programme remains unchanged. The T5 contract and case milestones were recorded before the foundry implementation.
The terminal projection corpus was serialized after exploratory runs from the manually
specified design; it is not a blinded or independently generated oracle. Development failures do
not revise the required results. All cases use finite synthetic model rosters, public test
signers, the actual inherited evaluators, and real temporary SQLite transactions.

| Case | Scenario | Required challenge and terminal progress |
|---|---|---|
| AC-E2E-01 | safe-token | Actual collected inventory, bounded agent read/admission, seven approved transitions, retired legacy route |
| AC-E2E-02 | dormant-worker | Quiet/resumable legacy capability blocks retirement; fencing plus all other obligations permits retirement |
| AC-E2E-03 | persisted-reader | Required compatibility reader cannot disappear while old persisted state lacks disposition; repair then retirement |
| AC-E2E-04 | wrong-cohort | Authentic wrong-cohort signatures cannot authorize the canary; correct scoped approvals then complete |
| AC-E2E-05 | late-revocation | Withheld change is not known; stale observations block; delivered revocation blocks; explicit successor model then completes |
| AC-E2E-06 | lost-ack | Committed target with lost acknowledgment stays UNKNOWN; reopen, refuse blind retry, reconcile one mutation, retire |
| AC-E2E-07 | targeted-rollback | Only selected cohort compensates under new approvals; unrelated cohort and raised security floor stay unchanged |
| AC-E2E-08 | storage-migration | Missing inventory blocks preparation; repaired storage evidence permits the complete migration |
| AC-E2E-09 | workload-migration | Resume/checkpoint/pending-write incompatibility blocks; compatible drainage/fence record permits the complete migration |
| AC-E2E-10 | policy-migration | Missing consent and unacknowledged scope widening block; explicit revised policy/model and scoped approvals then complete |

There are seven primary target-operation records per case, except targeted rollback: ten
records including the unrelated cohort, compensation and reapplication. Counts are exact
known-answer expectations, not throughput measurements. A complete result also records every
observed check, hashed trace step and controller event; a count alone cannot satisfy a case.

Additional fault tests cover partial and conflicting coverage, withheld observations, expiry
under uncertain clocks, duplicate records, unrecognized/revoked observers, scoped joint
approvals, pauses and floor changes, crash/restart boundaries, bounded retries, partial
multi-target outcomes, whole-database rollback with a separately held checkpoint, model
revision, and changed target state. Partial effects remain RECOVERY_REQUIRED; no generic
repair algorithm is claimed. Whole-system backup/rollback without a protected external
floor remains a deployment risk rather than a solved cryptographic problem.

All ten final scenario outcomes and their hand-authored terminal projections must agree.
The actual source-bound run, not this document, supplies their current dispositions.
