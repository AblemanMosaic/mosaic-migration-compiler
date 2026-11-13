# Capability Layer T5 — full local migration qualification

Distribution **mosaic-migration-compiler 0.1.0a5 / T5-r001**. Profile **T5-Q1** is a
finite qualification foundry, not a new production workflow language or an authority grant.
T1–T4 semantics are retained. The original 84 requirements and 100-case acceptance catalogue
remain frozen; this turn addresses W12 and the ten AC-E2E cases.

Read `PROTOCOL.md` for the scenario contract, `SCENARIOS.md` for exact scenarios,
`SECURITY.md` for scope/assumptions, `REPLAY.md` for commands, `FINDINGS.md` for retained
failures and `ACCEPTANCE.md` for requirement/case correspondence. The measured final counts
and release hashes are in the external verification and clean-replay receipts; prose is
not a substitute for completed source-bound execution records.

The foundry invokes actual T1/T2 compilation, T3 signed evidence, courts, Controller and
SimulatedStore, and T4 collectors, bounded agent admission, job observer and journal views.
A complete primary run goes through source capture, explicit accepted-model construction,
agent-assisted missing-coverage admission, prepare, canary, coexist, fence, reconcile,
cutover and retire. Host approval is separate. The job observer checks the simulated
legacy producer before and after fencing. No external discovery or real token issuance
is performed; the identity profile interprets modeled token/key relationships, while
actual P-256 signatures authenticate the qualification observations/approvals.

Run `mmc-foundry list` for scenarios; `mmc-foundry run safe-token` creates temporary local
SQLite state and prints its signed-fixture transcript. Nothing is submitted to production.
`inspect` checks a pinned record/journal without target effects. `replay` recomputes a
scenario in **new temporary databases**; it does not reissue operations to the original store.
The runtime core remains independently usable without the foundry, GUI or native P/PPI.
