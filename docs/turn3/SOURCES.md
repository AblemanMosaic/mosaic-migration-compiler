# Sources and implementation references

Primary project basis: frozen MMC v0.1 constitution and requirements, T2 source SHA-256
ab0ae74ba1b2e2f8f62f3257561bc7c37be5718d2259142702aeccce277d7258 and T2 handoff.
The predecessor is retained byte-for-byte in baseline/MMC-TURN2-SOURCE.zip.

External implementation references inspected during construction (not evidence of MMC correctness):
- cryptography 46.0.4 EC API: https://cryptography.io/en/46.0.4/hazmat/primitives/asymmetric/ec/
  P-256 point admission, ECDSA SHA-256, deterministic signing and explicit unsupported-backend handling.
- SQLite transaction language: https://www.sqlite.org/lang_transaction.html
- SQLite atomic-commit assumptions: https://www.sqlite.org/atomiccommit.html

The implementation uses the installed backend actually recorded in execution receipts. Documentation
of a primitive does not confer independent review on its integration. No new cryptographic algorithm,
production authority protocol, or native P/PPI schema is invented.
