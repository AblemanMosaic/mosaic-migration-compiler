# Mosaic Migration Compiler (MMC)

**Model the migration. Compile the obligations. Verify the transition.**

Turn 1 foundation candidate: **mosaic-migration-compiler 0.1.0a1 / T1-r001**.
This MMC is the Mosaic Migration Compiler, not Mosaic Media Center.

MMC compiles a finite migration model into deterministic, source-linked obligations. It keeps old
persisted state, producers, consumers, resumable jobs, cohorts, policies and evidence declarations
visible together. Agents can contribute discoveries; they do not silently change accepted rules.

## Implemented here
A frozen six-turn program (84 requirements, 100 acceptance cases); twelve typed model primitives;
a closed foundation profile; deterministic model normalization and IR; explicit dependency ordering;
literal state-chain checks; bounded guard compilation; source/profile/compiler commitments; full
recompilation verification; read-only Python API, JSON ABI and CLI; source-based qualification and
reproducible source/wheel packaging. Four synthetic domain examples use the same metamodel.

**Compilation never authorizes a migration.** Every example retains runtime obligations. The domain
profiles, richer planner, live controller, courts, effect adapters and native workbench are later
turns. In this turn, 29 mandatory cases are due; 71 remain NOT_RUN. Extra unit tests do not promote
those later cases. No performance, independent-study, production-safety or native P/PPI claim.

## Start locally

```sh
python -m pip install ./mosaic_migration_compiler-0.1.0a1-py3-none-any.whl
mmc capabilities
mmc model validate examples/identity.json
mmc compile examples/identity.json > compiled.json
```

Python 3.12+ is the target. Only environments named in the actual receipt are qualified. The wheel
uses the standard library only, with no DKN/CMBA/GUI/network dependency. These commands do not assert
that a public registry hosts this package. Shell redirection is an explicit caller write.

For source-only use: `PYTHONPATH=src python -m mosaic_mmc compile examples/identity.json`.
On PowerShell, set `$env:PYTHONPATH="src"` first. Source examples live in the source ZIP, not the wheel.

```python
from pathlib import Path
from mosaic_mmc import decode, compile_model, verify_compilation
model = decode(Path("examples/identity.json").read_bytes())
compiled = compile_model(model)
# Demonstration pin only; a real reader must obtain the expected model root independently.
report = verify_compilation(model, compiled,
                            expected_model_root=compiled["ir"]["model_root"])
assert report["eligibility"] == "NOT_EVALUATED"
```

## Read next
- [Full frozen program and requirements](../PROGRAM.md)
- [All 100 acceptance cases and gate schedule](../ACCEPTANCE.md)
- [Architecture](../architecture/ARCHITECTURE.md) and [normative T1 protocol](../architecture/PROTOCOL-T1.md)
- [Actual library/CLI interfaces](../interfaces/API.md)
- [Qualification and replay](../qualification/REPLAY.md)
- [Model/realization separation](../qualification/MODEL-AND-REALIZATION.md)
- [Security and P/PPI posture](SECURITY.md)
- [Current findings](../qualification/FINDINGS.md)

Source custody and the complete evidence packet are separate from the frozen semantic contract.
Everything is unsigned same-author engineering evidence. Public release is NOT_CLEARED; native
P/PPI admission is NOT_BOUND. This is not a production migration controller.
