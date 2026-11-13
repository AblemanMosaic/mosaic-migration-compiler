# MMC T2-D1 — domain predicates, finite planning, lifecycle/retirement

Status: experimental, additive Capability Layer T2 interpretation, frozen before implementation. Program and T1
semantics stay pinned. Runtime package mosaic_mmc_t2 consumes the unchanged mosaic_mmc foundation.
This is not a native P/PPI implementation or live controller.

## Exact representation and trust boundary
Use the unchanged T1 canonical JSON grammar; objects are closed. Inputs are bounded to 2 MiB;
outputs to 8 MiB and the T1 node/depth budgets. Domain arrays are finite. Input record array order
is significant in request hashes; set-valued attributes are compared as sets. Foundation objects
normalize using T1. No imports, expressions, network calls or clocks from documents. All times
are caller-supplied integer instants. Intervals are half-open [start,end); age <= max_age.
New hashes use SHA-256('MMC/T2/' + domain + NUL + canonical(value)) for closed domain names.
Accepted profiles are pinned installed schema/protocol contracts; hashing establishes identity,
not truth. Profile reports bind exact request, contract and realization. Report replay recomputes.

Positive reports say MATCH_FOR_SUPPLIED_MODEL, never permission. Contradictions say BLOCKED_FOR_
SUPPLIED_MODEL. Missing nullable facts say INDETERMINATE unless a known blocker already exists.
All return operational_eligibility=NOT_EVALUATED, evidence_authentication=NOT_PERFORMED,
authority_effect=NONE, effects=NOT_EXECUTED. Supplied approval/key/coverage declarations are not
cryptographic witnesses. T3 must authenticate/recognize evidence and mediate effects separately.

## Four application profiles
Identity: finite issuer/audience/scope/subject and parent-delegation relationships. A child must
name its parent's subject as issuer, attenuate scopes/audience/lifetime and follow an admitted
issuer-key pair. The root issuer must equal the reader-selected issuer. Reject cycles/unknown
parents, excess depth, malformed intervals, duplicate IDs and successor-key cycles/cross-issuer
links. Historical consistency at issuance is separate from present acceptance: retired keys can
retain historical consistency, revoked-after-issuance records do not retroactively become forged;
current acceptance requires accepted_keys and nonrevocation/nonretirement/time validity on every
chain member. No cryptographic token format, signature validation or external revocation fetch.

Storage: exact finite item and replica inventories, explicit COPY/RETAIN/ISOLATE/DELETE disposition
for every source item, optional rejection of unexpected destination items. COPY requires identical
digest and schema, preserved readers/writers/purposes/minimum retention and holds. Retained data
needs its legacy reader; isolated data needs fencing and preserved hold/retention. Deletion requires
expired retention and no hold. Both inventories require declared consistency; destination sequence
cannot precede source. Destinations must satisfy declared custody/residency/replica minima. Multiple
replica IDs do not prove independent failure domains or real availability. Hashes are inventory
claims, not verification of unavailable payload bytes. No arbitrary schema transformation inferred.

Policy: finite exact subject/action/resource/purpose keys, no wildcards. DENY overrides ALLOW.
Duplicate identical rules are refused. Effective allows combine consent requirements by OR and
minimum-retention by maximum; allowed authorities are exact sets. New effective permissions,
relaxed consent/minimum-retention and changed authority sets are listed as change commitments.
Caller-selected accepted_change_roots may acknowledge them in the model; actual scoped current
authorization is still a runtime obligation. Every new purpose must be covered by supplied consent;
missing consent is unknown. Required purposes must remain supported. No universal policy solver.

Workload: declared legacy code or resume version can produce future legacy writes even when idle.
Fencing/termination/upgrading/drainage dispositions have explicit consistency checks. Outstanding
writes block drainage until disposed; checkpoints must explicitly match a compatible target runtime.
Suspension alone is never drainage. All workers are the supplied inventory, not discovered exhaustively.

