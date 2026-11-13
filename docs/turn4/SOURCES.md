# Sources and evidence classes

Primary construction sources: the exact supplied MMC Capability Layer T3 archive (SHA-256
58126d03d272b2c0276b3a1940acc1523b749145d279e6d3565d1d930b0eb054), its handoff,
the byte-preserved full PROGRAM/REQUIREMENTS/ACCEPTANCE files, and the user instruction Capability Layer T4 — go.
No native P/PPI interpreter/host was supplied. The prior audit's distinction between local artifact
discipline and native admission is preserved rather than invented away.

Optional exact code inputs are recorded in src/mosaic_mmc_t4/data/native-pins.json and baseline/.
They are compatibility/reference readers, not substitutes for current external approval.

Official implementation references consulted: Python sqlite3 documentation for URI readonly and
transaction/query controls; urllib.request for request handlers and explicit proxies/redirect policy;
tkinter for the native event loop. Online documentation can describe newer Python releases; actual
execution here is identified separately in receipts (Python 3.13.5), not inferred from documentation.
These sources supply API context, not qualification evidence for MMC. Exact checks are source-bound
in the local test and replay records. No third-party benchmark or vendor claim is imported as PASS.
