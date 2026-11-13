# MMC test system

MMC presents tests by product meaning while preserving every historical Python test ID and
directory as compatibility ABI. `tests` and `tests_t2` through `tests_t6` correspond to Capability
Layers 1 through 6. `tests_t7` corresponds to Release Convergence; it is not a seventh layer.

The machine contract is `profiles/TEST-SYSTEM.json`. It fixes the canonical names, compatibility
directories, exact discovery profile, diagnostic lanes, cost classes, and effect classes. Registry
discovery refuses unless the complete offline qualification environment is present. This prevents
an optional dependency from silently turning a test module into one admitted skip.

The contract also names `installed-wheel-ci` as a separate artifact check. GitHub Actions builds the
wheel, installs it into a fresh environment outside the checkout, then runs `mmc-installed-ci` from
an unrelated working directory. That entry point rejects source-tree imports before running installed
protocol conformance and the disposable migration. It complements, but does not replace, the exact
externally pinned full release lane.

## Lanes

- `smoke`: fast orientation, agent protocol, and surface consistency.
- `public-ci`: the bounded cross-platform public-source suite used by GitHub Actions. Its one
  exact declared skip is the owner-custody CMBA a7 wheel test; full qualification supplies and
  executes that wheel instead of converting the skip into a pass. The lane also runs the T3
  controller restart, approval invalidation, target reservation and compensation suite plus the
  aggregate-journal and pre-effect capacity boundary witnesses.
- `preflight`: high-fanout release inputs and contracts; used before the expensive full run.
- `contract`: all six Capability Layers plus successor correspondence checks.
- `integration`: adapter, controller, authenticated transport, migration, retirement, and recovery.
- `platform`: offline dependencies, security snapshot, host aliases, and handoff behavior.
- `publication`: public projection, evidence scope, qualification index, and regression controls.
- `full`: all admitted tests. Only this lane can support release qualification.

Plan a lane without importing or executing tests:

```powershell
python -B tools_t7/test_runner.py --lane smoke --expected-source SOURCE_ROOT --plan-only
```

Execute a lane only after supplying the exact environment named in the machine contract:

```powershell
python -B tools_t7/test_runner.py --lane smoke --expected-source SOURCE_ROOT --out FRESH_OUTSIDE_SOURCE
```

Targeted lanes are diagnostic and iteration aids. They never authorize evidence reuse and never
replace `tools_t7/release_verify.py`, whose full path executes the complete admitted denominator,
integration checkpoints, disposable target migration, packaging, and installed-wheel checks.
Public CI may use `--self-pin` because it is a diagnostic observation of the checked-out bytes;
the `full` lane refuses that mode and requires an independently supplied `--expected-source` root.
The runner binds process and disposable-database temporary roots under the selected output directory
before loading tests, so a concurrent source observer never sees transient test state in the tree.
