# Replay from the admitted source

Install the supplied local wheel deliberately, prepare genuine operational/qualification
dependencies, and obtain the expected source root from the accompanying verification receipt.
Run from the extracted source directory; output must be outside it.

```sh
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase test-t1
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase test-t2
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase test-t3
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase test-t4
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase test-t5
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase tests
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase scenarios
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase examples
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase audit
python tools_t5/qualify.py --expected-source "$ROOT" --out /tmp/mmc-t5 --phase assemble
```

Each test group has its own terminal record. Missing groups, changed source, changed stage outputs,
wrong test identities, duplicate names, skipped/error cases or missing scenarios refuse aggregation.
No stage automatically regenerates model pins, source expectations or conformance oracles.
Add `--require-native-pippi` to demand that native gate; it deliberately refuses while unbound.
The `--expected-source` protects source relative to an accepted pin, not against a malicious host.

For one case: `mmc-foundry run lost-ack > result.json`. `mmc-foundry inspect --candidate result.json
--expected-root <accepted-root>` is non-effectful. `mmc-foundry replay lost-ack --candidate result.json
--expected-root <accepted-root>` reexecutes only in fresh temporary databases. The shell redirect
is an explicit user filesystem action. A successful CLI process does not approve production effects.

The source and wheel builders serialize the same frozen tree deterministically. Rerunning timed
logs or changing the execution environment is not expected to recreate the identical dossier.
Installed-wheel, final-extraction and current-platform qualifications are separate evidence legs.
