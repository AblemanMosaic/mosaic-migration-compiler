# Agent interface coverage and maturity

`mmc-product protocol` describes the implemented `mmc.agent.v1` surface. The retained T1–T4
dispatchers remain available unchanged, while `mmc-product request` gives agents one closed request
shape, one response/refusal envelope, explicit effect declarations, stable operation IDs, and
machine-exported schemas. `mmc-product schema all` exports the request and response schemas,
the installed layer schema graph, and its SHA-256. Every reference is local to its exported document;
recursive predicates and arbitrary JSON values retain local references. This is a self-contained
structural graph, not a proof of signature validity, recognition, scope, or exact replay.

| Surface | Implemented capability | Boundary |
|---|---|---|
| T1: `mmc request`, `mmc.request.t1` | Five operations: validate, compile, exact IR verification, capabilities, program inspection | Pure supplied-model computation |
| T2: `mmc-t2 request`, `mmc.request.t2` | Nine operations: profiles, assessment/replay, planning, retirement, routes, lifecycle, compilation/reverification | Supplied-domain assessments and plans |
| T3: `mmc-t3 request`, `mmc.request.t3` | Six operations: capabilities, plan, statement verification, evidence/replay, scoped approval assessment | Read-only decisions; signing backend needed for signed evidence |
| T4: `mmc-agent request`, `mmc.request.t4` | Fourteen operations: inspect/assess/replay/compare, work orders and submission review, journal views, profiles, records, installed readers and handoffs | Read-only agent data interface |
| T3/T4 Python host APIs | Controller lifecycle, evidence admission, enrolled collectors, create-only export, finite extension qualification | Trusted host selects resources, keys, code and mutations |
| T5: `mmc-foundry` | Catalogue, run, inspect and replay ten fixture scenarios | Temporary local simulation; separate CLI, no request dispatcher |
| T7: `mmc-product request`, `mmc.agent.v1` | 47 retained-layer, product, integration, negotiation, schema, transport discovery and migration operations | Uniform JSON framing; effects declared per operation |
| Effect adapter v1 | `descriptor`, `snapshot`, `lookup`, `apply`; effect request and ledger reconciliation contracts | Trusted host objects only; simulator and disposable SQLite profiles; no production profile |

The shipped application ABIs are versioned JSON interfaces. There is no native binary ABI.
Agent requests use exact closed key sets and the strict MMC JSON value grammar; outputs are canonical
JSON. The uniform path always returns `mmc.agent-response.v1`, including request-validation refusals,
and uses exit 0 for a completed operation or exit 2 for a refusal. A successful computation can still
report a blocked or indeterminate domain result, so consumers must inspect the nested result.

The T1 workflow IR has guards, source references, predecessor ordering, state transitions and effect
descriptors. T2 adds selected domain assessments, planner witnesses, routes and retirement checks.
T3 pins a plan to compilation, policy and evaluator identities, then creates effect requests with
scope, preconditions, expiry, floors and revocations. Exact recompilation and point-of-effect checks
remain necessary. No current IR lowers arbitrary migrations to platform executors; the controller
accepts a host-selected `EffectAdapter`, validates a closed descriptor profile, binds modeled effects
to that profile, and still requires a sequential execution witness. The shipped real adapter is
limited to a disposable local SQLite workload.

The agent surface covers inspection, reasoning, proposal, evidence review, dependency probes, and a
qualified disposable effect workflow. It does not provide full operational automation against an
external production target. Adapter construction remains a trusted Python host seam; collectors cover
explicit selected resources; installed reader/profile qualification is finite; nested layer value
schemas are bundled in the installed product and connected by local references. Known layer structures
are exported in `$defs`; result fields without a more specific layer schema use the explicit strict
JSON value grammar. Cross-field identity, signatures, scope and replay remain native runtime checks.
The runtime's byte, node, depth, and UTF-8 byte limits are published as schema extension metadata,
since standard JSON Schema cannot express all of those aggregate limits.

Use `protocol.negotiate` through the generic request command with exact argument keys `protocols`,
`required_operations`, and `required_features`. It returns `COMPATIBLE` with a selected protocol only
when a supported version satisfies every requested operation and feature. `INCOMPATIBLE` carries the
missing requirements. Negotiation never grants authority or enrolls an adapter. Existing operation IDs,
arguments, results and effect classes are stable within a protocol major. Breaking changes require a
new protocol major; deprecation must announce a replacement and removal major while retaining the
current major. Clients tolerate new operation IDs by requesting only their required subset.

The installed `mosaic_mmc_product.conformance.run_conformance()` runner executes effect-free positive
and negative protocol cases, including closed arguments for every operation. Layer vectors and real
effect qualification remain separate legs. `python tools_t7/export_agent_schemas.py` checks the source
schema bundle; `--refresh` deterministically refreshes it after native schema regeneration.

The out-of-process local adapter transport is implemented as `mmc.adapter-transport.v1`: fresh
private-pipe authentication, exact code/target enrollment, bounded IO, deadlines, cancellation,
process cleanup and ledger reconciliation. `transport.describe` discovers its contract;
`migration.verify-target` exercises the enrolled SQLite target in a disposable database.
This is a cooperative local process boundary; remote transport and an OS sandbox are separate profiles.
Qualify a production deployment only after identity, jurisdiction, credential custody, rollback,
and power-loss gates are bound.
Establish Linux/Windows/macOS replay evidence, installed-wheel examples, adversarial concurrency and
resource-bound tests, independent review, and comparative operator-effort measurement. Those are
separate obligations; the protocol manifest keeps their absence inspectable.
