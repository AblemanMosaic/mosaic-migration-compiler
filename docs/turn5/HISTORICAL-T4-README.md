# Mosaic Migration Compiler — Turn 4

**Model the migration. Compile the obligations. Verify the transition.**

Current candidate: `mosaic-migration-compiler 0.1.0a4 / T4-r001`.
MMC now joins its deterministic compiler and local simulated controller to a bounded agent
investigation interface, an obligation-first native workbench, and explicit read-only adapters.
Eight new agent acceptance cases can be qualified locally. Native P/PPI admission remains blocked;
T5 end-to-end qualification and T6 delivery/research gates remain open.

Start at [Turn 4 documentation](../turn4/README.md), [user guide](../turn4/USER-GUIDE.md),
[developer guide](../turn4/DEVELOPER-GUIDE.md), or the unchanged [full program](../PROGRAM.md).

```sh
python -m pip install ./mosaic_migration_compiler-0.1.0a4-py3-none-any.whl
mmc-agent capabilities
mmc-workbench
```

The library import is `mosaic_mmc_t4`; GUI is `mosaic_mmc_workbench`. Existing `mmc`, `mmc-t2`,
`mmc-t3` remain independent explicit profiles. Tk/display and optional cryptography 46.x are
needed for native GUI/operational evaluation. No auto-install or public registry availability
is assumed. Native source collectors and journal writes require separate trusted host calls.

Current release evidence is external to the source archive to avoid self-hash cycles. Test totals
are measured in the final receipt, not assumed from this README. All records are unsigned
same-author engineering evidence. No production migration, native P/PPI mediation, independent
approval, clinical/election/security-domain truth or productivity advantage is claimed.
