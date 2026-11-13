# Finite extension qualification and read-only adapters

## SDK
The host supplies a Python function plus its expected source hash, exact descriptor root and finite
expected cases to Registry.qualify. Descriptors never contain an executable import path. Qualification
requires positive and negative cases and exact canonical typed equality; no bool/int coercion. The
handler hash is checked before and after qualification and on use. This does not sandbox that Python,
prove transitive dependency integrity or establish correctness beyond the selected corpus. Installation
and authorization remain trusted host actions. New profiles cannot alter the original compiler domains.

The residency example checks declared regions only; the jobs observer checks whether supplied legacy
workers are resumable/unfenced or have pending writes. Both are independent additions using the same
SDK without changing T1/T2/T3. Successful invocation never authenticates physical coverage.

## Actual collectors and record interfaces

| Interface | Implemented mechanism | Qualification boundary |
|---|---|---|
| FileCollector | Exact admitted relative file list; bounded bytes and file hashes | Local selected paths; not exhaustive/atomic repository discovery |
| JsonFileCollector | Exact bounded JSON file; raw-source digest plus parsed value | Quiescent cooperative file; not truth/authentication |
| SQLiteCollector | Fixed SELECT id,value FROM mmc_observations; readonly/query_only | Quiescent regular database; no WAL/SHM/journal, virtual table, views or supplied SQL |
| HttpCollector | Host-selected exact HTTPS URL, or explicit loopback HTTP; no redirect/proxy/credentials | Actual loopback GET tested; production HTTPS service not deployed |
| repository records | Revision and exact supplied file identities | No Git process, remote enumeration or proof of complete checkout |
| release records | Exact artifact/source/toolchain correspondence | Declared release metadata, not reproducible build proof |
| deployment records | Exact cohort/version/supplied instance roster | Not a live Kubernetes adapter or global instance census |
| jobs records | Bounded workload state predicate | Not a live job scheduler discovery integration |

Collector caps are 1 MiB and 512 rows (file list 128 entries). HTTP accepts application/json and identity
encoding, with configured socket timeout 1..10 seconds plus between-read deadline checks. No universal
hard CPU/DNS/network deadline or hostile-host containment is claimed. HTTPS certificate behavior follows
the selected trusted Python/OpenSSL environment. Resources are chosen by the host, not an opened model.
Captures label unauthenticated collection; a separately recognized observer may endorse an exact claim.

## Native integrations
CMBA 0.1.0a4 core inspect and DKN 0.2.0rc5 archive verification are explicit optional readers. The exact
local wheels are retained under baseline/ and every selected package .py/.json/.md file is checked before
import against an admitted file set. Missing/changed/extra files refuse. This scopes source integrity,
not the entire interpreter or transitive dependency supply chain. Submitted data cannot auto-install.

CMBA retains its native root/report; DKN additionally requires the independently expected logical root.
NATIVE_REPORT_COMPUTED is not a broad PASS. Only these particular read operations are integrated, not the
entire native workbenches. Native P/PPI and UCM are NOT_BOUND; CHC handoff is REFERENCES_ONLY. No native
validator or host was available in this session, and local receipt tests cannot fill that absence.
