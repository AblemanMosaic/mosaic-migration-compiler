# MMC foundation T1 — normative wire and lowering contract

This profile is finite structural compilation, NOT migration execution. The program freeze governs
all six turns; T1 implements only the foundation. No external/native authority is acquired.

## Encoding and identity
MMC-JSON-I64-UTF8-T1 admits exact Python-independent JSON null, booleans, signed 64-bit integers,
Unicode scalar strings, arrays and string-keyed objects. It refuses floats, NaN/Infinity, duplicate
keys, lone surrogates, subclass/foreign values, cycles and excessive size/depth/nodes. UTF-8 is strict,
without BOM. Canonical text has no whitespace outside strings, code-point-sorted keys, unescaped
non-ASCII scalars, JSON control escapes and no slash escaping. Arrays are ordered. No NFC/case or
line-ending normalization occurs in strings. Raw author input may have whitespace/alternate valid
JSON escapes; canonical-read mode additionally requires exact canonical bytes. Framing newline is
outside the value. Negative zero is parsed as zero; canonical-read rejects the original -0 spelling.

SHA-256 commitments use ASCII `MMC/T1/` + a fixed allowed domain + NUL + canonical(body).
Domains: program-freeze, foundation-profile, canonical-model, compiler-realization, workflow-ir,
compilation-receipt, source-inventory, evidence-run, package-inventory. Domains cannot be user code.
Self-declared roots are excluded through explicit body/envelope separation. No private keys, signing,
authentication or independent trusted timestamp is implemented. Callers must pin accepted roots.

The selected foundation profile body binds the exact program root, foundation contract, declarative
metamodel, model JSON Schema and THIS document. It is separate from runtime code identity. Runtime
identity binds the installed mosaic_mmc .py and data files in POSIX-relative path order, excluding
__pycache__; distribution metadata and local filesystem paths are not in this identity.

## Input model
`schemas/model.t1.schema.json` defines the closed shapes. Every object has id, kind, provenance,
and attributes. IDs are ASCII `[a-z][a-z0-9_.-]{0,95}`; tokens use the explicit schema pattern.
Objects, initial/from/to states, and declared set fields normalize by IDs or canonical scalar bytes.
Duplicate members refuse before sorting. Predicate item arrays retain their source order. Provenance
is supplied attribution, never authentication. Observation values/status/intervals remain declarations.
A UNKNOWN observation has null value. Time bounds are both null or ordered nonnegative integer times.
References are globally unique, resolved, and kind checked according to metamodel.json.

Every Effect target is in its Transition's affected set and cohort members; expected_before/after
must equal that transition's literal state labels. One Effect belongs to exactly one Transition.
An Effect operation must be listed in its named Authority declaration; this only checks declaration
consistency. It does not recognize that Authority. Every Obligation is attached to a transition or
one of its effects. Cohort scope includes its members and its declared flows; a transition cannot
use an obligation about a different cohort or target. Each observation used by an obligation is
about the obligation's exact subject. Evidence referenced by an observation is about that subject.
Cohort member/flow declarations cannot prove that the real system has no other actors.

## Compilation
Resolve the exact installed profile reference first, then validate and normalize all declarations.
REQUIRES dependencies order Transition objects. Before and after differ and every dependency pair
is unique. Stable Kahn ordering uses a lexicographic ready queue. Any residual order cycle refuses
with residual nodes (which can include nodes downstream of a cycle; not a minimal-cycle proof).
Two transitions touching the same target must be explicitly transitively ordered; arbitrary
lexicographic scheduling cannot substitute for that dependency. All touched targets require initial
states. Simulate declared literal from/to states in the admitted order; mismatches refuse. This is
syntactic state compatibility, NOT physical-state evidence or a general planning solver.

The IR retains the entire normalized model plus ordered transition instructions. Each instruction
contains source references, pre/post state, direct predecessors, policies, source obligations,
normalized effect descriptors and generated guards. Applicable policy guards include explicit step
policies, selected cohort policies, affected asset policies and policies on flows in that cohort.
Source obligations and effect-required obligations lower with evidence classes, authority scope,
freshness and coverage requirements. Every step gets unresolved current-authorization and
fresh-evidence guards. Every effect adds unresolved adapter-binding and live-precondition guards.
RETIRE additionally gets all seven categories in FOUNDATION-CONTRACT. Nothing in T1 discharges these
runtime guards. This is obligation generation, not the T2/T3 retirement evaluator.

Conditions: literal exact bool, eq(observation, scalar), all, any, not. Only literal boolean algebra
is constant folded. eq is ALWAYS RUNTIME_REQUIRED even if an observation supplied a current-looking
value. A false static guard creates STATIC_CONDITION_FALSE diagnostics and compilation status
COMPILED_WITH_STATIC_BLOCKERS; otherwise COMPILED_WITH_RUNTIME_OBLIGATIONS. Both statuses say
eligibility=NOT_EVALUATED, authority_effect=NONE, effects=NOT_EXECUTED. Declared current states never
implicitly discharge obligations. Effect adapter names are descriptive tokens, not import paths.

IR and receipt commit model/profile/compiler/IR roots with separate domains. They contain no
ambient time, machine path, hostname, random seed, or network state. Source replay revalidates and
recompiles using the selected installed compiler and byte-compares the whole candidate. Merely
rehashing edited output cannot supply a genuine compilation relationship. No generic theorem of
semantic equivalence is claimed.

## Budgets and unsupported work
Limits are exactly those in FOUNDATION-CONTRACT. Predicates additionally permit at most sixteen
children per all/any. At most 128 transitions, 512 objects and 512 items per declared set. Input
bytes 2 MiB, output bytes 8 MiB; JSON depth 32 and nodes 50,000; strings at most 65,536 UTF-8 bytes.
No arbitrary cycles, coexistence solver, conditional-dependency planner, authenticated observers,
controller journal, adapters, live clocks, signatures, effect calls or native P/PPI admission exists
in T1. Future profiles require explicit versioned admission, not fallback coercion.

## CLI and ABI
Library compile/validate/replay functions take finite in-memory data. The read-only JSON ABI accepts
exact schema, operation, arguments. Supported operations are model-validate, compile, verify-ir,
capabilities and program-inspect. Unknown operations and extra arguments refuse. CLI operations only
read caller-selected regular local files or size-bounded stdin and write canonical results to stdout.
No file output, fetching, signing, installing, trust update, migration action or plugin operation is
exposed. Shell redirection is the caller's action. Success exits 0, typed refusal exits 2. A compiled
static blocker may exit 0 because compilation completed; it is explicitly not migration approval.
