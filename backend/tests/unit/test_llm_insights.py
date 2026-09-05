from app.agent.economics.scoring import score_recovery_options
from app.schemas.recovery import LLMInsights, RecoveryContext
from app.schemas.triage import TriageAction


def _score(context):
    return score_recovery_options("insight-case", context=context, permitted_actions=list(TriageAction))


def test_alternate_rail_insight_can_change_a_nearby_economic_ranking():
    context = RecoveryContext(amount_inr=1000, decline_reason="bank_timeout", customer_prior_success_rate=.7,
        customer_account_age_days=100, recent_retry_count=0, failure_hour=2)
    base = _score(context)
    insight = LLMInsights(transient_failure_probability=.1, alternate_rail_evidence=.99, review_worthiness=.1,
        interpretation_confidence=1, evidence_basis=["raw_decline_text"])
    informed = _score(context.model_copy(update={"llm_insights": insight}))
    assert base.selected_action == TriageAction.RETRY_SAME_RAIL
    assert informed.selected_action == TriageAction.RETRY_ALT_RAIL


def test_weak_insight_is_neutral_and_structural_zeros_survive():
    context = RecoveryContext(amount_inr=1000, decline_reason="card_expired", recent_retry_count=0)
    insight = LLMInsights(transient_failure_probability=1, alternate_rail_evidence=1, review_worthiness=1,
        interpretation_confidence=.2, evidence_basis=["raw_decline_text"])
    options = {o.action: o.estimated_probability for o in _score(context.model_copy(update={"llm_insights": insight})).options}
    assert options[TriageAction.RETRY_SAME_RAIL] == 0.0


def test_repeated_failure_review_and_off_hours_cases_remain_bounded():
    cases = [
        # Repeated retries / worsening failure: lower transient evidence.
        RecoveryContext(amount_inr=1200, decline_reason="bank_timeout", customer_most_recent_decline="bank_timeout", recent_retry_count=3),
        # Large ambiguous issue: review evidence may help, but is bounded.
        RecoveryContext(amount_inr=9000, decline_reason="some_unmapped_bank_specific_code_47B", recent_retry_count=0),
        # Off-hours issuer failure: timing interpretation is contextual only.
        RecoveryContext(amount_inr=1000, decline_reason="issuer_unavailable", failure_hour=2),
    ]
    insight = LLMInsights(transient_failure_probability=.8, alternate_rail_evidence=.3, review_worthiness=.9,
        interpretation_confidence=.8, evidence_basis=["raw_decline_text", "customer_history", "failure_time"])
    for context in cases:
        options = _score(context.model_copy(update={"llm_insights": insight})).options
        assert all(0.0 <= option.estimated_probability <= .95 for option in options)
