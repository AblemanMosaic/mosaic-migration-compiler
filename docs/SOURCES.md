# Sources and interpretation boundary

The controlling product scope is the user's six-capability-layer MMC work program and explicit Capability Layer T1 request in
this conversation. REQUIREMENTS.json is an engineering explication of that program, not a verbatim
historical transcript. provenance/USER-REQUEST.md records the current authorization and its limits.

provenance/public-requirements-summary.md preserves the non-identifying product requirements distilled
from owner-supplied design discussions: persisted old state, producers, consumers, dependency ordering,
phased mappings and rollback, dormant jobs, retirement only after cessation and blocking, and scheduled
rather than every-CI operation. The underlying conversations are intentionally not published. These are
requirements, not validation that any proposed system already enforces them.
provenance/native-pippi-prerequisites.md preserves the actual unexecuted native-admission work order.

Implementation references checked during this turn (not evidence of MMC security or performance):
- Python 3.13 json documentation: https://docs.python.org/3.13/library/json.html
- PyPA wheel format: https://packaging.python.org/en/latest/specifications/binary-distribution-format/

The exact JSON limits, schemas, normalization and compilation meanings are authored in the frozen
MMC contract. Python json defaults are not treated as that contract. The wheel builder implements
standard package metadata/RECORD; source archives use a separate closed inventory.

No CMBA/DKN source was copied into the runtime or silently deemed fully qualified. The reviewed
integrated CMBA candidate's stronger claims are not prerequisites assumed by this standalone build.
