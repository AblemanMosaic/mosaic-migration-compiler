# Exact-source replay

Obtain the expected source root from an accepted external handoff. Checking that a packet repeats
its own root establishes only consistency. Verify the source ZIP with the supplied package verifier,
extract into an empty directory, prepare the declared dependencies, and keep run output outside source.
Do not regenerate `SOURCE-ADMISSION.json`, frozen contracts or vector expectations during verification.

From that admitted source directory, run each phase separately:

```sh
python tools_t6/qualify.py --expected-source <accepted-source-root> --out <outside-output-directory> --phase test-t1
```

Repeat with `test-t2`, `test-t3`, `test-t4`, `test-t5`, `base-tests`, `scenarios`, `examples`,
`base-audit`, `base-assemble`, `test-t6`, `audit`, and `assemble`. Each group has its own terminal
record. Missing, skipped, failed, duplicate, extra or modified records refuse a passing assembly.
The source is admitted before test discovery and rechecked afterward. Scripts run in a trusted host;
they are not a sandbox against malicious interpreters or operators capable of replacing the checker.

`tools_t6/replay_posix.sh <root> <out>` and `tools_t6/replay_windows.ps1 -ExpectedSource <root> -Out <out>`
are convenience wrappers. They stop at a failed phase and do not silently skip unsupported target tests.
The PowerShell wrapper requires an actual Windows host. These helpers are NOT Windows/WSL/macOS evidence.
A target-specific failure requires a retained finding and explicit platform disposition, not edited oracles.

Add `--require-native-pippi` to demand native admission; it refuses while unbound.
`--require-platform Windows` refuses on a non-Windows host. A refusal is evidence of a guard, not a
successful native or Windows replay. Current receipt context states the actually executed platform.

Local assembly leaves installation and clean-extraction as SEPARATE_LEG_REQUIRED. For final release,
verify the installed wheel outside the source tree, rerun from the final source extraction, rebuild
source/wheel byte-identically, and verify all external delivery members. Comparison of timed logs
is not expected to be byte-identical; deterministic scenario outputs are compared separately.

The component inventory records observed dependencies, not a vulnerability scan or a license audit.
Optional preinstalled dependencies are not fresh download/resolution evidence. Native integration
and comparative study require their own real inputs and acceptance; local test counts supply neither.
