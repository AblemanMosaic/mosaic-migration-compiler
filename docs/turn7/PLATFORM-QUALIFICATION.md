# Exact platform qualification handoff

`tools_t7/platform_qualification.py` prepares, verifies, executes and audits a portable
qualification envelope. Preparation and cross-target wheel acquisition do not establish
native execution. Linux under WSL is reported with its actual kernel release. A missing
macOS run remains missing even when both macOS envelopes are ready.

Current `.v2` full profiles target native CPython 3.12 on Windows x64, Linux x64 and macOS
ARM64. They pin pip 26.3, cryptography 50.0.2 and Pillow 13.0.0, with the other ten original
pins unchanged. Their locks retain the exact dated OSV query/response snapshot, checked
offline during qualification. `NO_MATCHES_AS_OF_SCAN` reports that query result; it is not
proof that vulnerabilities are absent. Wheel payloads remain external to the source archive's
64 MiB boundary. The original twelve-wheel Windows embedded lock remains historical and
cannot satisfy current release verification. Earlier `.v1` full profiles belong to archived
r007 source and retain their known dependency-review findings.

The current macOS Intel profile is `BLOCKED_UPSTREAM_PATCHED_WHEEL_UNAVAILABLE`.
Cryptography 49 removed macOS x86_64 support; the patched 50.0.2 release has no Intel wheel.
Current qualification does not substitute an older affected crypto release or an unqualified
source build. Preparing the ARM64 handoff does not close the missing macOS execution gate.

The target needs CPython with venv and tkinter, Git, writable regular local storage,
loopback networking, hard-link support and an actual display. Linux may use explicitly
provisioned Xvfb with `xvfb-run` and `xauth`. Windows file-symbolic-link tests need the actual
link-creation privilege. macOS needs a logged-in graphical session and any OS screenshot
consent its display configuration requires. The runner does not grant privileges or install
OS packages. Missing fixtures remain failures or explicitly recorded host limitations.

Acquire an exact native closure into fresh custody:

```text
python -I -S -B tools_t7/dependencies.py --acquire-bundle FRESH_BUNDLE --profile linux-cpython312-x86_64-full-qualification.v2
```

For macOS acquisition on another host, select the ARM64 `.v2` full profile and add `--cross-target`.
This downloads genuine binary wheels for macOS 11 or later and checks official PyPI digests,
CPython wheel tags and target dependency markers with the verified pip parser. Its receipt
reports acquisition only. Native verification and installation never allow `--cross-target`.
Acquisition bootstraps pip 26.3 directly with the standard library, verifies official PyPI
metadata against the embedded wheel hash and checks wheel bytes/RECORD before importing pip.
It never imports the historical vulnerable installer to acquire its replacement.
Review and separately retain the resulting lock root. Preserve a failed acquisition directory;
`--author-lock --dependency-bundle BUNDLE --profile PROFILE` can finish metadata authoring
over its exact downloaded wheels. Add `--cross-target` only for a macOS acquisition profile.

After source binding renewal and test-registry review, seal the exact inputs:

```text
python -I -S -B tools_t7/platform_qualification.py prepare --out FRESH_HANDOFF --expected-source SOURCE_ROOT --ucm-source UCM_ROOT --pippi-source EXACT_PIPPI_R038_SOURCE --semcrys-source SEMCRYS_ROOT --subject IMMUTABLE_T6_SUBJECT --dependency-bundle BUNDLE --dependency-lock-root LOCK_ROOT --cmba-a4-wheel CMBA_A4_WHEEL --cmba-a7-wheel CMBA_A7_WHEEL --dkn-rc5-wheel DKN_RC5_WHEEL
```

The envelope includes the copied standard-library bootstrap, source archive and wheel,
three exact native integration wheels,
offline lock/requirements/every wheel, complete Git bundles for pinned product UCM/SemCrys
heads, the exact P/PPI r038 source-manifest closure, and the immutable subject archive.
The product UCM identity and P/PPI process-standard identity are distinct and independently
bound. `HANDOFF.json` binds every file and required path.
Retain its root separately. After transferring the unchanged directory, run its actual bootstrap:

```text
python -I -S -B RUNNER.py verify --handoff HANDOFF_DIRECTORY --expected-handoff HANDOFF_ROOT
python -I -S -B RUNNER.py run --handoff HANDOFF_DIRECTORY --expected-handoff HANDOFF_ROOT --out FRESH_OUTPUT
```

The runner checks the complete envelope before importing candidate code, refuses reused
custody, validates the native profile and reconstructs exact source/wheel/Git inputs without
line-ending conversion. It executes the repository release verifier and retains stdout,
stderr, exit status and `PLATFORM-EXECUTION.json`, including failures. Each release command
also retains its start/terminal records. `--preflight` remains `PASS_PREFLIGHT_ONLY`.

Audit actual full executions against the final source head:

```text
python -I -S -B tools_t7/platform_qualification.py audit --expected-source SOURCE_ROOT --execution FIRST_OUTPUT --execution SECOND_OUTPUT --out FRESH_AUDIT.json
```

The audit rechecks identities, test outcomes/logs, source/wheel bytes, exact command captures
and installed target-migration evidence. Missing platforms and actual limitations remain
visible. These unsigned same-author records are engineering evidence. Independent acceptance,
native integration, production qualification and public-release clearance remain separate gates.

The matrix separately derives `platform_inapplicable_tests` for exactly two Windows POSIX FIFO
fixtures: the precise declared POSIX-unavailable skip and the missing `os.mkfifo` attribute error.
Their recorded SKIP/ERROR outcomes and raw host limitations remain unchanged; neither becomes a
pass. Other errors, causes or host platforms remain actionable. Three-platform matrix completion
requires all three actually executed hosts and no `actionable_host_limitations`.
