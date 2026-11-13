# Explicit host effects versus data operations

Read/verify/evaluate/request interfaces cannot mutate a controller, select credentials, fetch a URL,
install a handler or commit a target effect. Host calls are intentionally separate:

* AgentHost.admit appends checked evidence using original T3 journal events with an exact head CAS.
* ReadSession and raw collectors perform only the separately enrolled local/network reads.
* Registry.qualify invokes explicitly supplied trusted host Python and is not a sandbox.
* LocalExport writes exact finite JSON after separate prepare, approve and commit steps.

## Create-only export
An operator selects an existing regular local directory. A plan retains exact output bytes, flat
portable JSON basename, directory identity, input-state token and a deadline. Prepare writes nothing;
approve is an explicit host call and returns an in-process, one-use object. JSON cannot represent an
accepted approval. Commit rechecks every precondition, consumes approval, stages mode-0600 bytes,
flushes/fsyncs, rechecks time/state/directory, and uses exclusive hard-link installation. A competing
destination is not overwritten. Unsupported hard-link semantics refuse; there is no weaker fallback.
After installation, durability/readback problems are reported as actual effects with uncertainty.

This is a cooperative, operator-owned local filesystem contract. It is not a defense against malicious
Python, administrator, kernel, symlink races from a hostile host, physical power failure or arbitrary
network filesystems. Local time is supplied by the host. Process death may leave a hidden staging file;
there is no automatic recursive cleanup. Export is not publication, encryption or a secret scrubber.

No new target-effect adapter is supplied. Actual target changes still require the original T3 host
prepare/approve/commit path with its separately qualified simulated adapter. UI checkmarks and signed
observations are never accepted as automatic effect permission.
