# Architecture Overview

## The Core Idea

Not every failed payment needs an AI model to reason about it. A card that was reported stolen has one correct action (do not retry, escalate to dunning) and no amount of context changes that. A payment that timed out mid-authorization might mean multiple different things depending on who the customer is, recent retry frequency, and historical patterns. The system routes each failed transaction down one of two paths based on how much the decline reason alone tells you.

```
                    Razorpay webhook: payment.failed
                                │
                                ▼
                  ┌─────────────────────────┐
                  │  Confidence gate        │
                  │  (app/agent/gate.py)    │
                  └────────────┬────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   ┌───────────────────────┐       ┌─────────────────────────────┐
   │ Deterministic fast    │       │ Reasoning path (Groq/Claude)│
   │ path                  │       │ app/agent/reasoning.py      │
   │ app/agent/rules/      │       │                             │
   │                       │       │ Given: decline reason, last │
   │ Fixed table: decline  │       │ N transactions for customer,│
   │ code → action, no     │       │ time-of-day, prior triage   │
   │ model call. Used only │       │ decisions, raw error text.  │
   │ when code is          │       │ Reasons in natural language,│
   │ unambiguous (e.g.     │       │ outputs allowed action plus │
   │ card_reported_lost,   │       │ structured confidence score.│
   │ account_closed).      │       │                             │
   └────────────┬──────────┘       └──────────────┬──────────────┘
                └────────────────┬────────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ Economic scoring engine      │
                  │ app/agent/economics/         │
                  │                              │
                  │ Ranks permitted actions by   │
                  │ expected net recovery:       │
                  │ P × Amount × Fraction − Cost │
                  │ − Risk Penalty.              │
                  │ If optimal action differs    │
                  │ from candidate, economics    │
                  │ choice wins.                 │
                  └──────────────┬───────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ Bounded action executor      │
                  │ app/agent/executor.py        │
                  │                              │
                  │ - Action MUST be in allow-   │
                  │   list (retry_same_rail,     │
                  │   retry_alt_rail, dunning,   │
                  │   hold_for_review, no_action)│
                  │ - Spend cannot exceed batch  │
                  │   spend cap (₹50k limit)     │
                  │ - Low-confidence reasoning   │
                  │   fails-close to             │
                  │   hold_for_review            │
                  └──────────────┬───────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ Execute on Razorpay test     │
                  │ mode (or bounded simulation) │
                  └──────────────┬───────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ Audit log & Decision storage │
                  │ (AuditEntry, RecoveryDecision│
                  │  RecoveryOutcome rows)       │
                  │                              │
                  │ transaction_id, path_taken,  │
                  │ evaluated options, verbatim  │
                  │ reasoning, confidence,       │
                  │ outcome, and timestamp.      │
                  └──────────────┬───────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ Operations Console           │
                  │ (React + Vite + Blade tokens)│
                  │                              │
                  │ Dashboard, Live Mode Stream, │
                  │ Recoveries, Decision Detail, │
                  │ Audit Trail, Evaluation      │
                  └──────────────────────────────┘
```

---

## Why Two Paths, Not One

Calling an LLM for every decision is slower, costs money per call, and — more importantly — is worse engineering when a deterministic answer exists. The buildathon's judging criteria explicitly reward "the right tool in the right place, and where you chose not to use one." The fast path is not a shortcut; it is the direct answer to that criterion. See [`docs/decisions/0003-two-path-agent.md`](../decisions/0003-two-path-agent.md) for the full reasoning and the specific decline codes routed to each path.

---

## Why the Executor is Separate from Reasoning

The reasoning path can be wrong, hallucinate, or produce low-confidence conjectures. The executor cannot trust it blindly. By keeping "decide" and "act" as separate components with a hard allow-list and spend cap in between, an anomalous reasoning output degrades to `hold_for_review`, never to unverified money movement. This is the direct implementation of the buildathon's stated bar: every financial action explainable, bounded, and gated.

---

## Economic Scoring Layer

RECOVR does not merely pick a categorical label; it scores all five permitted actions:
1. `retry_same_rail`: Immediate or scheduled retry on the identical payment method.
2. `retry_alt_rail`: Retry routed through an alternate rail (e.g., UPI instead of Card).
3. `escalate_to_dunning`: Issue a customer-facing Razorpay test-mode Payment Link via email/SMS.
4. `hold_for_review`: Pause automatic handling and route to a human operations queue.
5. `no_action`: Terminate recovery to avoid unnecessary gateway fees or compliance penalties.

The scoring formula:
$$\text{Expected Net Recovery} = \text{Probability} \times \text{Amount} \times \text{Recovery Fraction} - \text{Action Cost} - \text{Risk Penalty}$$

Where:
- **Probability** is estimated via empirical Bayes Beta-shrinkage heuristics with structural zeros for impossible actions.
- **Recovery Fraction** reflects real-world empirical recovery rates upon successful action (1.00 for retries, 0.90 for manual review, 0.82 for dunning).
- **Action Cost** accounts for gateway and processing overhead (e.g. ₹8 for same rail, ₹10 for alternate rail, ₹4 for dunning, ₹6 for review).
- **Risk Penalty** discourages aggressive actions on sensitive cases (e.g. +₹50 penalty for retrying compliance or lost-card blocks).

---

## Live Mode & Demo Streaming Pipeline

To provide reviewers and operators with an interactive, end-to-end demonstration without requiring external webhook generation, RECOVR features a dedicated Live Mode engine (`POST /demo/live-mode/*` and `/live` in the UI).
- **Canonical 10-Scenario Sequence**: Cycles through realistic payment failure scenarios (Nighttime bank timeout, High-value clean customer, Stolen card, Unmapped bank error, Repeat offender, Low-value nuisance, Spend cap in action, Genuinely novel bank code, Account closed, Compliance block).
- **Unified Pipeline**: Live mode uses the exact same `_simulate_transaction` helper, economic scoring, and safety executor as production webhooks.
- **Session-Scoped Metrics**: Metrics can be scoped to the active live-mode session (`scope=session`) or all historical records (`scope=all`), preventing demo playback from polluting historical evaluation benchmarks.
- **Honest Metric Accounting**: Transactions currently in `hold_for_review` are excluded from the recovery rate denominator, properly categorizing them as pending review rather than failed recoveries.

See [`docs/decisions/0007-live-mode-simulation.md`](../decisions/0007-live-mode-simulation.md) for the full architectural decision record.

---

## Data Flow for the Audit Trail

Every triage decision — regardless of which path produced it — writes an immutable `AuditEntry` and `RecoveryDecisionRow` containing the full option ranking and verbatim reasoning trace. The frontend dashboard reads this table directly; there is no secondary logging system to drift out of sync.

---

## Safe Public Inspection (`GET /config/public`)

To allow judges and operators to inspect runtime configuration honestly without compromising environment security, the service exposes `GET /config/public`. This endpoint serves operational thresholds (active LLM provider, spend ceiling, confidence gate, per-customer attempt limits, credential mode, and cost baseline) while strictly excluding every secret, webhook key, and database credential.

---

## What is Deliberately Out of Scope

- **No multi-gateway routing infrastructure.** Rail-switching here means choosing among payment methods Razorpay itself exposes in test mode (e.g., retry via UPI instead of card), not building a multi-PSP orchestration layer.
- **No custom-trained ML model.** The reasoning path uses an LLM provider directly (Groq with `openai/gpt-oss-120b` or Anthropic Claude) with structured context, not a fine-tuned black-box classifier.
- **No multi-tenant merchant accounts.** One demo merchant workspace with operator profile switching is sufficient to prove the mechanism.
