# Replay and qualification

Run only an accepted source tree. The source pin is in the separately delivered verification record
and provenance/SOURCE-ADMISSION.json. Reading that same untrusted file is not independent recognition.

```sh
python tools/qualify.py --expected-source YOUR_ACCEPTED_ROOT --out /tmp/mmc-run --phase tests
python tools/qualify.py --expected-source YOUR_ACCEPTED_ROOT --out /tmp/mmc-run --phase examples
python tools/qualify.py --expected-source YOUR_ACCEPTED_ROOT --out /tmp/mmc-run --phase assemble
python tools/check_model.py --tests /tmp/mmc-run/tests.json
python tools/check_vectors.py
python tools/package.py --source /tmp/mmc-rebuilt.zip --wheel /tmp/mosaic_migration_compiler-0.1.0a1-py3-none-any.whl
python tools/package.py --verify /tmp/mmc-rebuilt.zip
```

On Windows use an existing prepared Python 3.12+ environment and explicit drive paths instead of
/tmp. That is an instruction, NOT Windows execution evidence. Symlink/FIFO tests are platform-specific;
missing privileges or unsupported prerequisites are not turned into passing assertions.

The runner admits the exact source BEFORE test imports. It independently collects unittest IDs,
compares them with the frozen test registry, records every result and completed terminal status,
checks source again, and hashes raw outputs. Assembly checks exact stage fields, output names,
output bytes, types, test identities/counts and common environment. Evidence must live outside the
source tree. Stages are create-only: use a new output directory for a new run.

--require-native-pippi explicitly refuses while native binding is unavailable. No alternate locally
invented pipeline satisfies that requirement. The protocol itself never invokes tests or agents.

Program qualification additionally requires exact freeze, model, vectors, examples, fresh extraction,
outside-source wheel installation and closed archive legs. The test/example assembler alone clearly
returns PASS_TESTS_AND_EXAMPLES_ONLY. Full capability-layer status is in the final external receipt and evidence.
No source checker regenerates frozen expectations, contracts, test lists or realized bindings.

Reproducible packaging means serializing the SAME frozen tree; rerunning timed logs yields different
evidence bytes and is not claimed to recreate a historical dossier. Source ZIP uses ZIP_STORED,
fixed timestamps/modes and POSIX-relative ASCII ordering. Wheel is built with a complete RECORD.
Private scratch files or arbitrary unlisted output trees are not admitted into a closed archive.
