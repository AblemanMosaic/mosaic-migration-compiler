# UCM-governed evidence scope and requalification

MMC's release root always commits to the complete source and release envelope. Changed bytes
therefore create a new artifact identity. Revision r013 uses UCM r038's
`EVIDENCE_SCOPE_AND_REQUALIFICATION_DISCIPLINE` to answer the separate question: which claims have
actually lost their evidence dependency closure and which work lanes must run again?

MMC does not implement that decision engine. `tools_t7/evidence_scope_adapter.py` owns only the
application mapping. The exact UCM CLI builds and validates the evidence-scope profile,
claim-dependency map, and requalification-impact record through these registered surfaces:

- `BUILD_EVIDENCE_SCOPE_PROFILE`;
- `BUILD_CLAIM_DEPENDENCY_MAP`;
- `EVALUATE_REQUALIFICATION_IMPACT`.

The adapter maps every admitted source file into exactly one of UCM's seven roles:
`RUNTIME_EFFECTS`, `PROTOCOLS_SCHEMAS`, `ADAPTERS`, `TESTS`, `VALIDATORS`,
`PACKAGING_CI_DOCS`, or `EXTERNAL_DEPENDENCIES`. Unknown files refuse construction. Each component
keeps state, semantic, governance, and environment commitments separate. The external component is
complete only when the dependency lock, CMBA a4/a7 and DKN wheel roots, the r036 UCM integration
identity, the r038 P/PPI source-manifest root, SemCrys identity, and migration-subject root are all
present. Product correspondence and qualification governance are deliberately separate inputs.

## Claim denominator

The MMC adapter declares runtime, protocol, adapter, test, validator, packaging, portability,
release-integrity, and migration-lifecycle claims. UCM computes each transitive component closure.
Mutation and observation claims carry freshness rows; retained raw receipts may be revalidated only
where the claim explicitly permits it. A changed mutation dependency is held for a fresh authorized
lane and is never replayed automatically.

UCM returns one typed disposition per claim: `RETAIN`, `REVALIDATE_RAW_EVIDENCE`,
`RERUN_PURE_CHECK`, `REFRESH_OBSERVATION`, `EFFECTFUL_CASE_HELD_FOR_AUTHORIZED_LANE`, or
`FULL_QUALIFICATION`. Incomplete closure, denominator drift, policy/jurisdiction drift, or unknown
freshness broadens qualification. Release-candidate impact plans retain the complete final
denominator and never themselves qualify a release.

## Legacy index

`tools_t7/qualification_index.py` remains as a source-component inventory for compatibility with
existing release records. Its `compare` surface now always refuses with
`REUSE_REFUSED_UCM_REQUALIFICATION_IMPACT_REQUIRED`. In particular, equality of two empty external
binding dictionaries cannot authorize reuse.

## Workflow

During development, build the predecessor and successor profiles and ask the exact UCM CLI for an
impact plan. Run or revalidate only the typed affected lanes. Before the final expensive campaign,
freeze the candidate and bind a review-saturation root. The final release campaign still uses its
complete declared denominator once. Every new release receives new source, manifest, archive, and
release roots.

These records have standing `INFORMATION_ONLY`, authority effect `NONE`, real A5 false, and G0
closed. They do not grant migration, publication, installation, deployment, or independent-review
authority.
