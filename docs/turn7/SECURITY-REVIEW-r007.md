# r007 defensive review and repair record

The review subject was the r006 source inventory root
`198ff68682758f0af80380c6c3b5d68ddca74bbba8edb890d58057f0283c908c`.
Separate review sessions began without the builders' transcript. They retained original source
hashes, local failing witnesses and repair validation outside the candidate. The sessions belong
to the same agent team. This is engineering review; it does not satisfy the external independent
security approval required by the release profile. Automated review restrictions interrupted the
initial broader review route; the continued pass used defensive source review and ordinary local
regression tests against disposable databases and interpreter environments.

| Finding | Impact | Repair |
|---|---|---|
| SEC-001: SQLite conflict deletion bypasses cohort-only source fence | HIGH: native REPLACE-family writes could delete fenced source rows | BEFORE-write checks cover admitted UNIQUE keys, index collations and addressable rowid; unsupported unique-index expressions/partial predicates are refused; NULL/default substitution is guarded |
| SEC-002: copy inherits customer REPLACE/IGNORE policy | HIGH: copying could delete a control-cohort row or record an incomplete copy | INSERT OR ABORT overrides schema policy and transactionally preserves rows, state and ledger on conflict |
| SC-001: integrity observer starts Python site before verification | HIGH: unverified startup files could execute before refusal | -I -S bootstrap; verify complete installed file closure before adding purelib/importing packages; require an empty offline installer target |
| QUAL-001: actual GUI screenshot dependency absent | The previous sandbox limitation concealed a missing Pillow dependency | Thirteen-wheel native full profiles and matching qualification metadata include Pillow |
| QUAL-002: Linux wheel ZIP directory entries refused | Genuine Linux PyYAML wheel could not be admitted | Validate safe zero-length directory entries separately from immutable RECORD file closure |
| QUAL-003: limitation classification uses inspector OS | Cross-host verification could misclassify recorded Windows outcomes | Validate the recorded execution platform and use it for classification |
| QUAL-004: platform audit guesses command count | A complete release could fail aggregation, while omitted commands could be missed | Check the exact required release command identities and raw captures |
| QUAL-005: protocol test relies on an unarchived empty temp directory | A sealed source handoff fails despite passing in the authoring checkout | Use the runner-selected disposable temporary directory; no hidden source directory prerequisite |

Windows junction tests exercise real alias refusal in input, source packaging, database, collector,
export, CLI and worker-path boundaries. They supplement file-symlink fixtures. A missing Windows
symbolic-link privilege is still a limitation; POSIX FIFO execution requires a POSIX host.

The platform handoff and native dependency profiles are repository tools. They preserve source,
wheel, exact upstream Git bundles, immutable integration subject, runner and offline wheels as one
closed envelope, with fresh terminal custody. Cross-acquiring macOS wheels produces preparation
evidence only. A genuine macOS interpreter, display and full execution receipt are still required.

Re-run the full source and installed release workflow after registry/binding renewal. Retain its
current roots and raw logs with this review's original witnesses. No number of local passes closes
license selection, external review, production identity/adapter acceptance, native integration
acceptance or comparative operator study. Interpreter/OS trust, cooperative filesystems, source
coverage, power-loss behavior and hostile database-owner limits remain as documented in the profiles.