## Finite planner
Consumes a validated T1 model plus planning.t2 input. Maximum 16 transitions and 8192 visited states.
Foundation Dependencies remain strict order; extra conditional orders use explicitly supplied facts.
Unknown facts remain unresolved; never infer false from absence. COEXIST is state implication
(left state requires right state) at initial and every proposed state. EXCLUDE forbids simultaneous
matching states. Atomic phase groups are explicit disjoint same-cohort simultaneous transitions with
nonoverlapping target writes and no strict order inside them. MODELED atomicity adds an unmet adapter
obligation; it is not proof the real substrate can execute atomically. Strict order SCCs are unsatisfiable,
not cured by grouping. Mutual coexistence SCCs can be resolved only by a declared legal phase.
Deterministic breadth-first finite search checks exact pre/post state and constraints after each action.
It emits one canonical witness (stable lexical tie break, not an optimality/safety ranking). Exhausting
the full finite search proves UNSATISFIABLE_FOR_SUPPLIED_MODEL; hitting the budget is INDETERMINATE_
SEARCH_LIMIT, not unsatisfiable. Conditional unknowns yield INDETERMINATE_CONDITIONS. Dependencies,
cohort scopes and requirement-linked diagnostics remain in the result. No universal discovery claim.

## Lifecycle and cohort routes
Main sequence: DRAFT -> MODELED -> COMPILED -> READY -> CANARY -> COEXISTING -> DRAINING -> FENCED
-> RECONCILED -> RETIRED. Side states BLOCKED/PAUSED/INCONCLUSIVE retain one exact resume_from.
RESUME returns only there. COMPENSATING leads to RECOVERY_REQUIRED, which remains terminal to the
T2 interpreter pending a T3 recovery decision. RETIRED is terminal. Security floors cannot decrease;
previous revoked identities must remain revoked. Checking a permitted edge proposes state only.
Retirement is assessed separately; an allowed RECONCILED->RETIRED edge still needs retirement and
runtime authorization/evidence/adapter guards. Route input must name each supplied model cohort
exactly once, retain its use case and exact role/member lists, and distinguish legacy/new versions.

## Retirement requirements
Derive producers/workers/consumers/assets from the selected T1 cohort, Actor roles, and all legacy
Flow endpoints/assets in that cohort. Snapshot rows must exactly cover each required class. A worker
may also be a producer and the two records must agree on fencing/resumption capability. Require all
legacy producers fenced, all legacy-capable resumable workers disposed, no pending writes, accepted
persisted-state disposition, and every required consumer new-ready. Missing/nonmatching IDs are
structural refusals. Retention/holds, scoped declared approval, observation coverage/time and recovery
floor/revocation nonregression are checked as supplied facts. Quiet activity alone cannot pass.
Positive status is MODEL_RETIREMENT_CONDITIONS_MET; operational eligibility is still NOT_EVALUATED.

## Compilation overlay
compile_domain(model, planning, assessments, routes, retirements) reuses T1 validation and guards,
retains T1 model/profile identities, derives a T2 plan and source-linked domain guards. Each assessment
binds exactly one selected domain profile and transition; subject/cohort references are cross-checked.
Every transition must have a domain assessment of the model's selected domain; RETIRE transitions
also require an exact retirement snapshot and all cohort routes are required. Domain success cannot
discharge T1 runtime guards. Planner-generated simultaneous phases lower into grouped instructions;
no change to the T1 IR is misrepresented as a T1 compilation. Exact recompile verification is required.

## Compatibility and exclusions
T1 code/data and known answers are unchanged. T2 is explicitly selected by separate API/CLI and
schema/profile roots. The old mmc CLI remains T1; mmc-t2 exposes the extension. No automatic upgrade,
live authentication, effect execution, key custody, signing, network, GUI, durable controller or
native P/PPI admission. Tests establish bounded semantics, not independent security or productivity.
