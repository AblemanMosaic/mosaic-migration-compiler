# Windows qualification

Release Convergence fixes a real cross-platform identity defect: T2, T3, and T5 package walks now sort by normalized
relative POSIX path rather than host `Path` ordering. The predecessor T2/T3 implementation-bound vectors
are retained under `provenance/turn7/`, and successor vectors bind the repaired realization.

This establishes deterministic path ordering on the observed Windows host. It does not turn the
`py3-none-any` wheel tag into evidence for every target platform. Windows symbolic-link tests still
depend on the host's link-creation privilege; lack of that privilege is a platform-fixture limitation,
not evidence that link refusal was exercised. Junction refusal remains implemented in runtime path checks.

Target-platform claims require their own exact replay receipts. The final Release Convergence receipt reports only
the host and legs actually executed.

The managed Windows sandbox can also prohibit loopback sockets, hard-link creation, and interactive
Tk capture. Qualification records those exact test identities as host limitations; it does not relabel
them as passes. Behavioral failures outside the closed limitation set fail the run.

The r007 runner requires the admitted test-ID registry and records each outcome and failure detail. Failed subtests,
expected failures, unexpected successes and empty discovery cannot become implicit passes. A GUI
skip requires a direct OS fixture probe to return Windows hard-link permission error 5; arbitrary
GUI errors are never classified as environmental. Historical mismatch exceptions match the exact
known error, and a separate audit checks every later predecessor row and all T5 obligation bindings.

Use the full Windows dependency profile, including Pillow, when the host allows the GUI smoke
to reach its screenshot check. Real directory-junction tests also exercise input, package,
database, collector, export, and worker path refusal without symbolic-link privilege. They
supplement the original file-symlink fixtures; unsupported POSIX FIFOs and denied file-symlink
creation remain explicit nonpasses on Windows. Cross-host verification classifies limitations
using the recorded execution platform, rather than the machine inspecting the receipt.
