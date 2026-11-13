# Contributing

MMC preserves frozen requirements, acceptance oracles, compatibility identities, and
evidence boundaries. Read `AGENTS.md`, `docs/turn7/README.md`,
`docs/turn7/PRODUCT-CORRESPONDENCE.md`, and
`docs/release/CLAIMS-AND-ACCEPTANCE.md` before changing code.

Contributions should:

1. Name the obligation and acceptance case being changed.
2. Preserve a failing witness before implementing a repair.
3. Keep modeling, admissibility, authority, execution, observation, and evidence
   claims distinct.
4. Run the relevant positive and negative tests from the exact source tree.
5. Keep qualification output outside the source tree.
6. Never commit credentials, private DKN keys, customer data, or generated release
   archives.

By contributing, you agree that your contribution is licensed under Apache-2.0.
