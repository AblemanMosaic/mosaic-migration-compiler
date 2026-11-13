# T4-I1 interface and evidence semantics

## Selection and immutability
T4 is opt-in; `mmc-agent` and `mosaic_mmc_t4` select it. Existing `mmc`, `mmc-t2`,
`mmc-t3` and their model/receipt roots are not reinterpreted. T4 uses the existing strict
MMC JSON codec and SHA-256 over `MMC/T4/<domain>\0` followed by canonical body bytes.
A body and its root are separate; a self-consistent root does not establish recognition.
Supported domains are enumerated in `common.DOMAINS`. The source-bound T4 evaluator identity
is separate from the frozen T4 contract and includes the installed T4 Python/data files.

## Snapshot and reader
A snapshot contains a validated T3 plan, policy, migration and transition, supplied signed
observations, floor, revocations, and optional journal head. It is at most 2 MiB and 256
records. Structural inspection does not authenticate observation truth. A reader separately
pins the plan root, policy root, whole snapshot root and supplied time/uncertainty. The demo
helper derives these pins from the object and therefore is not an independent trust ceremony.

`assess_view` recomputes T3 evidence; it does not trust an imported assessment. It preserves
the T3 checks/quarantine/uncertainty, the original runtime guards, graph and planner witness.
Its evidence label means the procedure recomputed under the reader's recognition policy,
NOT that every supplied record was recognized or that testimony is objectively true.
The result expressly retains EVIDENCE_ONLY_NOT_OPERATIONAL_PERMISSION and NOT_EXECUTED.

## Work order
`make_work_order` selects exactly one unresolved claim. Claim-specific context includes source
references, accepted observer scope, reference payload, exact model/policy/cohort/targets,
current snapshot and evaluator, optional controller head, expected submission schema,
allowed content-addressed resource IDs, and a half-open deadline. It never copies the full
journal. Bounds: 256 KiB, 16 resource references, 1..3600-second requested TTL. A large
single claim may still be large; exceeding the limit refuses rather than omitting meaning.

The allowed-read list is a plan, NOT an I/O capability by itself. An actual host ReadSession
must enroll exact collectors and the externally accepted work root. No URL or filesystem
path is executable through a work-order document or the data ABI.

## Submission and host admission
A submission has exactly schema, work_order_root, record and notes. Notes are data up to
4096 characters. Review requires an independently supplied expected_work_root and rederives
the order; a rehashed authority expansion cannot substitute for the original order.
The signed record must match the exact scope, claim and subject. T3 verifies signature,
recognition, method, time, sequence and coverage. Invalid evidence is refused or remains
ineligible/quarantined. Negative recognized evidence may be valid for admission and must
remain negative in the resulting assessment. Review returns before/after computations but
writes nothing. It does not give the agent access to any signing key.

`AgentHost.admit` is a separate explicitly invoked host write: exact journal-head CAS,
work/snapshot/reader checks and signed-record review occur in one controller transaction.
Pending pre-effect work is cancelled using the existing T3 event rules when evidence changes.
No approval, commit, adapter execution or policy amendment is performed. Stale heads refuse.

## Receipts and replay
T4 view replay compares the complete exact canonical result to a fresh evaluation. Structural
receipt comparison is labeled IMPORTED_NOT_REPLAYED and preserves missing versus null.
Journal inspection checks the supplied T3 chain and reconstructs its projection under an
external policy root and optional floor. It does not establish actual host custody or replay
effects. Data-only handoffs are references requiring external decision, never native admission.

## Interface
Requests contain only schema `mmc.request.t4`, operation and arguments. `abi.OPERATIONS` is the
closed advertised callable surface; the CLI uses that same dispatch. Stdout is canonical JSON
plus one framing newline. Exit 0 means computation completed even for BLOCKED/INDETERMINATE;
exit 2 is a typed refusal. No data operation signs, fetches, registers code, approves, commits,
installs or publishes. Output schemas describe structure, not authenticity or decision correctness.
