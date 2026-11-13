# Use and integration

Install the supplied local a6 wheel in a deliberately selected Python 3.12+ environment:

```sh
python -m pip install ./mosaic_migration_compiler-0.1.0a6-py3-none-any.whl
mmc capabilities
mmc-t2 profiles
mmc-t3 capabilities
mmc-agent capabilities
mmc-foundry list
```

Prepare genuine `cryptography>=46,<47` for signed operations; the optional qualification extra also
requires `jsonschema>=4,<5`. An optional Tk graphical session is needed for `mmc-workbench`.
No public package-registry availability is assumed. The supplied wheel does not bundle optional
third-party packages. Consult the environment receipt for actual versions used, not implied target support.

From an installed source checkout, start with:

```sh
mmc compile examples/identity.json
mmc-t2 compile examples/t2/identity.json
python examples/t3/operational_recovery.py
python examples/t4/agent_cycle.py
mmc-foundry run safe-token > safe-token.json
```

The shell redirect is your explicit file write. The source examples are in the source archive, not
implicitly installed as CLI scripts. Full scenario execution creates temporary simulated SQLite state.
The deterministic fixture identities, clocks and model pins are not production recognition inputs.

## Select an interface, not a blanket trust level

| Interface | Scope |
|---|---|
| `mmc`, `mosaic_mmc` | T1 model validation/compilation and verification |
| `mmc-t2`, `mosaic_mmc_t2` | T2 domain/planner/retirement declarations |
| `mmc-t3`, `mosaic_mmc_t3` | Read-only signed evidence checks; Controller host calls are separate |
| `mmc-agent`, `mosaic_mmc_t4` | Work orders, return checks, read-only data operations and trusted-host SDK |
| `mmc-workbench`, `mosaic_mmc_workbench` | Same headless semantics in a native inspection interface |
| `mmc-foundry`, `mosaic_mmc_t5` | Fixed finite simulation scenarios and replay |

Exact signatures and JSON fields remain in the versioned guides:
[T2](../turn2/DEVELOPER-GUIDE.md), [T3](../turn3/DEVELOPER-GUIDE.md),
[T4](../turn4/DEVELOPER-GUIDE.md), [T5](../turn5/DEVELOPER-GUIDE.md).
Successful exit zero means computation completed; BLOCKED or INDETERMINATE can be legitimate results.
Use `importlib.metadata.version('mosaic-migration-compiler')` for the distribution version. The
preserved GUI/profile labels identify their historical implementation and are not a6 provenance by themselves.

## Real integration prerequisites

Bind actual discovery coverage, reader roots, recognized keys, source methods, clocks, external floors,
adapter identity-to-store custody and target semantics. Do not take pins from the untrusted object
being evaluated. Start in shadow mode. Validate one narrowly scoped effect adapter with before/after
witnesses and recovery tests before granting it real authority. No production effect adapter is shipped.
The complete construction and simulation dossier is evidence for review, not an operational approval.
