# Capability Layer T3 construction and review findings

T3-001: initial development imports requested clone from the wrong public package surface. Corrected
to the actual codec implementation; the initial smoke traceback is retained where captured.

T3-002: an initial crypto-negative test exposed MMCError (a ValueError subclass) being caught by the
cryptographic error normalizer, losing the precise strict-DER/high-S refusal. The explicit MMCError
branch now preserves typed refusals. This did not accept the invalid signature.

T3-003: replay repeatedly recompiled immutable plans. A large combined development run exceeded its
execution window and has no terminal success receipt. Exact-byte/evaluator-bound compilation and
projection caches were introduced. They do not cache current evidence eligibility or target state;
mutation/restart and no-effect tests preserve those boundaries. No performance claim is inferred.

T3-004 (substantive): an expired newer negative observation could be ignored while an older still-fresh
positive remained eligible. A pre-repair witness records EVIDENCE_SATISFIES_SELECTED_POLICY where the
oracle required INDETERMINATE. Recognized per-source stream sequence is now checked before freshness,
preventing that fallback. Equal-sequence conflicts block; known newer invalidation is not erased by age.

T3-005: standalone authority evaluation did not independently compare the request's policy root with
the supplied reader policy. A direct substitution test now requires MMC_T3_REQUEST_POLICY. The
controller already supplied its pinned policy; the pure boundary is now equally explicit.

T3-006: the first two-cohort regression requested a sorted-set API with an unsorted target list.
Corrected the test input ordering, not the expected behavior. Its failed run remains in evidence.

The unsupported streaming-exec invocation created no files and was not counted as execution evidence.
A following premature test invocation lacked its not-yet-created module; that failure is retained.
No failure history is rewritten as a pass. These are local engineering findings, not independent review.

T3-007: review found the standalone authority API accepted a string as a revocation iterable.
It now requires the exact sorted identifier list (the Python default empty tuple remains an explicit
convenience). Self-consistent malformed local journal events are normalized to a typed projection
refusal rather than leaking host KeyError/TypeError. These are admission repairs, not production
security certification. T3 known-answer case identities and expected status/refusal oracles were
retained while realization-derived roots/signatures were renewed; the earlier corpus is preserved.

Two combined qualification attempts exceeded the execution window after producing only T1/T2 group
records. A separately traced complete T3 invocation passed all 150 cases. The qualification runner
now exposes three source-bound test parts, verifies their exact disjoint identity union and terminal
receipts, and only then assembles the test stage. This is explicit repeatability accounting, not a
claim that the interrupted combined processes completed or a diagnosis of the host scheduling cause.

T3-008: an optional installed probe using system-site-packages inherited cryptography 43.0.0,
not the declared 46.x operational dependency, and its ambient environment had an unrelated missing
setuptools requirement. That exploratory workflow success is not accepted qualification. The final
probe requires 46.x inside the isolated prefix; exact genuine host distributions are copied with
hash inventories into a clean environment. This is not fresh dependency download/resolution evidence.
A documentation-only pause/resume API name was also corrected to the actual callable surface.
