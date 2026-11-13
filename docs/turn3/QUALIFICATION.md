# Qualification and exact replay

Source admission uses the externally selected root in provenance/SOURCE-ADMISSION.json. That file
is not self-authentication; the operator must obtain its expected root through an accepted path.
All noncache source/model/schema/test/tool/doc files are admitted before collection. Source-admission
itself and the canonical source FILE-MANIFEST are excluded from that root to avoid cycles. Evidence
files are separately archive-bound and cannot carry executable source. Generated .pyc is excluded.

From the exact extracted source directory in a prepared Python environment with genuine operational
crypto and JSON Schema validation dependencies:

```
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase test-t1
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase test-t2
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase test-t3
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase tests
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase examples
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase audit
python tools_t3/qualify.py --expected-source <PINNED_ROOT> --out <OUTSIDE_SOURCE> --phase assemble
```

Each phase is create-only. Interrupted runs have no completed terminal receipt and cannot satisfy a
gate. The runner binds actual interpreter/source directory/working directory, dependency versions,
source root, exact unique collected/executed test identities, result types and closed output hashes.
No missing, skipped or duplicated test may be relabeled a pass. Assembly rechecks all stage metadata
and files and rejects mixed environments. Root/test identities and rejection tests are not a sandbox
against an evidence producer who controls the host and can fabricate all records.

Mandatory local legs: all original and new named tests; seven workflows; three unchanged-or-versioned
known-answer corpora; all three model checks; exact predecessor preservation; clean extraction;
installed-wheel operation outside source; deterministic source/wheel reserialization; complete delivery.
Final local assembly explicitly leaves installed-wheel and clean-extraction evidence separate.

`--require-native-pippi` must refuse while its actual selected schema/interpreter/host remains unbound.
Do not create substitute receipts. No Win/WSL/macOS evidence is inferred from the Python wheel tag.
Snapshots and conformance are finite same-author evidence; independent security review and comparative
productivity study are NOT_PERFORMED. Existing T5 full-migration cases remain NOT_RUN despite smaller
T3 simulated workflows. Physical power loss and malicious-host resistance remain unestablished.

The source ZIP uses fixed timestamp/metadata and exact lexical POSIX path ordering. Byte-identical
rebuild means serialization of the same frozen tree, not regeneration of timestamped test logs.
Do not regenerate accepted vector oracles in a verifier; author_vectors.py is an explicit authoring tool.

The three test groups run in separate admitted invocations. Each binds its exact collection identities,
outputs, environment and terminal status. The tests phase verifies their disjoint union and full
execution coverage before assembly. Interrupted combined attempts remain incomplete in evidence;
separate completed groups are new runs, not retroactive completion of interrupted processes.
