# ADR 0003: Two-path agent (deterministic fast path + Claude reasoning path)

## Status
Accepted

## Context
Every failed transaction needs a triage decision. The naive design calls
an LLM for all of them. The buildathon's judging criteria explicitly list
"AI judgment... where you chose not to use one" as something they read for.

## Decision
Split decline reasons into two groups at intake:

- **Unambiguous codes** (routed to the deterministic fast path): decline
  reasons where no plausible context would change the correct action —
  `card_reported_lost`, `account_closed`, `card_expired`,
  `invalid_card_number`. See the full table and the reasoning for each
  entry in `backend/app/agent/rules/decline_taxonomy.py`.
- **Context-dependent codes** (routed to the Claude reasoning path):
  decline reasons where the correct action genuinely depends on the
  specific case — `insufficient_funds`, `bank_timeout`,
  `authentication_failed`, `issuer_unavailable`, and any decline reason
  string not recognized by the fast-path table at all.

## Reasoning
- An unambiguous code getting an LLM call is wasted latency, wasted API
  cost, and — more importantly — a missed opportunity to demonstrate
  restraint, which is a graded criterion here.
- A context-dependent code getting a hardcoded rule is exactly the failure
  mode of every existing competitor (see `docs/POSITIONING.md`) — the same
  code always gets the same action regardless of the customer's history.
- The split itself is a design decision, documented and defensible, not an
  accident of what was easy to build.

## Consequences
- The fast-path table needs to be conservative: when genuinely unsure
  whether a code belongs in the unambiguous group, it goes to the
  reasoning path instead. False confidence in the fast path is worse than
  an unnecessary model call.
- The reasoning path's output confidence feeds the bounded executor's gate
  (ADR 0003 pairs directly with the executor design in
  `docs/architecture/overview.md`) — a low-confidence reasoning output is
  routed to `hold_for_review`, never auto-executed.

## Addendum: Integration with Economic Layer (ADR 0006)
Following the addition of the economic scoring layer, the executor now takes
in the full economic evaluation (`RecoveryDecision` options and metrics) and
returns a populated `RecoveryDecision` instead of the narrower
`TriageDecision`. This ensures that both the decision-path's candidate
action and the overriding economic justification are inextricably bound to
the execution result, avoiding split-brain where an action executes for
economic reasons but only the raw triage path is returned.
