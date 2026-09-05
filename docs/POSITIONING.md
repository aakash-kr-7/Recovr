# Positioning: what's actually new here, and what isn't

This document exists because it should. A submission that claims novelty it
doesn't have is a worse signal than one that's honest about building on an
existing category well. This is the second kind.

## The category is not new

Recovering money from a failed payment is a well-established product
category. At minimum, these exist and work today:

- **Razorpay's own smart routing** — automatically redirects a failed
  payment to an alternate gateway.
- **Slicker** — decline-reason-aware retry timing, rail-specific rules,
  built with India's e-mandate framework in mind.
- **GR4VY** — a no-code payment orchestration rules engine that encodes
  exactly this kind of decision tree (insufficient funds → alternate
  acquirer, timeout → immediate retry, hard decline → dunning).
- **Stripe Smart Retries** — retry timing optimization for subscriptions,
  publishing an aggregate recovery percentage.

If you are a judge who knows this space, you already know these products.
We're not going to pretend otherwise, and if asked "isn't this just X,"
the honest answer is: the category is the same, the mechanism and the
evidence are different. Read on for exactly what that means.

## The design choice in this project

RECOVR does not claim to know the internals of competing payment products.
Its own design deliberately combines deterministic handling for known,
unambiguous failures with an optional bounded reasoning path for ambiguous
or unfamiliar cases. That path receives structured customer history, timing,
and raw decline context; economics and safety—not the LLM—remain
authoritative.

## What we do differently — three concrete, checkable claims

1. **Contextual inputs for ambiguous cases.** The optional reasoning path
   (see [`architecture/overview.md`](architecture/overview.md)) receives the
   decline code, customer history, and transaction timing. You can verify the
   structured context boundary directly:
   `backend/tests/fixtures/context_divergence_cases.json` contains pairs of
   transactions with the *same* decline code but different context. The
   output is constrained by the typed reasoning contract, economic ranking,
   and safety gate.

   **Current limitation:** the live Razorpay customer-history lookup is still
   a stub, so production webhook runs currently supply an empty history. This
   is not evidence of live historical enrichment.

2. **Unfamiliar cases fail safely.** A decline reason without a fast-path
   rule is routed to the optional reasoning path rather than a silent action
   default. If the provider output is unavailable or malformed, the system
   records the reasoning failure and holds for review. This behavior is
   covered by `backend/tests/integration/test_unseen_decline_reason.py` and
   `backend/tests/integration/test_demo_lifecycle.py`.

3. **An auditable, held-out synthetic evaluation.** The primary report is a
   fair action-level comparison of Retry All, Fixed Rule, and RECOVR under
   equal constraints, including net recovery and expected/realized regret.
   Legacy binary diagnostics remain secondary. All resulting INR figures are
   synthetic evaluation values, not merchant revenue. See
   [`architecture/evaluation.md`](architecture/evaluation.md) and run
   `backend/scripts/run_evaluation.py` yourself.

   *Addendum — empirical calibration verified on held-out data:* We found and
   fixed a real miscalibration in the probability heuristics. Using training data
   only ($N=140$), probabilities were calibrated via empirical Bayes / Beta
   shrinkage ($W=10$) with documented deterministic structural zeros and additive
   context shifts, validated by 5-fold cross-validation. On the untouched
   held-out test set ($N=60$), this reduced macro-average probability MAE from
   7.57 pp to 5.35 pp (-29.3% error reduction; `retry_same_rail` improved from
   8.01 pp to 5.23 pp [-34.7%], `retry_alt_rail` from 10.74 pp to 5.96 pp
   [-44.5%], and `escalate_to_dunning` from 7.86 pp to 4.52 pp [-42.5%], while
   `hold_for_review` regressed from 3.66 pp to 5.70 pp [+55.7%]). Primary
   probability-induced decision failures dropped from 15 to 10 (-33.3%). Full
   account in [`architecture/failure_log.md`](architecture/failure_log.md).

4. **Economic action selection instead of single-best-guess classification.**
   The system doesn't just pick "the right action," it computes an expected
   net recovery value across every permitted action and selects on that basis,
   with the full comparison visible in the audit trail. See
   `backend/tests/unit/test_economics_scoring.py` (specifically
   `test_higher_probability_action_loses_due_to_cost_risk`) which proves a
   high-probability retry will be rejected in favor of holding if the cost
   outweighs the expected recovery.

## What we are not claiming

- We are not claiming to have invented failure-triage-and-recovery as a
  concept.
- We are not claiming our reasoning path is more *accurate* than a
  well-tuned enterprise rules engine at scale — Slicker and GR4VY have
  production data and years of tuning we don't have in a week.
- We are not claiming rail-switching itself is novel — Razorpay's own
  smart routing and GR4VY both already do this.
- We are not claiming competitors lack any retry optimization or
  expected-value logic internally — they likely have sophisticated models.
  We are only claiming this project's specific transparency (visible
  per-option comparison, auditable heuristic, honest calibration reporting)
  as its differentiator, not the uniqueness of the underlying idea.

## What we are claiming

That RECOVR provides a checkable combination of contextual reasoning inputs,
per-action economic ranking, safety constraints, and transparent synthetic
evaluation. This is an implementation and evidence claim, not a claim of
superior production recovery versus established payment products.

If you disagree with this framing, we'd rather you disagree with an
honest claim than agree with an inflated one.
