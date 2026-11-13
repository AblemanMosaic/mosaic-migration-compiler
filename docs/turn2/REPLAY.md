# Exact-source replay

Verify the delivery/archive hash using an independently accepted expected value before extracting.
Use a fresh directory and the source-admission root in the current receipt. Do not regenerate the
source pin from an untrusted candidate and call that independent recognition.

```sh
python tools_t2/qualify.py --expected-source <accepted-source-root> --out /tmp/mmc-t2 --phase tests
python tools_t2/qualify.py --expected-source <accepted-source-root> --out /tmp/mmc-t2 --phase examples
python tools_t2/qualify.py --expected-source <accepted-source-root> --out /tmp/mmc-t2 --phase audit
python tools_t2/qualify.py --expected-source <accepted-source-root> --out /tmp/mmc-t2 --phase assemble
python tools_t2/package.py --source /tmp/mmc-t2.zip --wheel /tmp/mmc-t2.whl
```

Every stage uses source admission before test imports/subprocesses, exact test-identity coverage,
typed terminal status, environment equality, and hashed closed output sets. Evidence directories
must be outside the source. A repeated stage needs a new directory; earlier failure is not erased.
A caller requiring --require-native-pippi receives an explicit refusal because native binding is
absent. This is a correct gate, not native execution. Fresh extraction, installed wheel, and source/
wheel byte reproducibility are separately completed evidence legs in the external release receipt.

The tests use unittest and the compiler runtime uses Python's standard library. No third-party
runtime dependency is downloaded/required. To replay installed behavior, create an isolated venv,
install only the local wheel with --no-deps --no-index, then run from outside the source tree.
Actual Python/OS versions in receipts are evidence; supported-version metadata is not execution.

Frozen-tree reserialization is reproducible. Regenerating elapsed-time logs is NOT claimed to
produce identical source/dossier bytes. All records are unsigned same-author engineering evidence.
