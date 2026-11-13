# MMC — preserved Capability Layer T6 review dossier

Release Convergence is the current successor line. Start at [`docs/turn7/README.md`](../turn7/README.md);
the `turn7` directory name is retained compatibility ABI, not product architecture.
This directory retains the Capability Layer T6 claims and evidence boundary for predecessor replay.
Statements below about an unselected license, 0.1.0a6 dependencies, or an `evidence/`
directory describe the historical Capability Layer T6 candidate. They are not current v0.1 release metadata.

Distribution **mosaic-migration-compiler 0.1.0a6 / T6-r001**. The T1, T2-D1, T3-O1,
T4-I1 and T5-Q1 implementations retain their exact predecessor bytes. This is a qualification
and documentation release, not a new migration engine or production activation.

Start with [User and integration guide](USER-AND-INTEGRATION.md), then
[Architecture and boundaries](ARCHITECTURE.md). Agents start at [AGENTS.md](../../AGENTS.md).

| Document | Purpose |
|---|---|
| [Claims and acceptance](CLAIMS-AND-ACCEPTANCE.md) | Exact implemented, observed, missing and external obligations |
| [Replay](REPLAY.md) | Source-admitted grouped commands and target replay |
| [Migration and rollback](MIGRATION-AND-ROLLBACK.md) | Package selection versus operational compensation |
| [Security and review](SECURITY-AND-REVIEW.md) | Threat assumptions and exact review worklist |
| [Replacement qualification](REPLACEMENT-QUALIFICATION.md) | Stable contracts, changed realizations and new evidence |
| [Document status](DOCUMENT-STATUS.md) | Current guidance versus frozen protocol/history |
| [Observed components](COMPONENT-INVENTORY.json) | Environment inventory, not a vulnerability scan |
| [Findings](FINDINGS.md) | Retained construction and qualification findings |
| [Independent study](../../study/PROTOCOL.md) | Fair design; no invented productivity result |
| [Native admission](NATIVE-ADMISSION.md) | Prerequisites for actual P/PPI operation |

The original 84 requirements and 100 cases remain frozen under the program root in
`PINNED-PROGRAM-ROOT.txt`. Passing local tests cannot supply absent platform, native,
production, independent-review or comparative-research evidence. The current release
manifest is an unsigned integrity inventory; trust requires an independently accepted pin.
