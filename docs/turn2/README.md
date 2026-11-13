# MMC Capability Layer T2 — domain intelligence

Distribution `mosaic-migration-compiler 0.1.0a2`; explicitly selected profile **T2-D1**.
T1 compiler/package modules, original normative files, program constitution and known-answer
corpus retain their exact bytes. T2 is in a separate `mosaic_mmc_t2` package. The previous
source ZIP is retained under `baseline/` with its externally supplied SHA-256.

The four domain evaluators, finite dependency planner, lifecycle-edge interpreter, cohort routing
checker and retirement-model assessment are implemented. There is no live migration controller,
new key ceremony, actual revocation feed, authenticated observer, production adapter or native
P/PPI interpreter in this candidate. This is a local engineering candidate, not ratification.

Read `PROTOCOL.md` for frozen semantics; `DEVELOPER-GUIDE.md` for actual APIs; `ACCEPTANCE.md`
for exact scope; `SECURITY.md` and `FINDINGS.md` for assumptions/repairs; `REPLAY.md` for replay;
`REPLACEMENT.md` for the model/realization boundary; `TURN3-HANDOFF.md` for the next gate.

## What successful model evaluation means

* `MATCH_FOR_SUPPLIED_MODEL`: the finite declared relationship passed its installed predicates.
* `MODEL_RETIREMENT_CONDITIONS_MET`: the supplied snapshot satisfies the declared retirement model.
* `ADMISSIBLE_MODEL_PLAN`: one finite path satisfies the admitted state/order constraints.
* `COMPILED_WITH_RUNTIME_OBLIGATIONS`: successful lowering retains unresolved live obligations.

None means live eligibility, authenticated coverage, current permission or an executed migration.
A quiet producer is not fenced. An exhausted search budget is not a proof of impossibility.
A declared atomic phase still needs a qualified atomic/coexistence adapter in the real environment.
