# MMC Capability Layer T4 — bounded agent interfaces and native workbench

Distribution **mosaic-migration-compiler 0.1.0a4 / T4-r001**; explicit extension **T4-I1**.
The T1/T2/T3 kernel, profiles, signatures and controller retain their bytes and meanings.
Capability Layer T4 provides a narrow investigation/submission cycle, a shared read-only interface,
native Tk views, explicit host collectors, a finite extension SDK, and scoped native readers.

Start with [USER-GUIDE.md](USER-GUIDE.md) or [DEVELOPER-GUIDE.md](DEVELOPER-GUIDE.md).
[PROTOCOL.md](PROTOCOL.md), [SDK-AND-ADAPTERS.md](SDK-AND-ADAPTERS.md),
[HOST-BOUNDARY.md](HOST-BOUNDARY.md), [SECURITY.md](SECURITY.md),
[ACCEPTANCE.md](ACCEPTANCE.md), [REPLAY.md](REPLAY.md), [REPLACEMENT.md](REPLACEMENT.md),
[FINDINGS.md](FINDINGS.md), and [SOURCES.md](SOURCES.md) specify the boundaries.

Eight agent cases are due here. The ninth due case, native P/PPI admission AC-REPRO-06,
is BLOCKED_NATIVE_DEPENDENCY, not satisfied by a local handoff or a refusal test. The
full program has 84 requirements and 100 cases. No end-to-end T5 result or productivity
study is implied by these interface tests. All release records are unsigned same-author
engineering evidence; public release remains NOT_CLEARED.
