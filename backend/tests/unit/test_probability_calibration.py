"""Unit tests for calibrated action-probability estimator.

Tests:
- Calibration behavior and bounds [0.0, 0.95]
- Bayesian Beta-smoothing on sparse buckets
- Unseen/novel decline reasons
- Extreme input values (0.0, 1.0, high retry counts, large amounts)
- Preservation of deterministic cases (structural zeros)
- Action-specific semantics (each action has distinct recovery mechanisms)
- Anti-leakage guarantees (no hidden outcome fields or realized labels consumed)
"""

import inspect
from app.agent.economics.probability_heuristics import (
    STRUCTURAL_ZERO_ACTIONS,
    estimate_probabilities,
)
from app.schemas.triage import TriageAction


def test_calibration_bounds_and_validity():
    """All action probabilities must lie within [0.0, 0.95], and no_action must be 0.0."""
    decline_reasons = [
        "insufficient_funds",
        "bank_timeout",
        "authentication_failed",
        "issuer_unavailable",
        "card_expired",
        "card_reported_lost_or_stolen",
        "account_closed",
        "invalid_card_number",
        "compliance_block",
        "some_unmapped_bank_specific_code_47B",
    ]
    for dec in decline_reasons:
        probs = estimate_probabilities(
            decline_reason=dec,
            customer_prior_success_rate=0.5,
            customer_account_age_days=100,
            customer_most_recent_decline=None,
        )
        assert probs["no_action"] == 0.0
        for action, p in probs.items():
            assert 0.0 <= p <= 0.95, f"Action {action} on {dec} out of bounds: {p}"


def test_smoothing_on_sparse_buckets():
    """Sparse / low-sample decline reasons must be smoothed toward priors rather than 0 or 1."""
    # some_unmapped_bank_specific_code_47B had N=2 in training
    probs = estimate_probabilities(
        decline_reason="some_unmapped_bank_specific_code_47B",
        customer_prior_success_rate=None,
        customer_account_age_days=None,
        customer_most_recent_decline=None,
    )
    # retry_same_rail was 0/2 raw in training, but smoothed with prior should be around ~0.08
    assert 0.05 <= probs["retry_same_rail"] <= 0.15
    # retry_alt_rail was 1/2 raw (50%), smoothed should be ~0.15
    assert 0.10 <= probs["retry_alt_rail"] <= 0.25
    # hold_for_review was 1/2 raw (50%), smoothed should be ~0.34
    assert 0.25 <= probs["hold_for_review"] <= 0.40


def test_unseen_decline_reason_fallback():
    """Completely unknown decline reasons fall back gracefully to calibrated defaults."""
    probs = estimate_probabilities(
        decline_reason="novel_unseen_bank_error_99X",
        customer_prior_success_rate=None,
        customer_account_age_days=None,
        customer_most_recent_decline=None,
    )
    assert probs["retry_same_rail"] == 0.12
    assert probs["retry_alt_rail"] == 0.15
    assert probs["hold_for_review"] == 0.20
    assert probs["escalate_to_dunning"] == 0.06
    assert probs["no_action"] == 0.0


def test_extreme_probabilities_and_inputs():
    """Extreme inputs (e.g. 0.0 or 1.0 success rate, large amount, large retries) stay bounded."""
    # Maximum boosts possible
    max_probs = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=1.0,
        customer_account_age_days=1000,
        customer_most_recent_decline=None,
        amount_inr=1_000_000.0,
        last_successful_rail="upi",
        recent_retry_count=0,
        failure_hour=3,  # off-hours
    )
    for a, p in max_probs.items():
        assert 0.0 <= p <= 0.95

    # Maximum dampening possible
    min_probs = estimate_probabilities(
        decline_reason="insufficient_funds",
        customer_prior_success_rate=0.0,
        customer_account_age_days=0,
        customer_most_recent_decline="insufficient_funds",
        amount_inr=10.0,
        last_successful_rail=None,
        recent_retry_count=10,
        failure_hour=14,
    )
    for a, p in min_probs.items():
        assert 0.0 <= p <= 0.95


