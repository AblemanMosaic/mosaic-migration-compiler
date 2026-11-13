# Capability Layer T5 acceptance and requirement correspondence

The original programme root, 84 requirements and 100 acceptance cases remain unchanged.
AC-E2E-01 through AC-E2E-10 are due now. Each maps to a separately named complete scenario test
and a separately executed, source-bound scenario transcript. A correct refusal has a paired safe
continuation; a controller that blocks everything cannot pass.

Earlier scoped cases must replay. AC-REPRO-06 remains BLOCKED_NATIVE_DEPENDENCY; AC-REPRO-05 and
AC-REPRO-08 are due in Capability Layer T6 and remain NOT_RUN. A successful local Capability Layer T5 gate therefore has
97 scoped passes, one blocked native case and two later cases—not a full public release approval.

The eight W12 requirement bindings are checked by `tools_t5/check_model.py`. W12-R06 supports
only the environment actually run; other targets and independent review remain unestablished.
W12-R08 supports an executable claim-boundary check, not an independent participant experiment.
Hash/symbol/test traceability is not a semantic refinement proof. Stages are unsigned, same-author
records; a dishonest fully privileged host can forge records. No native P/PPI state is invented.

Current measures are in external receipts; this file states gate conditions rather than asserting
unexecuted test counts. T6 remains consolidation and research handoff, not another feature expansion.
