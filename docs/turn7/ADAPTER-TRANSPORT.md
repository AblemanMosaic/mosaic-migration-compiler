# Authenticated local adapter process transport

`mmc.adapter-transport.v1` carries the existing effect-adapter methods to one
host-enrolled, shipped worker process per call. It is an execution transport;
the native controller still decides eligibility, prepares the exact request,
requires separate scoped approvals, records dispatch, and reconciles uncertain
results. Transport authentication does not grant migration permission.

## Enrollment and execution

The trusted Python host reopens an already enrolled target, pins its descriptor,
and constructs the wrapper. Neither enrollment nor target creation is a worker
operation. The only backend registrations are `disposable.sqlite.v1` and
`sqlite.table-migration.v1`; they map to fixed imports in shipped source.
Request documents cannot supply an executable, import path, plugin or command.

The wire `workload_snapshot` result is explicitly versioned as
`mmc.adapter-workload-summary.v1`: control state, effect count, optional enrollment
root, and legacy/new row counts and SHA-256 digests. Row payloads never travel in
that result. Each digest starts with `MMC/ADAPTER/ROWS/v1` plus a NUL byte,
the ASCII collection name (`legacy` or `new`) and another NUL byte. It then
streams each adapter-ordered canonical row as its unsigned 64-bit big-endian
byte length followed by those bytes. This supports the enrolled row/payload
limits without canonicalizing an entire multi-megabyte inventory. Local
backend `workload_snapshot()` remains the full observation API; digest summary
alone does not establish source/destination semantic equivalence.

```python
from mosaic_mmc_product.sqlite_target import SQLiteTargetAdapter
from mosaic_mmc_product.transport import AuthenticatedAdapter

local = SQLiteTargetAdapter(existing_target_path)
adapter = AuthenticatedAdapter.open(
    existing_target_path,
    backend="sqlite.table-migration.v1",
    expected_descriptor=local.descriptor(),
    deadline_seconds=30,
)
# Pass adapter to the native Controller, which retains prepare/approve/commit.
```

Each RPC launches the actual CPython base executable with `-I -S -B`, a fresh
cache prefix, and explicit host-enrolled package/purelib/platlib roots. This
avoids Windows venv redirectors, so the authenticated worker PID must equal the
process handle held by the host. Isolated startup disables ambient Python
environment, user-site and `.pth` startup effects. In release qualification the
parent's dependency roots come from the closed offline venv. The interpreter,
stdlib and operating system remain declared host prerequisites.

Before launch the parent hashes the shipped Python/data closure in the model,
domain, controller and product packages. The worker independently recomputes
that fingerprint and must match the enrollment. The backend then reopens the
selected target and must return the exact enrolled adapter descriptor. Code
or target-descriptor substitution refuses before a backend effect.

## Authentication and replay

The parent generates a fresh 256-bit session secret and nonce. They travel only
through the child's anonymous stdin pipe, never argv, environment, a key file,
or a receipt. The child creates its own nonce and returns an HMAC-SHA256
challenge binding the protocol, both nonces, backend, implementation fingerprint
and actual worker PID. The parent checks the challenge with constant-time MAC
comparison and pins the PID to its process handle.

The parent's signed request binds that challenge, the derived session ID, a
sequence of one, operation and arguments. The worker authenticates it and
requires EOF immediately after the single request. A second appended request,
different sequence/session, changed arguments, forged MAC or message from a
different phase is refused. The response binds the exact request root and
session. MAC domains are distinct for challenge, request and response.

This is mutual possession authentication on a private local process channel,
with exact code/target enrollment. It is not a public principal certificate,
network TLS endpoint, MosaicID passport or production identity binding. A
hostile process with the same user's memory/filesystem access is outside the
cooperative-host assumption.

## Limits, cancellation and uncertain effects

Frames are canonical UTF-8 JSON with at most 2 MiB per frame. Bootstrap is capped
at 16 KiB, stderr at 64 KiB, and stdout at exactly challenge plus response.
Native JSON type/depth/node/string limits still apply. A valid response followed
by extra output or stderr overflow is not success. IO reader/writer threads are
drained and reaped before a successful return.

The deadline covers startup, handshake, write, response and process exit.
`cancel()` interrupts the active call, while `close()` also refuses future calls.
On deadline, cancellation, malformed output or process death, the owned worker
is terminated/killed and reaped. IO bounds and deadlines are resource controls;
they are not an operating-system memory/CPU/filesystem/network sandbox.

The transport never retries an `apply`. A timeout or lost response may occur
after the target transaction and ledger entry commit. The controller retains
`UNKNOWN`; a new worker performs `lookup(operation_id, request_root)` against
the target's durable ledger. Only reconciliation determines whether an effect
was recorded. Local transaction/ledger behavior does not establish distributed
exactly-once execution or physical power-loss durability.

Fault selection is disabled by default. Qualification hosts explicitly opt into
`allow_test_faults=True` to exercise lost acknowledgment, death after commit,
and delay before/after apply. No regular agent request can turn this on.

## Host path prerequisite

The enrolled interpreter, package root, purelib and platlib paths must be real
directories/files with no symbolic-link or junction component. This is a deliberate
implementation-substitution boundary: the transport does not resolve an alias and then
pretend that the originally enrolled path was exact. POSIX installations that symlink the
interpreter or `site-packages` must create a dedicated environment with copied executables
(for example, `python -m venv --copies ENV`) and invoke the copied versioned executable
(`ENV/bin/python3.12`, not the possibly symlinked `ENV/bin/python`). The public CI uses that
exact versioned path on Linux and the copied `Scripts/python.exe` on Windows.
`MMC_TRANSPORT_IMPLEMENTATION_PATH` is a prerequisite
refusal, not evidence that an adapter effect failed. Relaxing this rule changes transport
semantics and requires separate security and migration qualification.

## Evidence and conformance

`transport_manifest()` is a pure discovery function; it starts no process and
loads no optional signing dependency. `adapter.transport_receipt()` returns a
rooted bounded history with code/session/request/result roots, worker/launcher
PIDs, exit status, IO hashes/lengths, cleanup and retry dispositions. It records
worker challenge authentication separately from response authentication, so a
lost acknowledgment never becomes a fabricated authenticated response.

Qualification explicitly opts into `retain_transcripts=True` when constructing
the wrapper. `transport_receipt(include_transcripts=True)` then carries lossless
base64 chunks in `raw_transcripts` for the signed request, stdout, stderr and exit status;
`export_transcripts()` exposes the same raw bytes for artifact custody. Bootstrap
and session secrets are never retained. These raw transcripts can contain
target metadata and the caller's data, so retention requires explicit opt-in.
Retention neither declassifies that data nor authorizes upload or disclosure.
The custody label is `RETAINED_RAW_BYTES`. The ephemeral HMAC key is destroyed;
an archive alone cannot independently reauthenticate its MACs. Archive hashes
establish integrity while the authentication disposition is recorded host testimony.
A total raw
byte cap defaults to 8 MiB, with worst-case capacity reserved before every
dispatch; exhaustion refuses before starting a process or issuing an effect.
Default runtime history retains compact hashes only. Flood diagnostics retain
a bounded prefix with an explicit truncation flag and a failing outcome.

The source includes executable witnesses for real child authentication, fresh
sessions, forged host/response MACs, replay with a valid MAC, code and target
substitution, output flooding after a valid signed response, deadline/cancel
cleanup, lost acknowledgment and worker death after commit. The real target
qualification uses this transport through the native controller for migration,
recovery, renewed cutover, reconciliation and retirement.
