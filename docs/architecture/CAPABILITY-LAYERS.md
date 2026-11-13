# MMC capability layers

MMC is organized into six durable capability layers. `T1` through `T6` are stable
compatibility identifiers; they are not build numbers and they do not require every runtime
migration to execute a literal six-step pipeline.

| Compatibility ID | Capability layer | Scope |
|---|---|---|
| T1 | Foundation | Program constitution, migration metamodel, canonical IR and deterministic compiler |
| T2 | Domain intelligence | Domain profiles, dependency planning, lifecycle and retirement semantics |
| T3 | Operational spine | Durable controller, evidence and authority courts, effects, reconciliation and recovery |
| T4 | Integration surfaces | Agent protocol, CLI, workbench, SDK, collectors and interoperability |
| T5 | Qualification | End-to-end simulations, failure witnesses, replay and fidelity qualification |
| T6 | Delivery and research handoff | Packaging, operator guidance and comparative-study materials |

Layer dependencies describe semantic prerequisites. They do not turn compilation into authority,
make qualification a runtime effect, or imply that delivery evidence grants production admission.
Consumers select explicit versioned operations and schemas from the layers they use.

## Stable identifiers and legacy paths

The public ABI retains identifiers such as `mmc.request.t1`, `mosaic_mmc_t2`, `T3-O1`, and the
`tools_t*`, `tests_t*`, `docs/turn*`, and `provenance/turn*` source paths. Renaming those identifiers
would break compatibility and historical evidence without improving semantics. In those retained
paths and frozen predecessor records, `turn` is a legacy construction noun only; the canonical
product noun is **capability layer**.

The frozen JSON contracts retain `turn` and `turns` as deprecated exact aliases of the canonical
`capability_layer` and `capability_layers` fields. New consumers should use the canonical fields;
the aliases exist only to preserve the v0.1 ABI and frozen predecessor tooling.

## Release convergence

Release Convergence is the successor integration, qualification and publication line implemented
under the legacy `t7` source namespace. It is not Capability Layer T7 and does not extend the
six-layer program. Release Convergence may repair realizations, renew exact bindings and assemble a
release, but it cannot silently amend the capability-layer contracts or their authority ceilings.

The terminology amendment is recorded under `provenance/` with predecessor and successor program
roots. Historical source requests and predecessor manifests retain their original wording.
