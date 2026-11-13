# Capability Layer T1 construction findings and residual limits

## F001 — duplicated unittest discovery (repaired)
The first expanded run reported 165 successful executions. Inspection found that importing an
acceptance TestCase class into the boundary-test module caused five tests to run twice. These were
not 165 unique cases. The earlier raw log is retained. The import now references the module instead
of exposing an imported TestCase class; qualification independently verifies unique collected and
executed IDs against the source-bound registry. Later denominators supersede, not erase, this run.

## Scope findings, not completed features
- Four examples establish representation through one metamodel; they do not implement four domain engines.
- Actual state, observation credibility, current authority, completeness and fencing remain unresolved.
- Conditional/coexistence/exclusion planning, persistent control and effect adapters remain future work.
- Native P/PPI cannot be fabricated by a new local program schema; it stays NOT_BOUND.
- No known predecessor is silently modified; this package is a new migration-compiler workspace.
- Exact reproduction is scoped to the accepted frozen source and actual tested interpreter/environment.

Record any later failure or repair with exact inputs, source identity, terminal outcome and disposition.
No independent reviewer has approved this candidate.

## F002 — oversized diagnostics could escape the typed CLI boundary (repaired)
A valid-sized source with two long unknown field names triggered MMC_FIELDS, but the diagnostic
repeated both names and exceeded the canonical string budget while serializing the refusal. The
pre-repair command exited 1 with a traceback instead of the documented typed exit-2 response.
The diagnostic now retains counts and bounded samples. The regression exercises the actual CLI
and requires MMC_FIELDS, exit 2 and a bounded response. The earlier stderr and result are preserved.
This fixes reporting; no malformed model compiled or external effect occurred.

## F003 — source enumeration failure could omit files (repaired)
The first attempt patched os.scandir, but pathlib had cached its scanner: that attempt produced
two members and did NOT demonstrate omission. Its misleading provisional finding label is corrected
here and the raw attempt is retained. A second probe targets glob._StringGlobber.scandir and
reproduces the prior rglob enumeration branch; the denied scan is suppressed and a manifest-only ZIP
passes internal closure despite the fixture having a required file. Both attempts are preserved. Source
admission/build now use explicit scandir traversal and refuse scan/stat failures with MMC_SOURCE_IO.
The regression requires that refusal rather than a source archive. No delivered final package uses
the defective builder. Atomic filesystem snapshots/hostile administrator races remain unclaimed.

## F004 — CLI compile-to-verify framing mismatch (repaired before delivery)
After a provisional 179-test qualification and package build, a final end-to-end CLI probe showed
that redirecting `mmc compile` output into a file and using it with `mmc ir verify` failed: the first
command emitted an ABI response envelope, while the second expected a bare compilation. The CLI
now admits and strictly unwraps only its exact successful compile framing, then performs the same
full recompilation check. Bare library compilations still work; JSON ABI semantics do not change.
Three regressions cover the actual round trip and rejection of extra fields or integer truth.
The provisional source archive and receipt are retained as superseded pre-delivery evidence, not
final release results. T1 program/profile roots are unchanged; implementation/test roots are renewed.
