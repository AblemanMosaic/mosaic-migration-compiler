# Implemented interfaces

```python
from mosaic_mmc import (
    canonical, decode, digest, validate_model, compile_model, verify_compilation,
    profile_reference, capabilities, program_inspect, MMCError,
)
```

| API | Exact scope |
|---|---|
| canonical(value) | Bounded T1 canonical JSON bytes; no floats, duplicate input keys, surrogate strings or coercion |
| decode(raw, canonical_only=False) | Size-bounded strict UTF-8 parsing; optional exact canonical spelling |
| validate_model(model) | A detached normalized model; validates declared relationships, not actual deployment |
| compile_model(model) | Deterministic compilation envelope; no clock, network, evaluator plugin or effect call |
| verify_compilation(model, candidate, expected_model_root=...) | Recompile and compare every canonical output byte; expected model pin required |
| profile_reference() | The installed fixed foundation contract reference |
| capabilities() | Only actual available read-only operations and current limitations |
| program_inspect() | Program counts and due case identities; not a qualification result |

## CLI
`mmc capabilities`; `mmc program-inspect`; `mmc model validate INPUT.json`;
`mmc compile INPUT.json`; `mmc ir verify MODEL.json COMPILED.json --expected-model-root HASH`;
`mmc request REQUEST.json`; `mmc --version`. Use '-' for one size-bounded stdin input.
Two simultaneous '-' arguments refuse. The later planned init/discover/commit/controller commands
are NOT advertised as implemented.

Read-only request shape is exactly schema=`mmc.request.t1`, operation, arguments.
Operations: model-validate {model}; compile {model}; verify-ir {model,compilation,expected_model_root};
capabilities {}; program-inspect {}. Unknown operations/arguments refuse. Response includes schema,
operation, ok and result. Typed refusals contain an error code/path/detail and authority_effect NONE.
Argparse command syntax failures use argparse's standard stderr/exit-2 surface, not a protocol result.

Exit 0 means the computation completed. COMPILED_WITH_STATIC_BLOCKERS is a legitimate compilation
result and may exit 0. It is never operational approval. Interpretation requires reading result
fields, not just the exit code. Library errors raise MMCError; command operation errors exit 2.

## Hashes
canonical-model identifies the normalized declared model. foundation-profile identifies the exact
selected wire/rule contract. compiler-realization identifies installed package source/data.
workflow-ir identifies the derived IR. compilation-receipt binds those identities and scoped result.
None is a signature. Caller-owned expected pins are not obtained merely by believing an input bundle.

## Structured schemas
model.t1.schema.json is a frozen normative shape reference. Additional exported output schemas aid
consumers; JSON Schema cannot enforce hashes, reference resolution, ordering, or semantic lowering.
Those checks are performed by the implementation and exact recompilation, not by shape alone.

## CLI compilation framing
`mmc compile` emits the standard response envelope around its compilation result. `mmc ir verify`
accepts either the bare library compilation or that exact successful compile envelope. It unwraps
only schema=mmc.response.t1, operation=compile, ok=true with no extra fields; integer 1 is not true.
The JSON ABI's verify-ir operation still takes the bare compilation as specified. In either case
actual recompilation is required. The framing flag supplies no permission or cryptographic evidence.
