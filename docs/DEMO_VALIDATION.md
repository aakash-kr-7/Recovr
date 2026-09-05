# RECOVR end-to-end demo validation

This is technical validation evidence, not a merchant-revenue claim. All
amounts below are INR; a Payment Link is never called recovered until a
confirmed outcome is recorded.

## Golden live scenario: deterministic dunning attempt

On 2026-09-04, the running local backend received this signed test-mode
`payment.failed` input (sensitive credentials are intentionally omitted):

```json
{
  "event": "payment.failed",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_recovr_demo_1788549762",
        "amount": 10000,
        "currency": "INR",
        "status": "failed",
        "error_code": "card_reported_lost_or_stolen",
        "error_description": "Demo: card reported lost or stolen",
        "contact": "recovr-demo@example.test"
      }
    }
  }
}
```

The webhook signature was accepted and persisted transaction
`4f82652a-749b-4e10-a821-482077400b3b` as a non-synthetic `production`
record. The deterministic gate selected `escalate_to_dunning`; the economic
ranking independently selected the same action:

| Action | Expected net |
| --- | ---: |
| escalate_to_dunning (selected) | ₹26.75 |
| hold_for_review | ₹3.45 |
| no_action | ₹0.00 |
| retry_alt_rail | -₹55.00 |
| retry_same_rail | -₹58.00 |

The executor made the supported test-mode Razorpay Payment Link request. The
configured test credential was rejected by Razorpay with `Authentication
failed`. RECOVR therefore recorded, rather than hiding, the terminal attempt:

| Field | Recorded value |
| --- | --- |
| selected action / execution action | `escalate_to_dunning` / `escalate_to_dunning` |
| execution mode | `REAL_RAZORPAY_ACTION` |
| execution status | `FAILED` |
| provider | `razorpay` |
| provider reference | `null` (no link was created) |
| actual recovered | `null` |
| error code | `razorpay_request_failed` |
| audit outcome | `execution_failed` |

This transaction visibly renders in the RECOVR decision view as
`REAL · RAZORPAY` plus `EXECUTION FAILED`; it does not show recovered revenue.
The UI contract defect discovered in this run (uppercase backend enum states
versus lowercase UI checks) was corrected during validation.

## Mocked callback lifecycle

`tests/integration/test_demo_lifecycle.py` is the deterministic, provider-free
counterpart for callback validation. It uses an isolated in-memory database
and explicitly marks the row `BOUNDED_SIMULATION` / `mock_razorpay`; it must
not be presented as a Razorpay result.

It verifies this lifecycle:

```text
pending mock Payment Link → callback handler → SUCCEEDED / ₹100
→ audit outcome recovered → duplicate callback returns duplicate
→ non-holdout historical evidence is queryable
```

It additionally inserts a matching holdout outcome and proves it is excluded
at the SQL query boundary. Expected evidence is one non-holdout,
production-partition **mocked** outcome with `escalate_to_dunning: 1.0`, not
two records; it is not a real provider recovery.

## Path and failure coverage

| Case | Evidence |
| --- | --- |
| Deterministic fast path | Golden live case; `test_deterministic_fast_path_bypasses_reasoning_path` |
| Ambiguous reasoning path | Gate/scoring and unseen-decline integration coverage |
| Economics overrides candidate | `test_divergence_recorded_and_economic_wins` |
| Safety hold | `test_low_confidence_reasoning_decision_is_gated_to_hold_for_review` |
| Simulated retry | `test_simulated_action_does_not_consume_or_gate_provider_spend_cap` |
| Pending / paid / expired lifecycle | `test_payment_link_lifecycle.py` |
| Duplicate webhook / callback | live duplicate failure request; payment-link duplicate test |
| Malformed LLM output | `test_malformed_llm_output_is_held_and_audited` proves a fail-closed hold and audit |
| Razorpay provider failure | live controlled test-mode request recorded `razorpay_request_failed` |
| Unknown provider reference | live signed unknown-link callback returned `ignored` |

## Frontend/API read-model contract

The golden record was verified through:

```text
GET /transactions/recent → RecentTransaction → Overview / Recoveries / Transactions / Audit Trail
GET /transactions/audit/{transaction_id} → AuditDetail → Decision detail
GET /evaluation/latest → EvaluationReport → Evaluation (Reliability calibration curve)
GET /config/public → PublicConfig → Settings (safe operational parameters)
GET /demo/presets → DemoPresets → Simulator panel drawer
POST /demo/simulate → SimulationResult → Real-time triage lifecycle
```

The local UI rendered Overview, Recoveries, Transactions, Decision detail,
Audit Trail, Evaluation, and Settings against the live API. `null` provider references
and actual recovery values render as `Unavailable`, never as zero or a fake
recovery.


## Real-provider blocker

Test-mode credentials are configured, but Razorpay rejected the controlled
Payment Link request. Consequently there is no real Payment Link ID, no
provider callback, and no real recovered/expired outcome for this run. A valid
test credential plus a publicly reachable webhook URL is required before a
real `payment_link.paid` or `payment_link.expired` lifecycle can be captured.
