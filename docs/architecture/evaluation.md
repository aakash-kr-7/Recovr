# Evaluation methodology

## Why this document exists

Every competitor we could find publishes a single aggregate recovery
percentage. None publish a breakdown of how often their system is wrong,
or what being wrong costs. We think that breakdown is the more honest and
more useful number, and it's cheap enough for a solo builder to produce
properly — so we do it, and we explain exactly how, so the number can be
trusted rather than taken on faith.

## The dataset

`backend/scripts/generate_synthetic_data.py` builds a labeled set of
synthetic failed transactions. Each record has:

- A decline reason (drawn from a realistic distribution of UPI/card
  failure types — see `backend/app/agent/rules/decline_taxonomy.py` for the
  full list and where it's sourced from)
- A synthetic customer history (0–12 prior transactions, with a
  configurable pattern: clean history, first-time customer, prior
  insufficient-funds pattern, etc.)
- A **ground-truth label**: the action a careful human would take on this
  case, assigned *before* the system ever sees the record.

This label is what makes precision/recall meaningful. Without a
ground-truth assigned independently of the system's own output, a
"confusion matrix" is just theater. Ours is not: the labeling logic in
`generate_synthetic_data.py` is a separate, simpler function from anything
the agent itself uses, specifically so it can't leak the agent's own
assumptions back into its own grading.

## The split

70% of the generated set is used during development (prompt iteration,
rule-table tuning). The remaining 30% is written to
`backend/data/eval/holdout.json` at generation time and is never read by
any code path except `run_evaluation.py`. This file's checksum is logged
on first generation specifically so it's obvious if it was ever
regenerated or peeked at during development — see the checksum note this
script prints on first run.

## The metrics, defined in plain terms

For the binary decision "is this decline worth retrying":

- **True positive** — system said retry, and the ground truth says it
  would have succeeded. Money recovered.
- **False positive** — system said retry, but the ground truth says it
  never would have succeeded. This has a real cost: wasted gateway fees,
  a possible card-network penalty for excessive retries, and an annoyed
  customer. We report this cost, not just the count.
- **False negative** — system said don't retry (or escalate), but the
  ground truth says a retry would have succeeded. Real revenue left
  unrecovered.
- **True negative** — system correctly identified a non-recoverable
  decline and didn't waste a retry on it.

`backend/scripts/run_evaluation.py` computes precision, recall, and an
estimated ₹ cost of false positives (using a configurable
per-wasted-retry cost constant — see `backend/app/core/config.py`,
`WASTED_RETRY_COST_INR`) and writes the full report, including which
specific transaction IDs fell into each bucket, to
`backend/data/eval/latest_report.json`.

## The naive baseline

The report also computes a "retry everything" baseline and a "retry
nothing" baseline for comparison, so the actual lift from the triage logic
is visible rather than asserted. The commonly cited industry figure for
naive retry recovery (roughly 15-20% of failed payments, per public
figures from Razorpay's and Stripe's own blogs — see citations in
`docs/decisions/0004-baseline-sourcing.md`) is included as a third
reference point.

## Running it

```bash
cd backend
python scripts/generate_synthetic_data.py   # first time only, or to regenerate
python scripts/run_evaluation.py
```

Output is printed to the console and written to
`backend/data/eval/latest_report.json`. The dashboard's Results page reads
this JSON file directly — see
[`frontend/src/pages/ResultsPage.tsx`](../../frontend/src/pages/ResultsPage.tsx).

## Addendum: Historical Evidence Isolation & Anti-Leakage Guarantee

With the introduction of the economic decision layer and historical evidence lookup (`backend/app/agent/economics/historical_evidence.py`), the system can consult past recovery outcomes to calibrate action probabilities. To preserve the scientific validity of the evaluation, **the historical lookup must never observe outcomes from the evaluation holdout partition**.

### The Mechanism
1. **Schema-Level Partitioning (`Transaction.data_split`)**:
   Every transaction row carries an indexed `data_split` string column:
   - `'working'`: 70% synthetic development dataset used for heuristic calibration and historical evidence queries.
   - `'holdout'`: 30% synthetic evaluation set generated once, checksummed, and reserved exclusively for evaluation.
   - `'production'`: Real webhook traffic from payment gateways.

2. **Query-Level Enforcement**:
   Holdout isolation is not an application convention or post-filter; it is enforced directly in the SQL `WHERE` clause:
   ```python
   stmt = (
       select(RecoveryOutcomeRow, Transaction.customer_history)
       .join(Transaction, RecoveryOutcomeRow.transaction_id == Transaction.id)
       .where(
           Transaction.data_split != "holdout",
           Transaction.decline_reason == decline_reason,
           RecoveryOutcomeRow.observed_success.is_not(None),
       )
   )
   ```
   Because `Transaction.data_split != "holdout"` is evaluated by the SQLite query engine before records are returned, rows associated with the holdout dataset are never loaded into memory by the decision pipeline.

### Verification Protocol: Proving Zero Leakage
Anyone auditing or verifying this repository can confirm zero holdout leakage through three complementary checks:

1. **Automated Leakage Test**:
   Execute the dedicated regression test:
   ```bash
   cd backend
   pytest tests/unit/test_historical_evidence.py -k "test_holdout_outcomes_never_queried" -v
   ```
   This test constructs a fixture with matching decline reasons and identical customer histories tagged as `data_split="holdout"`, calls `query_historical_evidence()`, and asserts that the query returns 0 matching cases and `low_confidence=True`.

2. **Source Code Audit**:
   Inspect `backend/app/agent/economics/historical_evidence.py`. Confirm that the database query explicitly includes `Transaction.data_split != "holdout"`.

3. **Checksum Stability**:
   The evaluation script checks the holdout partition in `backend/data/eval/holdout.json`. Its SHA-256 checksum remains unchanged across pipeline runs.

## The economic evaluation metrics, defined in plain terms

The confusion matrix above treats every transaction as an equal vote: getting a ₹50 transaction right counts the same as getting a ₹50,000 transaction right. But in a real business, **a wrong ₹50 decision and a wrong ₹50,000 decision are not equally costly**.

The `economic_evaluation` section of the evaluation report measures financial outcomes directly from the decisions and outcomes produced during the holdout run:

- **Total at risk (`total_at_risk_inr`)** — the gross ₹ value of every failed transaction in the held-out set. Matches `money.total_at_risk_inr` exactly.
- **Total expected recovery (`total_expected_recovery_inr`)** — what the economic decision layer *predicted* it would recover across all decisions (summing `expected_recovery_inr = probability × amount` for the winning option in each decision).
- **Total actual recovered (`total_actual_recovered_inr`)** — the actual ₹ amount recovered when successful actions executed against ground truth. Reconciles exactly with `money.recovered_inr`.
- **Expected vs. actual variance (`expected_vs_actual_variance_inr`)** — `actual_recovered - expected_recovery`. A positive variance means the system under-promised and over-delivered; a negative variance means it was overly optimistic. This is the calibration feedback signal.
- **Average expected value per decision (`average_expected_value_per_decision_inr`)** — the average gross recovery anticipated on each transaction.
- **Average realized value per decision (`average_realized_value_per_decision_inr`)** — the actual ₹ collected per transaction evaluated.
- **Recovery rate (`recovery_rate`)** — `actual_recovered / total_at_risk`. The net proportion of failed payment volume saved.
- **Wasted retry cost (`wasted_retry_cost_inr`)** — money lost to payment gateway fees on retries that failed. Reconciles with `money.false_positive_cost_inr`.
- **Missed recovery (`missed_recovery_inr`)** — recoverable money left on the table because the system chose not to retry. Reconciles with `money.missed_recovery_inr`.

### Amount-band breakdown

To expose how well the system performs across different transaction ticket sizes, the report groups decisions into three value tiers:
1. **Under ₹500** — micro-transactions where retry costs (₹8 gateway fee) represent a significant fraction (1.6% to 16%+) of the transaction value. Here, aggressive retries easily produce negative expected net recovery.
2. **₹500 - ₹5,000** — mid-tier payments where the balance between recovery upside and wasted retry fees is moderate.
3. **Over ₹5,000** — high-value transactions where false negatives are catastrophic (thousands of ₹ lost), justifying retries even at lower win probabilities.

For each tier, the report details transaction counts, ₹ at risk, ₹ recovered, wasted retry costs, decision counts (true/false positives/negatives), decision accuracy, and realized recovery rates.
