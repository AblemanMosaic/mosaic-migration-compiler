# T3-O1 operational protocol

## Representation and identities

Use the unchanged T1 canonical JSON grammar: exact JSON types, signed 64-bit integers, Unicode
scalars, no floats or duplicate keys, explicit byte/depth/node budgets. No JCS equivalence is claimed.
T3 digests are SHA-256 over ASCII `MMC/T3/` + declared domain + NUL + canonical value.
Domains are contract, policy, plan, context, request, statement, assessment, event, adapter,
realization, ledger and test. An operational plan commits its exact T2 bundle/compilation/model,
reader policy root, T3 contract and installed evaluator source/data identity. Recompilation is
required when admitting a plan. A self-consistent attacker-created hash is not reader recognition.

The operational policy normalizes observer and jurisdiction row order. Set-valued member arrays
must already be sorted and unique. Recognized observers have exact permitted claims, subjects,
cohorts, methods, evidence classes and model-authority affiliations. Every configured jurisdiction
requires its unique admitted-key threshold. Distinct keys do not imply independent people.

## Signed statements

Algorithm: **ECDSA-P256-SHA256-DER-LOW-S**. Keys are compressed SEC1 points, lower-case hexadecimal,
validated on secp256r1 by the optional cryptography backend. Public statements contain no private key.
The signed message is `MMC/T3/SIGNED-STATEMENT` + NUL + canonical statement body. Signatures are strict
canonical ASN.1 DER; r is in [1,n), s in [1,floor(n/2)]. Signing uses the backend's deterministic
ECDSA mode and explicitly refuses unsupported backends. This is a separate profile from prior DKN
Ed25519 records; no old key/signature is reinterpreted.

An observation or approval body binds migration, exact plan and policy, transition, cohort, complete
target set, signer, half-open validity interval, sequence, and a closed typed payload. The public
statement root commits body, algorithm and signature. Approval additionally commits the exact
request and evidence context, jurisdiction and ALLOW/DENY decision.

## Recognition, freshness and negative evidence

Time is supplied as integer `now` and nonnegative `uncertainty`; the entire [now-u,now+u] interval
must fit inside [issued_at,expires_at). Age equality is accepted; uncertainty above policy limit
blocks. No wall clock or external lookup occurs inside a court. Controller mutation times cannot
regress below its journaled clock floor; this is not a trusted clock service.

Every supplied signature is verified. Malformed material refuses. Valid but irrelevant, unrecognized,
revoked, below-floor, superseded or stale statements remain ineligible with reasons. For recognized
streams (signer, claim, subject) in this exact scope, the highest known sequence is determined
BEFORE freshness eligibility. Thus expiry of a newer negative statement cannot revive an older
positive one. Equal-sequence equivocation and applicable conflicting values block. Explicit newer
statements can supersede older statements under this profile; the complete history is retained.

Coverage requires recognized COVERAGE testimony over the exact modeled cohort roster. This establishes
that the selected observer asserted complete coverage of that roster, NOT absence of unmodeled actors.
Foundation expressions are evaluated from scoped recognized observations and their admitted evidence
classes/model authorities. Dynamic domain records cannot rewrite locked requirements: token audience,
identity query, source inventories, policy rules and normative retirement scope remain pinned.
T2 domain and retirement predicates are recomputed, not inferred from submitted PASS reports. Where
a record has a time field, the conservative upper reader time is supplied to its evaluator.

Evidence statuses: BLOCKED, INDETERMINATE, EVIDENCE_SATISFIES_SELECTED_POLICY.
Authority statuses: BLOCKED, SCOPED_APPROVALS_SATISFIED. All configured jurisdictions must match;
any applicable fresh recognized denial prevents approval. A duplicate key never increases a threshold.
These results do not themselves grant effect permission or institutional authority.

## Journal and projection

Explicit create-only local SQLite database; application format marker; DELETE journal mode,
synchronous FULL, explicit BEGIN IMMEDIATE writes. Events bind sequence, previous event root, type
and canonical payload. Capacity: 4,096 events, 64 migration instances, 256 observations per active
migration. Journal replay reconstructs the projection and rechecks signed inputs, plan identity,
recorded evidence/authority at dispatch and exact result correspondence. It makes no adapter call.
External checkpoint `{sequence,root}` may be supplied when opening; a database predating or conflicting
with it refuses. Without a protected external checkpoint, whole-database rollback remains possible.

Pure compilation and replay projections may be memoized only by exact immutable input bytes and
current evaluator identity. Live target state, current eligibility and new evidence are never cached
through that mechanism. Caller data and cached projections are detached copies.

## Effect lifecycle

PREPARED -> APPROVED -> DISPATCHED -> APPLIED.
DISPATCHED can yield UNKNOWN, NOT_APPLIED or RECOVERY_REQUIRED; UNKNOWN must reconcile before retry.
PREPARED/APPROVED/NOT_APPLIED can be cancelled. Partial outcomes retain reservations and require an
explicit later recovery design; no automatic cancellation/revision hides an unresolved effect.

Prepare changes the controller journal only. It binds exact current target states/versions, proposed
states, monotone security floors/revoked-set union, selected adapter, cohort, plan, evidence context,
expiry, direction and a unique operation ID. It validates the explicit model effect adapter/scope.
Only the chosen sequential T2 witness is executable here. Simultaneous multi-transition phases are
refused with MMC_T3_ATOMIC_PHASE_NOT_BOUND; a valid model phase is not a distributed transaction.

Approval requires actual signatures over that exact request. Commit recomputes evidence and approval,
checks expiry and actual target preconditions, then durably records dispatch intent BEFORE calling
the target. A second controller transaction serializes final rechecking and dispatch against cooperating
controller updates. Target-state compare-and-swap is atomic inside the separate target database.
A missing acknowledgment is UNKNOWN, never a false no-effect result. Reconcile reads the target's
idempotency ledger and records the established outcome; it does not apply the request again.

The selected target adapter is **SimulatedStore**, local SQLite only. Target mutation and its operation
ledger entry commit in one transaction. Repeating an identical operation returns the recorded result;
reusing its ID with other bytes refuses. Proven absence from THIS local ledger permits a bounded
retry under the same still-valid request/approval (maximum three attempts, policy may be stricter).
This is a local qualified property, not distributed exactly-once execution.

A compensation uses a NEW request and approval, explicitly reverses the latest accepted transition of
one cohort only when its model declares restore-prior-state, and refuses completed successors that
depend on it. It preserves current security floors and revocations instead of restoring old security
state. Other cohorts are unaffected. Pause, plan revision and new evidence invalidate pending approvals
where the outcome is not ambiguous. No live policy amendment is implemented; select a new reader policy
through separately reviewed configuration, not untrusted data.

## Limits

Trust the host, code, filesystem and configured recognition roots. No network, production adapter,
key storage, automatic watcher, global revocation feed, secret scrubber, physical power-loss proof,
or universal source-discovery guarantee. Supplied time is not measured elapsed time at a remote effect.
No claim of hostile-administrator resistance. Authority effect NONE means no jurisdictional promotion;
explicit controller/target SQLite mutations are real local filesystem effects.

Revocation-floor identifiers may include exact public-key encodings and modeled opaque revocation IDs.
Only an exact key encoding disables a statement signer; opaque IDs retain their modeled security-floor
meaning and are never inferred to identify another key. Signed timestamps are issuer claims checked
under the supplied clock, not independent timestamp-authority evidence.
