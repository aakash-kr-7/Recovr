# ADR 0006: Economic decision layer — three separate structures, not one

## Status
Accepted

## Context
The triage pipeline (ADR 0003) selects an action for each failed
transaction, but today that action carries no economic reasoning: there
is no record of *how much* recovery the system expected, what it cost to
attempt, or whether the actual result matched the prediction. Without
these numbers the evaluation report can show accuracy (did the system
pick the right action?) but cannot show value (did the system's
decisions earn more than they cost?).

The dashboard needs to display expected-vs-actual recovery, and the
evaluation report needs to aggregate net recovery across batches. Both
require structured data, not free-text reasoning.

## Decision
Add three new structures to the domain model:

1. **RecoveryOption** (Pydantic schema only, no ORM table) — the
   economics of one candidate action: estimated probability, expected
   recovery, cost, risk penalty, net recovery, and a human-readable
   supporting-evidence string. There are several of these per decision.
2. **RecoveryDecision** (Pydantic schema + ORM table
   `recovery_decisions`) — the system's chosen action for a transaction,
   plus the full list of RecoveryOptions it evaluated (stored as JSON),
   the winning option's net recovery, the margin over the next-best
   option, confidence, reasoning text, which path produced the decision,
   and whether the confidence gate intervened.
3. **RecoveryOutcome** (Pydantic schema + ORM table
   `recovery_outcomes`) — the measured result after execution: actual
   recovery in INR, success boolean, and variance against the expected
   recovery at decision time. Populated asynchronously.

RecoveryDecision and RecoveryOutcome are stored in **separate tables**.

## Reasoning
The core principle, already established in `docs/architecture/overview.md`,
is: never let an expected value and a measured outcome share a row.

- **When they share a row**, it is trivially easy to overwrite
  `expected_recovery_inr` with `actual_recovered_inr` (or vice versa)
  during an update, silently destroying the comparison the evaluation
  report depends on. This is not a hypothetical risk — it is the
  default failure mode of any "just add more columns to the same row"
  schema when the update path has any async component.
- **When they are separate tables**, the system writes the decision row
  at decision time and the outcome row at outcome time. Neither row is
  ever updated; both are append-only. The evaluation report joins them
  on `transaction_id` to compute variance, and if the join produces no
  match, the outcome is simply "not yet known" — which is the correct
  state, not a data integrity failure.
- **RecoveryOption is schema-only** (not its own table) because options
  are never queried individually in SQL — they are always loaded as a
  batch from the decision's `options_json` column. Giving each option
  its own row would add a join for every audit-trail detail view with
  no compensating benefit.

The options list is stored as a JSON column on `recovery_decisions`,
matching the existing `customer_history` JSON column pattern in
`transaction.py`. This is consistent with the project's established
convention: use JSON for variable-length nested data that is displayed
as a unit, use real columns for scalar values that need to be filtered
or aggregated in SQL.

## Alternatives considered
- **Single combined table** (decision + outcome in one row) — rejected
  because it violates the estimate-vs-measurement separation principle.
  The update path from "decision written" to "outcome received" would
  be an in-place mutation, not an append, making it impossible to
  guarantee the original expectation is preserved.
- **RecoveryOption as its own ORM table** with a foreign key to
  `recovery_decisions` — rejected because options are never queried
  individually and the extra join penalizes the most common read path
  (audit-trail detail view) with no benefit to any write path.
- **Storing options as a separate Pydantic list field without JSON
  persistence** — rejected because the audit trail must show the full
  option set even if the scoring formula changes between decision time
  and audit-review time.

## Consequences
- The scoring formula (next prompt) will produce a `RecoveryDecision`
  containing a ranked list of `RecoveryOption`s. The executor will read
  the `selected_action` from this decision.
- The outcome writer (in the webhook handler for real transactions, and
  in the evaluation script for synthetic data) will create a
  `RecoveryOutcome` row when the result is known.
- The evaluation report will join `recovery_decisions` and
  `recovery_outcomes` on `transaction_id` to compute calibration
  metrics: mean variance, systematic bias, and value-weighted accuracy.
- Adding a new action to `TriageAction` requires no schema migration on
  these tables, since `selected_action` and `action` are stored as
  plain strings, not SQL enums — matching the existing convention.
