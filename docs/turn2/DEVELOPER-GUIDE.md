# Using the explicit T2-D1 extension

## Python API

```python
from mosaic_mmc import decode
from mosaic_mmc_t2 import compile_domain, verify_compilation
from pathlib import Path

bundle = decode(Path("examples/t2/identity.json").read_bytes())
compiled = compile_domain(bundle)
assert compiled["body"]["operational_eligibility"] == "NOT_EVALUATED"
# Demonstration pin only. Production readers obtain their pin independently.
check = verify_compilation(bundle, compiled,
    expected_model_root=compiled["body"]["model_root"])
```

`assess_profile(profile_reference(name), record)` accepts one of identity/storage/policy/workload.
`replay_assessment(ref, record, receipt)` recomputes and compares the entire receipt.
`plan(model, planning)` produces a finite witness, explicit unsatisfiability or uncertainty.
`assess_routes(model, routes)` binds each cohort's exact use case and member-role lists.
`assess_retirement(model, record)` derives required inventory from the model; omitted rows refuse.
`assess_lifecycle(record)` checks a proposed edge, not a journal transition or operational effect.

The compiler bundle contains exactly schema, model, planning, assessments, routes, retirements.
Each assessment names id, profile_ref, transition, subject and record. Every transition needs
its model-domain assessment. Each RETIRE needs its own scoped retirement record. All supplied
negative/unknown assessments are preserved as blockers; no submission of a previously computed
PASS report substitutes for source records. The original T1 runtime guards remain unresolved.

## Profiles

Identity uses modeled token and key records, exact issuer/audience/subject/scope and attenuation,
not a particular OAuth/JWT implementation. A key's recorded retirement/revocation is interpreted
at issuance and evaluation time separately. No token signature is verified by this profile.

Storage compares inventory digests/schema and declared replica/custody/residency information,
with explicit persisted-state disposition. It does not read unavailable object bytes, inspect
real storage, or prove that replicas/administrators are independent. COPY preserves declared
reader/writer membership; it is not a complete destination access-policy authorization check.

Policy is a finite exact-key allow/deny model, not a generic language such as Cedar or Rego.
Widening hashes must be explicitly acknowledged in accepted_change_roots for a positive model
result. That acknowledgment is not authenticated approval and leaves current authorization open.

Workload interprets suspended/resumable legacy workers, outstanding writes and explicit checkpoint
compatibility pairs. Silence cannot imply drainage. Independent observers/coverage remain T3 work.

The retirement approval record uses operation `RETIRE`; the model Authority must declare the
capability token `retire`. Their distinct schema roles are intentional. Times are supplied integers,
validity intervals are half-open, and age equality is accepted. No clock is read inside an evaluator.
Observed freshness and approval are still declarations; not live authority evidence.

## Planner limits and meaning

Maximum 16 transitions; search_limit between 1 and 8192 visited states. Orders constrain entire
transitions; coexistence is state implication and exclusion forbids joint states. An atomic phase
has disjoint same-cohort members/target writes and cannot erase a strict order. Its operation name
cannot alias any transition. One stable witness is returned; alternative paths are not enumerated.
No known path under an exhausted complete search is UNSATISFIABLE_FOR_SUPPLIED_MODEL. A resource
limit is INDETERMINATE_SEARCH_LIMIT. Unknown conditional facts are INDETERMINATE_CONDITIONS.

## CLI and JSON

`mmc-t2 profiles`; `mmc-t2 compile bundle.json`; `mmc-t2 request request.json` (or `-` for stdin).
Requests contain exactly `schema: mmc.request.t2`, `operation`, `arguments`. Operations and keys:

| Operation | Exact arguments |
|---|---|
| profiles | none |
| assess | profile_ref, record |
| replay | profile_ref, record, receipt |
| plan | model, planning |
| retirement/routes | model, record |
| lifecycle | record |
| compile | bundle |
| verify-compilation | bundle, candidate, expected_model_root |

Output is canonical JSON plus newline. Exit 0 means a computation completed, including a blocked
or inconclusive model result; exit 2 means typed refusal. There is no execute, approve, install,
sign, fetch, mutate-trust or publish operation. Input paths are caller-selected bounded local reads.

## Examples

Run `examples/t2/domain_profiles.py`, `retirement_progress.py`, and `coexistence_planning.py`.
They cover four domains, a dormant-worker refusal and supplied-safe counterpart, forged-result
rejection, a phase-resolvable coexistence cycle, and strict-order impossibility. These are synthetic
examples, not a full live end-to-end migration (which remains a T5 acceptance obligation).
