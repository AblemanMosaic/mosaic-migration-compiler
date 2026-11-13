# Enrolled SQLite table migration

`mosaic_mmc_product.sqlite_target.SQLiteTargetAdapter` migrates actual preexisting application
tables. It does not construct the application's source data or select a path from an effect
request. A trusted host explicitly enrolls one existing regular SQLite database and an exact
closed manifest. Worker construction reopens enrollment and cannot enroll a new database.

The manifest selects source/destination table names, ID/cohort/payload/checksum column names,
one migration and model cohort, a finite cohort roster, three model target-role IDs, and row/UTF-8
payload limits. Identifiers use a small closed alphabet; no SQL text, expression, import path,
credential or arbitrary command is accepted. The manifest and exact customer/owned schema are
committed in the descriptor identity. A changed enrollment cannot substitute for the old descriptor.

Customer tables must be ordinary tables with exactly three (source) or four (destination) TEXT
columns, explicit NOT NULL constraints, one ID primary key and no foreign keys or foreign triggers.
The application creates both tables before enrollment. The selected destination cohort must be
empty. Enrollment preserves existing customer rows and the application's SQLite application ID.
Declared control cohorts can have destination data already present. Customer constraints may refuse
copy; copying explicitly uses the ABORT conflict policy, overriding schema-level REPLACE or IGNORE,
and the transaction then rolls back all inserted rows, target changes and the ledger entry.
Source UNIQUE indexes must use ordinary enrolled columns with BINARY, NOCASE or RTRIM collations.
Partial and expression UNIQUE indexes are refused because their conflict predicates are outside
this adapter's closed fence model. Nonunique indexes remain supported and pinned.

Selected cohort comparisons and inventory ordering explicitly use BINARY collation, even when a
customer column declares NOCASE. Thus case-distinct tenants do not share a fence or copy scope.
The adapter refuses case aliases for table and column identifiers. New undeclared source cohorts
are refused by the installed fence triggers rather than silently acquiring write permission.

MMC creates prefixed enrollment, target-state, control and operation-ledger tables plus writer
triggers. The source triggers enforce insert, update, delete and cohort-move fencing. Before insert
and update, they also check whether any admitted unique key or addressable hidden rowid would
replace an existing fenced row. This does not depend on a client enabling recursive triggers.
Explicit NULL insert/update values are refused before SQLite can substitute a NOT NULL default
under a REPLACE policy. Omitted columns with non-NULL defaults remain supported; the adapter
does not independently evaluate default expressions.
The rowid check fails closed when SQLite reports an unspecified insert rowid as -1 and a fenced
row already has that rowid; an explicit unused rowid or a WITHOUT ROWID table avoids that ambiguity.
A monotone
control trigger refuses reopening legacy writes. Every schema object attached to the customer and
metadata tables is pinned, including foreign-named triggers and indexes. Schema/trigger/enrollment
checks run again on each effect and observation. The adapter assumes a cooperating local database owner; an owner who
can remove triggers, rewrite all custody or restore an old database remains outside this boundary.

The seven lifecycle transitions use the existing finite migration model: prepare, canary, coexist,
fence, reconcile/copy, cutover and retire. Customer row copies, target compare-and-swap, monotone
cohort security state, and the operation ledger commit in one transaction. Cutover and retirement
recheck actual row payloads and checksums inside that transaction. Compensation is qualified only
for cutover recovery and preserves the writer fence, revocations and security floor. It does not
delete copied data, restore revoked authority or reopen the old producer.

The backend ID and model adapter are `sqlite.table-migration.v1`. The T3 descriptor uses mode
`SQLITE_TABLE_MIGRATION` and effect `MIGRATE_ENROLLED_SQLITE_TABLES`; `production` remains false.
Host enrollment is `SQLiteTargetAdapter.enroll(path, manifest, initial_states, floor=5, revoked=...)`.
`SQLiteTargetAdapter(path)` reopens only. The effect ABI remains descriptor/snapshot/lookup/apply.
`workload_snapshot()` provides bounded normalized observations; it does not establish complete
discovery outside the enrolled tables and supplied roster.

`run_target_qualification()` creates independently named customer credential tables, seeds 32
selected rows and a control tenant before enrollment, then runs the native controller through
authenticated process transport. It verifies lost acknowledgment followed by fresh-controller and
fresh-transport ledger reconciliation, same-process dormant native-SQL writer refusal, compensating
recovery, renewed cutover, retirement, control-tenant writes and an independent SQL inventory match.
The entire target is inside an owned disposable directory. Public signed evidence/approval fixtures
are used; they are not production recognition or external authority. A direct in-process baseline is
available only through the trusted Python keyword `authenticated=False` for comparison tests.

This qualifies a real local storage adapter in a disposable environment. It does not qualify live
customer operations, hostile-host isolation, cross-host transactions, distributed exactly-once,
physical power loss, or arbitrary SQLite schema transformations.
