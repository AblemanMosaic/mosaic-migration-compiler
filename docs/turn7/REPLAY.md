# Release Convergence replay

The r013 Release Convergence entry point is `tools_t7/release_verify.py`; see
[release preparation](RELEASE-PREPARATION.md) for its complete invocation. It includes
two hash-locked clean environments, complete installed-member checks and authenticated target migration.
The lower-level qualification and package commands below remain available for diagnosis.
The canonical test topology and targeted diagnostic lanes are documented in
[TEST-SYSTEM.md](TEST-SYSTEM.md). Targeted lanes reduce iteration cost but cannot replace the full
release denominator.

Run output outside the source tree and bind temporary files to an operator-selected writable directory.
The current qualification consumes exact clean UCM and SemCrys Git identities and the bundled exact
CMBA a7 wheel; it performs local temporary SQL and journal writes but no installation, network access,
live target mutation, or production effect. Source probes require the exact pinned clean checkouts.

```powershell
$env:TEMP = '<outside-source-temp>'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B tools_t7/qualify.py `
  --out '<outside-source-evidence>' `
  --ucm-source '<exact-clean-mosaic-ucm-r036-checkout>' `
  --pippi-source '<exact-verified-mosaic-ucm-r038-source>' `
  --semcrys-source '<exact-clean-semcrys-core-0.1.0-checkout>' `
  --subject '<exact-capability-layer-t6-subject-directory>' `
  --cmba-a4-wheel '<exact-cmba-a4-wheel>' `
  --cmba-a7-wheel '<exact-cmba-a7-wheel>' `
  --dkn-rc5-wheel '<exact-dkn-rc5-wheel>' `
  --dependency-bundle '<exact-native-offline-bundle>' `
  --dependency-lock-root '<separately-retained-lock-root>' `
  --expected-source '<precomputed-current-source-root>'
```

Build deterministic artifacts with:

```powershell
python -B tools_t7/package.py --source '<outside>/MMC-v0.1.0a9-RELEASE-CONVERGENCE-r013-SOURCE.zip'
python -B tools_t7/package.py --wheel '<outside>/mosaic_migration_compiler-0.1.0a9-py3-none-any.whl'
python -B tools_t7/package.py --verify-source '<outside>/MMC-v0.1.0a9-RELEASE-CONVERGENCE-r013-SOURCE.zip'
```

The qualification receipt is same-author engineering evidence. The Stage I1 return is
`READY_FOR_REVIEW`, not production admission. A privileged Windows replay is still required to execute
the historical symbolic-link fixtures when the ordinary host token lacks link-creation privilege.
