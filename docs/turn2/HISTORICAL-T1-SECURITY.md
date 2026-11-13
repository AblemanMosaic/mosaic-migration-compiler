# Security boundary — Turn 1

The compiler is a deterministic structural evaluator over finite supplied data. It does not validate
real infrastructure, authenticate observations, certify a signer, grant permissions, enforce a
migration, or discover undeclared producers. Declared Authority objects are data, not trust roots.
A source can contain every desired assertion and still leave all live guards unresolved.

Installed Python, compiler files, host OS and accepted model/profile roots are trust dependencies.
Package immutability during execution is assumed; hashing on-disk source is not attestation of the
interpreter's complete in-memory execution. Byte/graph budgets do not provide a CPU/OS sandbox.
The CLI refuses regular-path symlinks/junctions and nonregular files, with bounded reads and change
checks; hostile administrators racing paths are outside its guarantee. It never writes an output
file directly. User-selected shell redirection is outside the read-only ABI.

References are not fetched. Adapter names are labels, not import locations. Evidence is unauthenticated
in T1. All generated receipts are unsigned; an internally consistent root needs an independently
accepted expected value for authenticity. Recompilation validates the claimed relationship for this
implementation; it does not prove global program correctness.

## Process posture
ARTIFACT_MEDIATED_LOCAL_ENGINEERING_NOT_NATIVE_PIPPI is a descriptive label, not a native P/PPI state.
Native admission, interpreter receipts, standards/atlas binding and host effect mediation remain
NOT_BOUND. Do not infer them from tests of MMC's future effect mechanism or from local scripts.

## Release limits
This is a same-author construction candidate. Native Windows/WSL/macOS, independent security review,
production custody/time/floor enforcement and deployment adapters remain unestablished. No production
migration, external service, public publication, or external review submission occurred. Development
and testing deliberately create files and install a local wheel in temporary environments.

Report precise findings against exact artifact hashes; preserve failed witnesses. A code fix that
changes the protocol needs a versioned semantic amendment. No source license/public-release clearance
is silently inferred from this construction authorization.
