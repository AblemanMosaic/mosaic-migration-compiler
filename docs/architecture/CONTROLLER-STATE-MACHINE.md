# Controller state machine

The Capability Layer 3 controller is an event-sourced local state machine. Input data cannot select
or construct an adapter; the trusted host supplies an admitted adapter object. Replay reads only the
journal and never calls an adapter.

## Operation transitions

| Current state | Event | Required condition | Next state | External target effect |
|---|---|---|---|---|
| — | `PREPARED` | Current plan, evidence, target pre-state and adapter descriptor match | `PREPARED` | None |
| `PREPARED` | `APPROVED` | Every required jurisdiction supplies a current scoped approval | `APPROVED` | None |
| `PREPARED`, `APPROVED`, `NOT_APPLIED` | `CANCELLED` | No unresolved or confirmed effect | `CANCELLED` | None |
| `APPROVED`, `NOT_APPLIED` | `DISPATCHED` | Evidence, authority, expiry, target pre-state and retry budget recheck | `DISPATCHED` | None; durable intent only |
| `DISPATCHED` | adapter `apply` | Durable intent and bounded recovery capacity already exist | unchanged until `OUTCOME` | Host-selected adapter may change its target |
| `DISPATCHED`, `UNKNOWN`, `RECOVERY_REQUIRED`, `NOT_APPLIED` | `OUTCOME: APPLIED` | Closed result matches exact request and post-state | `APPLIED` | Confirmation only |
| same | `OUTCOME: PARTIAL` | Closed result identifies the changed request targets and exact observed states | `RECOVERY_REQUIRED` | Confirmation of partial target change |
| same | `OUTCOME: UNKNOWN` | Closed bounded uncertainty record | `UNKNOWN` | Unknown; reconcile before retry |
| same | `OUTCOME: NOT_APPLIED` | Qualified adapter ledger reports absence | `NOT_APPLIED` | None confirmed; retry still requires all rechecks |

An `APPLIED` outcome releases the migration's pending-operation reservation. A partial outcome marks
the migration recovery-required. Compensation is a new prepared and approved operation over the
declared inverse transition; it does not erase the original event history or lower security state.

## Durable ordering and capacity

Every controller append occurs in one SQLite write transaction and is followed by projection of the
entire candidate history. The transaction commits only if the aggregate history and resulting state
remain within the canonical node, byte, depth and event-count limits. A capacity refusal rolls back
the row, so a successful append cannot make the journal unreadable.

While an operation is `DISPATCHED`, the admission check also simulates a maximum closed `PARTIAL`
outcome followed by a terminal `APPLIED` reconciliation. While it is `UNKNOWN` or
`RECOVERY_REQUIRED`, it simulates the terminal reconciliation. Other journal writes are admitted only
if these reservations still fit. Consequently, capacity exhaustion is detected before `apply` and
cannot be consumed by unrelated evidence writes while an external result is unresolved.

## Claim boundary

This state machine provides cooperative local SQLite durability and bounded recovery for qualified
adapters. It does not establish hostile-host safety, disk-full or power-loss guarantees, distributed
exactly-once behavior, production authority, identity custody, or the completeness of external
evidence. Those remain deployment and qualification obligations.
