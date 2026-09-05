from app.agent.reasoning import ReasoningResult
from app.schemas.triage import TriageAction
from pydantic import ValidationError
from scripts.run_evaluation import _load_holdout
from scripts.run_llm_ablation import evaluate


def test_valid_llm_recommendation_cannot_bypass_economics():
    result = evaluate(_load_holdout()[:2], lambda _: ReasoningResult(action=TriageAction.NO_ACTION, reasoning_text="x", confidence=.99))
    assert result["decision_effect"]["llm_changed_decision_count"] == 0
    assert result["economics_only"]["net_recovery_inr"] == result["llm_informed_recovr"]["net_recovery_inr"]


def test_provider_failure_falls_back_without_changing_action():
    result = evaluate(_load_holdout()[:2], lambda _: (_ for _ in ()).throw(TimeoutError("timeout")))
    assert result["reliability"]["failure_count"] == 2
    assert result["reliability"]["fallback_count"] == 2
    assert result["decision_effect"]["net_value_added_by_llm_inr"] == 0


def test_invalid_or_missing_structured_output_is_rejected_before_ablation():
    with __import__("pytest").raises(ValidationError):
        ReasoningResult(action="not_an_action", reasoning_text="x", confidence=.9)
    with __import__("pytest").raises(ValidationError):
        ReasoningResult(action=TriageAction.NO_ACTION, reasoning_text="x")


def test_contradictory_free_text_cannot_change_final_action():
    result = evaluate(_load_holdout()[:1], lambda _: ReasoningResult(
        action=TriageAction.NO_ACTION, reasoning_text="Retry immediately on another rail.", confidence=.99))
    observation = result["records"][0]
    assert observation["final_action"] == observation["economic_action"]
    assert observation["llm_changed_decision"] is False
