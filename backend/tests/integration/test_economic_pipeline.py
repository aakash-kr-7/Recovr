"""Integration tests for the economic pipeline (gate -> scoring -> executor)."""

from unittest.mock import patch
from datetime import datetime
import json

from app.agent.executor import BatchSpendTracker
from app.api.webhooks import _live_spend_tracker
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction, TriagePath
from app.agent.economics.scoring import score_recovery_options

# Import the actual module that webhooks and evaluation will use to execute the pipeline
# We'll simulate the pipeline flow directly to test the integration logic.

def _make_transaction(decline_reason: str, amount_inr: float = 1000.0, history=None) -> Transaction:
    if history is None:
        history = {"success_rate": 0.8, "account_age_days": 180}
    return Transaction(
        id="test-txn-1",
        amount_inr=amount_inr,
        decline_reason=decline_reason,
        decline_reason_raw=decline_reason.replace("_", " "),
        customer_id="test-customer",
        customer_history=history,
        failed_at=datetime.utcnow(),
        is_synthetic=True,
    )

def test_forbidden_actions_never_selected():
    """Construct a case where an economically-attractive action is deliberately
    excluded from the permitted set and assert it never appears.
    
    We'll bypass the webhooks router and test the scoring engine integration directly.
    """
    txn = _make_transaction(decline_reason="bank_timeout", amount_inr=1000.0)
    
    # RETRY_SAME_RAIL would normally score well for a bank timeout.
    # We deliberately omit it from the permitted actions.
    permitted = [TriageAction.HOLD_FOR_REVIEW, TriageAction.ESCALATE_TO_DUNNING]
    
    decision = score_recovery_options(
        transaction_id=txn.id,
        amount_inr=txn.amount_inr,
        decline_reason=txn.decline_reason,
        customer_prior_success_rate=txn.customer_history.get("success_rate"),
        customer_account_age_days=txn.customer_history.get("account_age_days"),
        customer_most_recent_decline=txn.customer_history.get("most_recent_decline"),
        permitted_actions=permitted,
    )
    
    # Assert RETRY_SAME_RAIL is not in the options
    output_actions = {opt.action for opt in decision.options}
    assert TriageAction.RETRY_SAME_RAIL not in output_actions
    assert decision.selected_action in permitted


@patch("app.api.webhooks.get_triage_decision")
def test_deterministic_fast_path_bypasses_reasoning_path(mock_get_triage_decision):
    """Deterministic fast-path transactions still bypass the reasoning path entirely."""
    # Test using the actual webhook endpoint logic directly via Fastapi TestClient
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import get_settings
    import hmac
    import hashlib
    
    from unittest.mock import MagicMock
    from app.db.session import get_db
    
    client = TestClient(app)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    
    settings = get_settings()
    
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test123",
                    "amount": 100000, # paise
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "card_reported_lost_or_stolen",
                    "error_description": "card lost",
                    "contact": "test@example.com",
                    "created_at": 1600000000
                }
            }
        }
    }
    body_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        settings.razorpay_webhook_secret.encode(), body_bytes, hashlib.sha256
    ).hexdigest()
    
    # card_reported_lost_or_stolen is a deterministic fast-path decline reason.
    response = client.post(
        "/webhooks/razorpay", 
        content=body_bytes, 
        headers={"x-razorpay-signature": signature}
    )
    
    assert response.status_code == 200
    mock_get_triage_decision.assert_not_called()


def test_divergence_recorded_and_economic_wins():
    """When reasoning-path suggestion and economic-layer selection diverge, both are
    recorded, and the economic layer's choice is what actually executes.
    """
    from app.agent.executor import execute
    from app.agent.gate import GateDecision
    
    txn = _make_transaction(decline_reason="insufficient_funds", amount_inr=10.0, history={"success_rate": 0.1})
    
    # Let's say reasoning path suggests RETRY_SAME_RAIL
    candidate_action = TriageAction.RETRY_SAME_RAIL
    base_reasoning = "Model thinks we should retry."
    
    # Run economic scoring
    economic_decision = score_recovery_options(
        transaction_id=txn.id,
        amount_inr=txn.amount_inr,
        decline_reason=txn.decline_reason,
        customer_prior_success_rate=txn.customer_history.get("success_rate"),
        customer_account_age_days=txn.customer_history.get("account_age_days"),
        customer_most_recent_decline=txn.customer_history.get("most_recent_decline"),
        permitted_actions=list(TriageAction),
    )
    
    # Economic scoring will pick a different action (not RETRY_SAME_RAIL because the amount is too low to justify the retry cost).
    assert economic_decision.selected_action != candidate_action
    
    reasoning_text = (
        f"Path suggested {candidate_action.value} but Economic scoring "
        f"selected {economic_decision.selected_action.value}. "
        f"Base reasoning: {base_reasoning}"
    )
    
    decision = execute(
        transaction=txn,
        path=TriagePath.REASONING,
        action=economic_decision.selected_action,
        reasoning_text=reasoning_text,
        confidence=0.9,
        spend_tracker=BatchSpendTracker(cap_inr=10000.0),
        options=economic_decision.options,
        selected_expected_net_recovery_inr=economic_decision.selected_expected_net_recovery_inr,
        value_advantage_vs_next_best_inr=economic_decision.value_advantage_vs_next_best_inr,
    )
    
    # The economic choice won and executed
    assert decision.selected_action == economic_decision.selected_action
    assert "Path suggested retry_same_rail" in decision.reasoning_text
    assert "Economic scoring selected " in decision.reasoning_text


def test_evaluation_report_action_level_section_structure():
    """The primary report evaluates selected actions against hidden outcomes.

    The legacy retry/not-retry matrix remains available only as a secondary
    diagnostic for backwards-compatible dashboard rendering.
    """
    from scripts.run_evaluation import run_evaluation

    report = run_evaluation()
    assert report["evaluation_version"] == "comparable_action_economics_v3"
    assert set(report["unconstrained"]) == {"retry_all_same_rail", "fixed_rule_policy", "recovr"}
    assert set(report["constrained"]) == set(report["unconstrained"])
    for view in (report["unconstrained"], report["constrained"]):
        assert {row["transaction_count"] for row in view.values()} == {report["holdout_set_size"]}
        assert len({row["total_amount_at_risk_inr"] for row in view.values()}) == 1
        for row in view.values():
            assert row["realized_regret_inr"] == row["opportunity_loss_inr"]
            assert row["expected_regret_inr"] >= 0
    assert report["multi_seed_robustness"]["recovr"]["seeds"] == [42, 7, 19, 73, 101]
