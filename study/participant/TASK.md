# Participant task: a safe security-migration workflow

Build a solution to manage migration of a legacy delegation-token flow to a new flow. The system has
persisted data with policy references, producers, consumers and a long-running worker. Model cohorts
explicitly. Support phased rollout, scoped recovery and retirement. Expose a deterministic JSON
assessment explaining whether a requested transition is allowed, blocked or indeterminate and why.
Never regard missing observations as zero activity. A stalled but resumable worker must be accounted for.

You will receive the same source facts and discovery interface as the other arm. New stages are released
by the operator. Preserve working artifacts between stages. Use the tools assigned by the operator;
ordinary reusable models, policy engines and automation are permitted. Record actual setup, modeling,
adapter, coding, debugging, review and supervision effort. Do not invent hours for unobserved work.

Do not execute production changes. The operator supplies approved local test effects and hidden cases.
A signature or a correct hash alone does not establish recognized authority or deployment safety.
Progress matters: support legitimate completion when every required obligation is satisfied.