def test_deterministic_cases_preserved():
    """Structural zeros for deterministic / impossible actions must remain strictly 0.0,
    even when positive contextual boosts are present."""
    # card_expired: retry_same_rail is impossible
    probs_expired = estimate_probabilities(
        decline_reason="card_expired",
        customer_prior_success_rate=1.0,  # strong history
        customer_account_age_days=500,
        customer_most_recent_decline=None,
        failure_hour=2,  # off-hours
    )
    assert probs_expired["retry_same_rail"] == 0.0
    assert probs_expired["escalate_to_dunning"] > 0.30

    # compliance_block: retries and dunning are strictly forbidden
    probs_compliance = estimate_probabilities(
        decline_reason="compliance_block",
        customer_prior_success_rate=1.0,
        customer_account_age_days=500,
        customer_most_recent_decline=None,
        last_successful_rail="upi",
    )
    assert probs_compliance["retry_same_rail"] == 0.0
    assert probs_compliance["retry_alt_rail"] == 0.0
    assert probs_compliance["escalate_to_dunning"] == 0.0
    assert probs_compliance["hold_for_review"] > 0.20

    # account_closed: retries impossible
    probs_closed = estimate_probabilities(
        decline_reason="account_closed",
        customer_prior_success_rate=1.0,
        customer_account_age_days=500,
        customer_most_recent_decline=None,
        last_successful_rail="upi",
    )
    assert probs_closed["retry_same_rail"] == 0.0
    assert probs_closed["retry_alt_rail"] == 0.0

    # card_reported_lost_or_stolen: same rail retry impossible
    probs_stolen = estimate_probabilities(
        decline_reason="card_reported_lost_or_stolen",
        customer_prior_success_rate=1.0,
        customer_account_age_days=500,
        customer_most_recent_decline=None,
    )
    assert probs_stolen["retry_same_rail"] == 0.0
    assert probs_stolen["escalate_to_dunning"] > 0.30


def test_action_specific_semantics():
    """Each action models a distinct recovery mechanism and should have distinct probabilities."""
    # 1. On card_expired, dunning is the primary recovery path
    p_exp = estimate_probabilities(
        decline_reason="card_expired",
        customer_prior_success_rate=0.6,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
    )
    assert p_exp["escalate_to_dunning"] > p_exp["hold_for_review"]
    assert p_exp["escalate_to_dunning"] > p_exp["retry_alt_rail"]
    assert p_exp["retry_same_rail"] == 0.0

    # 2. On bank_timeout, retrying rails is the primary path, not dunning
    p_timeout = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.6,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
    )
    assert p_timeout["retry_same_rail"] > p_timeout["escalate_to_dunning"]
    assert p_timeout["retry_alt_rail"] > p_timeout["escalate_to_dunning"]

    # 3. On authentication_failed, alt-rail and review are significantly higher than same-rail
    p_auth = estimate_probabilities(
        decline_reason="authentication_failed",
        customer_prior_success_rate=0.6,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
    )
    assert p_auth["retry_alt_rail"] > p_auth["retry_same_rail"]
    assert p_auth["hold_for_review"] > p_auth["retry_same_rail"]


def test_contextual_shifts_directionality():
    """Observable contextual adjustments must shift probabilities in the intended directions."""
    base = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
    )

    # Strong customer history boosts retry
    strong = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.9,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
    )
    assert strong["retry_same_rail"] > base["retry_same_rail"]
    assert strong["retry_alt_rail"] > base["retry_alt_rail"]

    # Repeated same decline dampens same-rail and boosts alt-rail & dunning
    repeated = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline="bank_timeout",
    )
    assert repeated["retry_same_rail"] < base["retry_same_rail"]
    assert repeated["retry_alt_rail"] > base["retry_alt_rail"]
    assert repeated["escalate_to_dunning"] > base["escalate_to_dunning"]

    # Recent retry count >= 2 dampens same rail
    high_retries = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
        recent_retry_count=3,
    )
    assert high_retries["retry_same_rail"] < base["retry_same_rail"]

    # UPI evidence boosts alt rail
    upi_evidence = estimate_probabilities(
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
        last_successful_rail="upi",
    )
    assert upi_evidence["retry_alt_rail"] > base["retry_alt_rail"]


def test_no_hidden_outcome_leakage():
    """Ensure no hidden outcomes or realized truth fields are accepted or consumed by estimate_probabilities."""
    sig = inspect.signature(estimate_probabilities)
    param_names = set(sig.parameters.keys())
    forbidden_terms = {
        "action_outcomes",
        "recovered",
        "success_probability",
        "recovered_amount_inr",
        "net_recovered_inr",
        "ground_truth_label",
        "best_actions",
    }
    for term in forbidden_terms:
        assert term not in param_names, f"Forbidden leakage parameter found in signature: {term}"

    # Also inspect source of estimate_probabilities to ensure it does not access forbidden fields
    source = inspect.getsource(estimate_probabilities)
    assert "action_outcomes" not in source
    assert "recovered_amount_inr" not in source
    assert "net_recovered_inr" not in source
    assert "ground_truth_label" not in source
