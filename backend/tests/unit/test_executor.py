"""Unit tests for app/agent/executor.py — the confidence gate and spend
cap that make this project's "bounded and gated" claim checkable rather
than aspirational."""

from datetime import datetime, timezone

from app.agent.executor import BatchSpendTracker, execute
from app.core.config import get_settings
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction, TriagePath


def _make_transaction(amount_inr: float = 1000.0) -> Transaction:
    return Transaction(
        id="test-txn-1",
        amount_inr=amount_inr,
        decline_reason="bank_timeout",
        decline_reason_raw="bank timeout",
        customer_id="test-customer",
        customer_history={},
        failed_at=datetime.now(timezone.utc),
        is_synthetic=True,
    )


def test_low_confidence_reasoning_decision_is_gated_to_hold_for_review():
    settings = get_settings()
    txn = _make_transaction()
    tracker = BatchSpendTracker(cap_inr=settings.batch_spend_cap_inr)

    decision = execute(
        transaction=txn,
        path=TriagePath.REASONING,
        action=TriageAction.RETRY_SAME_RAIL,
        reasoning_text="Model thinks this is worth retrying.",
        confidence=0.4,  # below default threshold of 0.75
        spend_tracker=tracker,
        options=[],
        selected_expected_net_recovery_inr=0.0,
        value_advantage_vs_next_best_inr=0.0,
    )

    assert decision.selected_action == TriageAction.HOLD_FOR_REVIEW
    assert decision.was_gated is True


def test_high_confidence_reasoning_decision_executes_as_predicted():
    settings = get_settings()
    txn = _make_transaction()
    tracker = BatchSpendTracker(cap_inr=settings.batch_spend_cap_inr)

    decision = execute(
        transaction=txn,
        path=TriagePath.REASONING,
        action=TriageAction.RETRY_SAME_RAIL,
        reasoning_text="Clean history, isolated timeout, safe to retry.",
        confidence=0.9,
        spend_tracker=tracker,
        options=[],
        selected_expected_net_recovery_inr=0.0,
        value_advantage_vs_next_best_inr=0.0,
    )

    assert decision.selected_action == TriageAction.RETRY_SAME_RAIL
    assert decision.was_gated is False


def test_deterministic_path_ignores_confidence_gate():
    """The deterministic path has no confidence score at all — it must
    never be gated on the confidence threshold, since None < threshold
    would otherwise incorrectly gate every deterministic decision."""
    txn = _make_transaction()
    tracker = BatchSpendTracker(cap_inr=10_000.0)

    decision = execute(
        transaction=txn,
        path=TriagePath.DETERMINISTIC,
        action=TriageAction.ESCALATE_TO_DUNNING,
        reasoning_text="Card reported lost, escalating per fixed rule.",
        confidence=None,
        spend_tracker=tracker,
        options=[],
        selected_expected_net_recovery_inr=0.0,
        value_advantage_vs_next_best_inr=0.0,
    )

    assert decision.selected_action == TriageAction.ESCALATE_TO_DUNNING
    assert decision.was_gated is False


def test_simulated_action_does_not_consume_or_gate_provider_spend_cap():
    txn = _make_transaction(amount_inr=6000.0)
    tracker = BatchSpendTracker(cap_inr=5000.0)  # cap smaller than this txn

    decision = execute(
        transaction=txn,
        path=TriagePath.REASONING,
        action=TriageAction.RETRY_SAME_RAIL,
        reasoning_text="Simulated retries have no provider spend.",
        confidence=0.95,
        spend_tracker=tracker,
        options=[],
        selected_expected_net_recovery_inr=0.0,
        value_advantage_vs_next_best_inr=0.0,
    )

    assert decision.selected_action == TriageAction.RETRY_SAME_RAIL
    assert tracker.spent_inr == 0.0


def test_non_money_moving_actions_never_touch_spend_cap():
    txn = _make_transaction(amount_inr=999_999.0)  # would blow any cap
    tracker = BatchSpendTracker(cap_inr=1.0)

    decision = execute(
        transaction=txn,
        path=TriagePath.DETERMINISTIC,
        action=TriageAction.NO_ACTION,
        reasoning_text="No action needed regardless of amount.",
        confidence=None,
        spend_tracker=tracker,
        options=[],
        selected_expected_net_recovery_inr=0.0,
        value_advantage_vs_next_best_inr=0.0,
    )

    assert decision.selected_action == TriageAction.NO_ACTION
    assert tracker.spent_inr == 0.0
