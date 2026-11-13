# Capability Layer T2 development review and retained findings

Same-author findings, not independent certification. No original T1 runtime, contracts or acceptance
expectations were changed to repair a T2 defect. Raw evidence is under evidence/turn2/development.

* T2-F01: the retirement example imported clone from the wrong public module. It now imports the
  actual codec function. The original example and failing terminal output are retained.
* T2-F02: a delegation test shallow-copied its parent's scope list; mutating the child also widened
  the parent. The intended negative outcome was never changed. Deep-copying the test fixture
  restores the actual attenuation test. Original source and failed test output are retained.
* T2-F03: malformed transition IDs could reach dictionary membership as lists, raising TypeError.
  Exact string admission now precedes lookup; malformed CLI/API references return typed refusal.
* T2-F04: the initial overlay accepted a workload record that omitted all model workers. Scope
  validation now requires exact worker/asset coverage for those domain profiles, not a subset.
  The pre-repair compiled result and post-repair refusal are recorded.
* T2-F05: the initial retirement model checked an Authority reference's kind but not its declared
  retirement capability. It now requires the model's `retire` operation, separately from the
  approval statement's `RETIRE` action. This still does not authenticate or recognize that authority.
* T2-F06: a phase could reuse an ordinary transition's action identifier, producing two different
  actions under the same displayed ID. Phase IDs now cannot alias transitions. The original
  witness with duplicate action names and the regression are retained.

These repairs narrow defective realization behavior to the frozen T2 semantics. There is no
retrospective claim that prior runs passed or that model completeness proves operational safety.
