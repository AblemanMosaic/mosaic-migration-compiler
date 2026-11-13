# r008 dependency security successor

The r006 defensive review and r007 repair record remain retained. Current r008 preserves the
SQLite conflict-fence/copy repairs and safe interpreter-startup checks, and adds active dependency
advisory remediation. Frozen requirements and acceptance oracles remain unchanged.

The original pip 26.0.1, cryptography 46.0.3 and Pillow 12.0.0 pins matched current OSV advisories.
The advisory review retained exact requests/responses and aliases; multiple records for one CVE
were deduplicated before reporting. MMC uses P-256 ECDSA/SHA-256 through fixed bytes/DER inputs,
and its Pillow use captures a trusted GUI screenshot and saves PNG. It exposes neither generic
PKCS#7/X.509 operations nor an arbitrary image-decoding API. This limits reachability; it is not
a reason to retain affected versions in current release environments.

Current `.v2` full profiles therefore select pip 26.3, cryptography 50.0.2 and Pillow 13.0.0.
The other ten exact pins are retained. The proposed thirteen-pin query returned no OSV matches
at 2026-11-10T06:34:25Z. Each actual acquisition performs and embeds its own dated snapshot,
binding exact pins, raw query/response bytes, service, timestamp and roots. Offline verification
rechecks those bytes and refuses known matches. The bootstrap verifies patched pip against its
reviewed official PyPI digest before importing any third-party parser or installer.

Upstream primary references:

- [cryptography security advisories](https://github.com/pyca/cryptography/security/advisories)
- [bundled OpenSSL advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-537c-gmf6-5ccf)
- [Pillow security advisories](https://github.com/python-pillow/Pillow/security/advisories)
- [Pillow bundled OpenJPEG advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-78g4-xqwv-q3g8)
- [pip security advisories](https://github.com/pypa/pip/security/advisories)
- [OSV query API](https://google.github.io/osv.dev/post-v1-querybatch/)

The original embedded twelve-wheel Windows closure remains an immutable historical input.
Current release verification rejects that profile before installation; it cannot acquire a
current qualification label by rehashing an old lock. Current binary profiles cover Windows x64,
Linux x64 and macOS ARM64. Intel macOS is blocked because the patched upstream cryptography
wheel is unavailable; no affected-wheel fallback or unobserved source build is supplied.

OSV snapshots are dated service observations, not independent security approval or a claim of
no vulnerabilities. Host interpreter, standard library, OS, native system libraries and external
production custody remain separately declared trust dependencies. The release channel remains
an alpha review candidate. External review, owner license selection, native integration acceptance,
production adapter/identity qualification, and the comparative study remain separate gates.

Platform outputs require persistent custody. A prior Linux run completed but its `/tmp` evidence
was lost after a WSL restart, so its summary was not admitted as release evidence. Use persistent
output and preserve the exact raw evidence outside disposable VM storage before the host exits.
The local UAC wrapper only launches the sealed repository runner with a user-approved administrator
token; the qualification logic remains the repository program. Its exact script and terminal records
are retained as launch evidence rather than silently treated as installed MMC functionality.
