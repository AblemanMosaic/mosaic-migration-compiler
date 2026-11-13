# Capability Layer T5 construction findings and limits

## F01 — incorrectly modeled delegation parent in the first new fixture
The initial parent token retained the leaf subject; actual attenuation checks rejected the model.
The fixture now states that the parent holder is the child issuer. The failing compiled assessment
is retained. No library rule or expected safe/unsafe outcome was weakened.

## F02 — bounded execution window and noncanonical probe telemetry
A combined preliminary probe exceeded its invocation window after completed cases. Those case
outputs are preliminary records, not a complete gate. The subsequent probe completed all remaining
scenarios but its own final summary attempted to encode floating-point seconds using the exact
canonical codec, which correctly refused. Successful scenario records and the failed wrapper log
remain preserved. Qualified tools use integer nanoseconds and independently terminal stages.
An unavailable interactive terminal launch and a missing provisional probe script are also retained
as operational setup errors; they do not count as product failures or successful runs.

## F03 — wrong-plan observation rejected earlier than test expected
The first additional fault suite expected a wrong-plan statement to reach the evaluator's quarantine.
The real Controller rejected it at ingestion with MMC_T3_OBSERVATION_SCOPE. The corrected test
requires that stronger early refusal and confirms missing evidence does not become eligible.
The failing test log is retained. Runtime and frozen acceptance oracles remain unchanged.

## Review scope
Additional tests challenge partial coverage, expiry during a partition, superseded observations,
equal-sequence contradictions, duplicated positives, key revocation, wrong plan/target/cohort,
missing/denying jurisdictions, clock uncertainty, changed floors, pause/revision invalidation,
crash and ambiguous return, bounded retries, partial multi-target effects, whole-file rollback,
live target drift, result/receipt type substitution, false productivity/native claims, and exact
qualification-source/output identities. Existing T1–T4 mutation, subprocess-crash, GUI and native
adapter tests are retained. This is same-author engineering evidence, not independent certification.

## F04 — harness trace indexing and counter-handle cleanup
Adding an actual collector trace moved the initial discovery record. A negative replay
fixture indexed the old position and raised KeyError instead of exercising replay rejection.
It now selects the discovery record by its declared kind. The original terminal failure is
retained. The new foundry's count-only SQLite connection also now closes explicitly; no
inherited runtime is changed. These are harness defects, not changes to expected outcomes.

## F05 — malformed foundry record errors
Additional rehashed malformed-record probes produced untyped TypeError/KeyError failures
for list-valued scenario IDs, malformed journal entries and incomplete target maps. The
new qualification record inspector now validates the relevant types and converts remaining
structural indexing failures into MMC_T5_RESULT_STRUCTURE. Seven regressions require typed
refusal; source/runtime T1–T4 and the original acceptance criteria are unchanged. The issue
was an input/error-surface gap, not a demonstrated permission bypass.

## Oracle chronology and evidence standing
The original program and T5 case meanings/milestones were frozen before new harness code.
The compact terminal projection corpus was serialized after exploratory runs, using the
manual seven-transition/ten-operation design and frozen case meanings; it is not a blinded
or independently generated oracle. Expected scenario outcomes were not rewritten to hide
failures. Every raw run is same-author evidence; final qualification is tied to exact
source bytes and complete terminal records.
