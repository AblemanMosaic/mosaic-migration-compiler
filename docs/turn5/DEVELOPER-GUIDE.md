# Using the finite Capability Layer T5 migration foundry

Distribution `mosaic-migration-compiler 0.1.0a5`, qualification profile **T5-Q1**.
The compiler/controller/agent/workbench semantics from T1–T4 are unchanged. The new
package is a qualification harness, not a second controller and not a production adapter.

## Installed use

```sh
python -m pip install ./mosaic_migration_compiler-0.1.0a5-py3-none-any.whl
mmc-foundry list
mmc-foundry run safe-token > safe-token.json
```

The list command is standard-library-only. Running signed scenarios requires the deliberately
installed optional cryptography 46.x dependency. None is fetched or installed by a scenario.
All keys are PUBLIC deterministic fixture keys. Run outputs may expose fixture policy and
journal material; no customer data is read. SQLite databases are created only in temporary
local directories selected by the harness and removed on normal completion.

```python
from mosaic_mmc_t5 import run_scenario, replay_scenario
from mosaic_mmc_t5.foundry import inspect_result
candidate = run_scenario('lost-ack', seed=0)
# This is a self-generated demonstration pin, NOT independent publisher recognition.
inspection = inspect_result(candidate, expected_root=candidate['root'])
replay = replay_scenario('lost-ack', candidate)
assert replay['status'] == 'MATCH_EXACT_FRESH_SIMULATION'
```

`inspect_result` verifies exact structure, caller-supplied root, claim ceiling, recorded
trace chain and the recorded controller journal. It does not establish that the trace
was actually produced by an execution. `replay_scenario` recomputes the whole scenario
in NEW temporary stores and compares the complete canonical result. It performs local
simulation writes. The native controller's separate journal replay is non-effectful and
never reissues target operations. These three meanings of replay must not be conflated.

CLI inspection/replay require `--candidate FILE --expected-root HEX`; use `--seed N`
for the same selected finite schedule. No shell command, handler import, database path,
production target, private key or arbitrary scenario program is accepted from that file.
The fixed installed catalogue contains ten scenarios; seeds are integers from 0 to 31.
Seeded variation changes message order, not cryptographic policy or expected safety results.
A CLI exit zero means the selected local qualification computation completed, not a grant.

## What is composed

The fixture source inventory is collected by the actual T4 JSON collector. The safe-token
case performs an explicit resource-pinned agent read and evidence-admission cycle. Each
case uses actual T2 compilation, T3 signed observations, separate jurisdictional approvals,
controller transitions and SimulatedStore transactions. The final roster is model-declared;
there is no claim of live discovery completeness. The legacy-write probe is a finite model
of a resumable producer inspected by the installed job observer, not a production token issuer.

The standard path is prepare, canary, coexistence, fencing, reconciliation, cutover and
retirement. Discovery precedes the effect path. Seven committed primary transitions each
use a fresh scoped request/approval. Negative conditions are tested by invoking actual
controller operations and checking that the simulated target bytes and effect ledger do
not change. A separately admitted repair must then permit progress. The targeted-rollback
case also migrates an unrelated cohort and checks that compensation cannot affect it.

## Qualification versus integration

A deployment needs its own trusted inventories, keys, clock/floor custody, policy selection,
source coverage and qualified adapters. A publicly known fixture signature is not evidence
about that deployment. Arbitrary host Python remains trusted code, not sandboxed. No native
P/PPI or UCM activation, CMBA model promotion, public publication, remote collection or
production migration occurs. Existing read-only `mmc`, `mmc-t2`, `mmc-t3`, `mmc-agent` and
`mmc-workbench` interfaces keep their exact original implementations.
