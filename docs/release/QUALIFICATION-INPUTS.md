# External qualification inputs

The public Git repository is source-only. Full qualification requires exact external inputs whose
licenses and custody are independent of MMC:

- CMBA Core 0.1.0a4 wheel, SHA-256 `2a595c06ac64371647eeb9586defde9d3238dbe16271a788ea231de2e15831ce`;
- DKN Core 0.2.0rc5 wheel, SHA-256 `6cc2d9e21c1c26b9b9104bb84a27b8e873f17c7e52bed15228230775e005ccf8`;
- CMBA Core 0.1.0a7 wheel, SHA-256 `fad457fd7a8fe4598da1280fbca90881cfc5e48a5dd410ab9c784ffcb19c70ca`;
- an exact UCM source checkout matching the integration pins;
- an exact SemCrys source checkout matching the integration pins;
- exact UCM r038/Pippi source matching its source manifest and constitutional atlas; and
- the applicable platform-specific offline dependency bundle and lock root.

Supply them to `tools_t7/qualify.py` with `--cmba-a4-wheel`, `--dkn-rc5-wheel`,
`--cmba-a7-wheel`, `--ucm-source`, `--pippi-source`, `--semcrys-source`, and
`--dependency-bundle`. The r036 UCM product input and r038 P/PPI qualification input are distinct.
The qualifier
also requires the independently retained dependency identity through `--dependency-lock-root`. The qualifier
hash-checks the native inputs before use. Absence means the corresponding native test is skipped in
the public source-only CI; it is not silently replaced or downloaded.

The public predecessor manifests under `provenance/public-predecessors/` retain only canonical
paths, byte counts, and SHA-256 values for executable and contract semantics. Private conversations,
historical source archives, and raw run evidence are not required to build or use the public product.
