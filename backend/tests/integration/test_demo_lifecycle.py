"""End-to-end read-model validation for the documented mocked callback flow.

This intentionally uses an in-memory database and a mock provider reference.
It validates RECOVR's callback/persistence/UI-read-model contract without
claiming that the callback came from Razorpay.
"""

from datetime import datetime
import hashlib
import hmac
import json
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.economics.historical_evidence import query_historical_evidence
from app.api.webhooks import _complete_link_payment
from app.db.session import Base
from app.models.audit_entry import AuditEntry
from app.models.recovery_decision import RecoveryDecisionRow
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction


def test_mocked_payment_link_callback_updates_lifecycle_and_evidence() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    history = {"prior_success_rate": 0.8, "most_recent_decline_reason": None}
    db.add_all(
        [
            Transaction(
                id="golden-production",
                razorpay_payment_id="pay_golden",
                amount_inr=100.0,
                decline_reason="card_reported_lost_or_stolen",
                decline_reason_raw="lost card",
                customer_id="demo-customer",
                customer_history=history,
                failed_at=datetime.utcnow(),
                is_synthetic=False,
                data_split="production",
            ),
            Transaction(
                id="holdout-must-not-leak",
                razorpay_payment_id="pay_holdout",
                amount_inr=100.0,
                decline_reason="card_reported_lost_or_stolen",
                decline_reason_raw="lost card",
                customer_id="holdout-customer",
                customer_history=history,
                failed_at=datetime.utcnow(),
                is_synthetic=True,
                data_split="holdout",
            ),
        ]
    )
    db.add_all(
        [
            RecoveryDecisionRow(
                transaction_id="golden-production",
                options_json=[],
                selected_action="escalate_to_dunning",
                selected_expected_net_recovery_inr=26.75,
                value_advantage_vs_next_best_inr=23.3,
                confidence=None,
                reasoning_text="Golden demo selection.",
                decision_path="deterministic",
                was_gated=False,
            ),
            AuditEntry(
                transaction_id="golden-production",
                path_taken="deterministic",
                action="escalate_to_dunning",
                reasoning_text="Golden demo selection.",
                confidence=None,
                was_gated=False,
                amount_inr=100.0,
                outcome="pending",
            ),
            RecoveryOutcomeRow(
                transaction_id="golden-production",
                action="escalate_to_dunning",
                execution_status="PENDING",
                actual_recovered_inr=None,
                observed_success=None,
                variance_inr=None,
                outcome_timestamp=datetime.utcnow(),
                provider="mock_razorpay",
                provider_reference="plink_mock_golden",
                mode="BOUNDED_SIMULATION",
                amount_attempted=100.0,
                action_cost_inr=4.0,
                risk_penalty_inr=0.0,
                net_recovered_inr=None,
                outcome_source="mock_executor",
            ),
            RecoveryOutcomeRow(
                transaction_id="holdout-must-not-leak",
                action="escalate_to_dunning",
                execution_status="SUCCEEDED",
                actual_recovered_inr=100.0,
                observed_success=True,
                variance_inr=0.0,
                outcome_timestamp=datetime.utcnow(),
                provider="mock_razorpay",
                provider_reference="plink_mock_holdout",
                mode="BOUNDED_SIMULATION",
                amount_attempted=100.0,
                action_cost_inr=4.0,
                risk_penalty_inr=0.0,
                net_recovered_inr=96.0,
                outcome_source="mock_executor",
            ),
        ]
    )
    db.commit()

    payload = {"payload": {"payment_link": {"entity": {"id": "plink_mock_golden", "amount_paid": 10000}}}}
    assert _complete_link_payment(db, payload)["status"] == "outcome_completed"
    assert _complete_link_payment(db, payload)["status"] == "duplicate"

    decision = db.query(RecoveryDecisionRow).filter_by(transaction_id="golden-production").one()
    outcome = db.query(RecoveryOutcomeRow).filter_by(transaction_id="golden-production").one()
    audit = db.query(AuditEntry).filter_by(transaction_id="golden-production").one()
    assert decision.selected_action == outcome.action == audit.action
    assert outcome.provider_reference == "plink_mock_golden"
    assert outcome.execution_status == "SUCCEEDED"
    assert outcome.actual_recovered_inr == 100.0
    assert audit.outcome == "recovered"

    evidence = query_historical_evidence(
        db,
        decline_reason="card_reported_lost_or_stolen",
        customer_history=history,
        min_sample_size=1,
    )
    assert evidence.sample_size == 1
    assert evidence.count_recovered == 1
    assert evidence.recovery_rate_by_action == {"escalate_to_dunning": 1.0}


@patch("app.api.webhooks.get_triage_decision", side_effect=ValueError("malformed provider output"))
def test_malformed_llm_output_is_held_and_audited(_mock_llm) -> None:
    """An ambiguous payment must not become an automatic action on LLM failure."""
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.db.session import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    app.dependency_overrides[get_db] = lambda: session
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_malformed_llm_demo",
                    "amount": 10000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "ambiguous_new_failure",
                    "error_description": "ambiguous provider response",
                    "contact": "demo@example.test",
                    "created_at": 1_700_000_000,
                }
            }
        },
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(
        get_settings().razorpay_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/webhooks/razorpay",
                content=body,
                headers={"x-razorpay-signature": signature},
            )
        assert response.status_code == 200
        transaction_id = response.json()["transaction_id"]
        decision = session.query(RecoveryDecisionRow).filter_by(transaction_id=transaction_id).one()
        outcome = session.query(RecoveryOutcomeRow).filter_by(transaction_id=transaction_id).one()
        audit = session.query(AuditEntry).filter_by(transaction_id=transaction_id).one()
        assert decision.selected_action == outcome.action == audit.action == "hold_for_review"
        assert outcome.execution_status == "HELD"
        assert audit.outcome == "held_for_review"
        assert "LLM unavailable" in decision.reasoning_text
    finally:
        app.dependency_overrides.clear()
