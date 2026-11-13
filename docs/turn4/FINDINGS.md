# Capability Layer T4 construction findings

## F01 — missing versus null in structural receipt comparison
The first interface regression run had 45 passing cases and one failure. compare_views used dict.get,
which treated an absent checkpoint field as equivalent to an explicitly null checkpoint. This could
hide a meaningful difference in an imported report comparison (not grant authority). The fix checks
field presence before exact canonical value equality. The failing log and repaired regression are
preserved; the original program/contract expectations were not weakened.

## Scope of review
The targeted tests challenge scope/key/work substitution, rehashed work, stale heads, expired reads,
negative evidence, imported PASS, data-supplied plugin names and commands, source replacement, byte/row
limits, malformed JSON, symlinks/special files, HTTP redirects/proxies, SQL/view access, expired exports,
one-use approval, existing destinations and stale/cancelled worker results. Native adapters exercise
actual pinned original code plus wrong roots/source changes. These are same-author bounded tests, not
an independent security review or all real deployments.

Any subsequent interrupted or failed qualification runs remain in the accompanying evidence dossier.

## F02 — installed-probe construction error
The first optional installed probe supplied zero dimensions to the native CMBA binding constructor.
CMBA correctly refused CMBA_DIMENSION_LIMIT. The probe now uses one explicit noncritical fixture
dimension, as the documented native API requires. This was a probe error, not an MMC runtime defect.
The failed terminal log remains preserved and the corrected outside-source probe is recorded separately.

## F03 — optional installed-environment admission
The first host-shared virtual environment inherited system cryptography 43.0.0 rather than the
declared 46.x dependency, lacked jsonschema, and could not capture the GUI without Pillow. Its
initial functional success is superseded by failed dependency qualification, not accepted evidence
of the declared environment. A new isolated environment uses inventoried exact copies of genuine
preinstalled 46.0.4 and required packages. The probe now explicitly checks the version and isolated
module path. Fresh resolver/download remains unestablished. Failed probes remain in the dossier.

## F04 — qualification child-process import path
The first full T3 replay under the new runner passed 145 cases and failed five child-process checks
because the child interpreter could not import the admitted source. Parent sys.path insertion does
not propagate to subprocesses. The new runner now explicitly sets its admitted source import paths
for children and records them in the stage environment. No inherited test or runtime was changed.
The unsuccessful source-bound run is retained; all groups are replayed against the renewed source.
