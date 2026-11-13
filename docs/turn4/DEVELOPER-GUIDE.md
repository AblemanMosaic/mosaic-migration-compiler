# Library, agent and collector integration

Install the local wheel deliberately. Pure discovery, extension predicates and structural operations
are standard-library-only. T3 evidence verification needs genuine cryptography>=46,<47. Tk and
an actual display are required only by the optional workbench. The complete source dossier is not
inside the runtime wheel. Existing test fixtures use public keys/scalars, never production keys.

```sh
python -m pip install ./mosaic_migration_compiler-0.1.0a4-py3-none-any.whl
mmc-agent capabilities
mmc-agent profiles
mmc-workbench
```

## Main surfaces

| Module | Operations | Boundary |
|---|---|---|
| views | snapshot, assess_view, replay_view, compare_views, journal_view | Recomputed T3 evidence, no permission/effects |
| work | make_work_order, review_submission | One unresolved claim; review only |
| host | AgentHost.capture/admit, ReadSession.read | Explicit evidence append or bounded selected read; not target commit |
| sdk | Registry.qualify/call | Host supplies code; finite fixture qualification, not sandbox |
| extensions | residency_profile, job_observer | Finite supplied-record predicates |
| collectors | FileCollector, JsonFileCollector, SQLiteCollector, HttpCollector | Explicit host I/O; no automatic authority |
| collectors | assess_record | Pure repository/release/deployment snapshot correspondence |
| exports | LocalExport.prepare/approve/commit | Explicit create-only local JSON export |
| integrations | manifest, native_read, handoff, require_native_pippi | Exact optional runtime readers; missing native gates remain blocked |
| mosaic_mmc_workbench.model | Workbench | UI and headless client of same semantics |

## Narrow agent cycle

```python
from mosaic_mmc_t4.host import AgentHost
from mosaic_mmc_t4.work import make_work_order, review_submission

host = AgentHost(controller)                 # existing explicitly owned T3 controller
snapshot = host.capture(migration, transition)
# reader pins/time must be selected through the host's accepted configuration path.
work = make_work_order(snapshot, reader, "coverage", allowed_reads, ttl=30)
review = review_submission(snapshot, reader, work, submission,
                           expected_work_root=accepted_work_root)
# Only an explicit host choice performs this separate evidence write:
result = host.admit(migration, transition, reader, work, submission,
                    expected_head=snapshot["head"],
                    expected_work_root=accepted_work_root)
```

The example names real caller inputs rather than inventing authority. `submission` must contain
a valid signed T3 observation; MMC does not autonomously call an LLM or give an agent observer
credentials. The host still runs T3 prepare/approval/commit separately if a target change is desired.

`ReadSession(work, expected_work_root=..., sources=..., current_snapshot_root=...)` enrolls fixed
collector objects at the host. The work references exact SHA-256 canonical captured-value roots.
Reads are exact-ID, time/snapshot checked before and after, with a budget of 16 attempts. Values
with unknown future digests need a new accepted work order after discovery; the API does not
pretend a content pin can cover arbitrary future data. Raw collectors may independently capture
candidate data through host-selected configuration, then return proposals.

Run `examples/t4/agent_cycle.py`, `extensions_and_collectors.py`, `workbench_review.py` from the
source checkout. They use temporary files and public fixture identities and do not demonstrate
production observation, external native orchestration or developer productivity.

## JSON and CLI
`mmc-agent request file.json` or `mmc-agent request -` consumes one bounded canonical request.
Use the operation map from `mmc-agent capabilities`; exact shapes are exported in schemas/t4.
`mmc-agent --version` reports the T4 distribution. Existing CLI versions retain their original
profile meaning. The ABI contains no filesystem/network path parameters; native-read takes bytes
or data, while native imports are pinned installed code selected by the host.
