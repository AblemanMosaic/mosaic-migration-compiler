# Capability Layer T3 — operational spine

W06–W08: durable controller, evidence/authority courts, restricted simulated effects.
The frozen contract is `model/operational-t3/CONTRACT.json`, root
`34ae08f720e005da3515d420d7ca7f7a2bd70a716bafcb0852887803162da924`.
The full program root remains `abf1559fdede121a573335243b91dfa38014c6c825218ff2a6273656e593c7b7`.

This is an opt-in extension. Foundation guards and supplied-model assessments retain their original
meaning. T3 adds a reader-pinned recognition policy, actual signatures, current-context checks,
a durable journal and an independently persisted simulated target with its own idempotency ledger.

A successful court cannot invoke an effect. The host must explicitly prepare, obtain all scoped
signatures, approve, and commit. A committed target whose acknowledgment is lost must be reconciled.
Replaying a controller journal never calls a target adapter. A partially applied operation remains
`RECOVERY_REQUIRED`; this release does not invent a repair that makes an unknown outcome disappear.

Read PROTOCOL.md, DEVELOPER-GUIDE.md, SECURITY.md, FINDINGS.md, ACCEPTANCE.md, QUALIFICATION.md,
REPLACEMENT.md and SOURCES.md in this directory. Exact current receipts are external to the source
archive to avoid self-hash cycles. Historical receipts remain historical.
