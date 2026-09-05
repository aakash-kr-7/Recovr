"""Action-specific probability semantics and structured-context tests."""

from app.agent.economics.probability_heuristics import estimate_probabilities
from app.agent.economics.scoring import score_recovery_options
from app.schemas.recovery import RecoveryContext
from app.schemas.triage import TriageAction


def _estimate(**overrides):
    values = {"decline_reason": "bank_timeout", "customer_prior_success_rate": 0.6,
              "customer_account_age_days": 120, "customer_most_recent_decline": None,
              "amount_inr": 2000.0, "last_successful_rail": None,
              "recent_retry_count": 0, "failure_hour": 12}
    values.update(overrides)
    return estimate_probabilities(**values)


def test_probabilities_are_action_specific_and_review_can_recover():
    probabilities = _estimate(decline_reason="authentication_failed")
    assert probabilities["hold_for_review"] > 0.0
    assert probabilities["hold_for_review"] != probabilities["retry_same_rail"]
    assert probabilities["no_action"] == 0.0


def test_last_successful_rail_boosts_alternate_rail_only():
    baseline, upi = _estimate(), _estimate(last_successful_rail="upi")
    assert upi["retry_alt_rail"] > baseline["retry_alt_rail"]
    assert upi["retry_same_rail"] == baseline["retry_same_rail"]


def test_repeated_retries_reduce_same_rail_probability():
    assert _estimate(recent_retry_count=2)["retry_same_rail"] < _estimate()["retry_same_rail"]


def test_off_hours_adjust_timeout_and_review_probabilities():
    daytime, off_hours = _estimate(failure_hour=12), _estimate(failure_hour=23)
    assert off_hours["retry_same_rail"] > daytime["retry_same_rail"]
    assert off_hours["hold_for_review"] < daytime["hold_for_review"]


def test_scorer_consumes_typed_context():
    decision = score_recovery_options(
        transaction_id="context-test", permitted_actions=list(TriageAction),
        context=RecoveryContext(amount_inr=2000.0, decline_reason="bank_timeout",
                                customer_prior_success_rate=0.6, customer_account_age_days=120,
                                last_successful_rail="upi", recent_retry_count=2, failure_hour=23),
    )
    options = {option.action.value: option for option in decision.options}
    assert options["hold_for_review"].estimated_probability > 0.0
    assert options["retry_alt_rail"].estimated_probability > 0.0
