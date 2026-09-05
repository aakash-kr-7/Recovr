# Architecture overview

## The core idea

Not every failed payment needs an AI model to reason about it. A card that
was reported stolen has one correct action (do not retry, escalate) and no
amount of context changes that. A payment that timed out mid-authorization
might mean five different things depending on who the customer is and what
happened before. The system routes each failed transaction down one of two
paths based on how much the decline reason alone tells you.

```
                    Razorpay webhook: payment.failed
                                │
                                ▼
                  ┌─────────────────────────┐
                  │  Confidence gate          │
                  │  (app/agent/gate.py)      │
                  └────────────┬─────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   ┌───────────────────────┐       ┌─────────────────────────────┐
   │ Deterministic fast path │       │ Reasoning path (Groq/Claude)│
   │ app/agent/rules/         │       │ app/agent/reasoning.py       │
   │                          │       │                             │
   │ Fixed table: decline     │       │ Given: decline reason, last  │
   │ code → action, no model  │       │ N transactions for this      │
   │ call. Used only when the │       │ customer, time-of-day/date   │
   │ code is unambiguous       │       │ pattern, any prior triage    │
   │ (e.g. card_reported_lost,│       │ decisions on this customer.  │
   │ account_closed).          │       │ Reasons in natural language, │
   │                          │       │ outputs one of the allowed   │
   │                          │       │ actions plus its reasoning.  │
   └────────────┬───────────┘       └───────────────┬──────────────┘
                └────────────────┬───────────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │ Economic scoring engine         │
                  │ app/agent/economics/scoring.py  │
                  │                                  │
                  │ Ranks permitted actions by       │
                  │ expected net recovery. If the    │
                  │ economically optimal action      │
                  │ differs from the path's          │
                  │ candidate, economic choice wins. │
                  └────────────────┬─────────────────┘
                                   ▼
                  ┌──────────────────────────────┐
                  │ Bounded action executor         │
                  │ app/agent/executor.py           │
                  │                                  │
                  │ - Action MUST be in the allowed  │
                  │   list (retry_same_rail,          │
                  │   retry_alt_rail, hold_for_review,│
                  │   escalate_to_dunning, no_action) │
                  │ - Spend cannot exceed the batch    │
                  │   spend cap (config.py)            │
                  │ - Low-confidence reasoning-path     │
                  │   outputs are routed to             │
                  │   hold_for_review instead of        │
                  │   auto-executing                    │
                  └────────────────┬─────────────────┘
                                   ▼
                  ┌──────────────────────────────┐
                  │ Execute on Razorpay test-mode   │
                  │ API (app/services/razorpay.py)  │
                  └────────────────┬─────────────────┘
                                   ▼
                  ┌──────────────────────────────┐
                  │ Audit log                       │
                  │ (app/db/models.py: AuditEntry)  │
                  │                                  │
                  │ transaction_id, decline_reason,   │
                  │ path_taken, action, reasoning_text│
                  │ (verbatim if reasoning path),      │
                  │ confidence, outcome, timestamp    │
                  └──────────────────────────────────┘
```

## Why two paths, not one

Calling an LLM for every decision is slower, costs money per call, and —
more importantly — is worse engineering when a deterministic answer
exists. The buildathon's own judging criteria explicitly reward "the right
tool in the right place, and where you chose not to use one." The fast
path is not a shortcut; it is the answer to that criterion. See
[`docs/decisions/0003-two-path-agent.md`](../decisions/0003-two-path-agent.md)
for the full reasoning and the specific decline codes routed to each path.

## Why the executor is a separate component from the reasoning

The reasoning path can be wrong. The executor cannot trust it blindly. By
keeping "decide" and "act" as separate components with a hard allow-list
and spend cap in between, a bad reasoning output degrades to
"held for human review," never to "money moved incorrectly." This is the
direct implementation of the buildathon's stated bar: every money action
explainable, bounded, and gated.

## Data flow for the audit trail

Every triage decision — regardless of which path produced it — writes one
`AuditEntry` row containing the full reasoning trace. The frontend
dashboard reads this table directly; there is no separate "logging system"
to keep in sync. See [`backend/app/db/`](../../backend/app/db/).

## Safe public inspection (`GET /config/public`)

To allow judges and operators to inspect runtime configuration honestly without compromising environment security, the service exposes `GET /config/public`. This endpoint serves operational thresholds (active LLM provider, spend ceiling, confidence gate, per-customer attempt limits, credential mode, and cost baseline) while strictly excluding every secret, webhook key, and database credential.

## What is out of scope, deliberately

- **No multi-gateway routing infrastructure.** Rail-switching here means
  choosing among payment methods Razorpay itself exposes in test mode
  (e.g., retry via UPI instead of card), not building a multi-PSP
  orchestration layer. That space is already occupied (GR4VY, Razorpay's
  own routing) and is out of scope for a one-week solo build.
- **No custom-trained ML model.** The reasoning path uses an LLM provider
  directly (Groq with `openai/gpt-oss-120b` by default, or Anthropic Claude)
  with structured context, not a fine-tuned classifier. See
  [`docs/decisions/0002-no-custom-model.md`](../decisions/0002-no-custom-model.md).
- **No multi-tenant merchant accounts.** One demo merchant, hardcoded, is
  sufficient to prove the mechanism.

