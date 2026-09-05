from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.webhooks import _complete_link_failure, _complete_link_payment
from app.db.session import Base
from app.models.audit_entry import AuditEntry
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db):
    db.add(Transaction(id="origin", razorpay_payment_id="pay_origin", amount_inr=100,
        decline_reason="bank_timeout", decline_reason_raw="timeout", customer_id="cust", customer_history={},
        failed_at=datetime.now(timezone.utc), is_synthetic=False, data_split="production"))
    db.add(AuditEntry(transaction_id="origin", path_taken="deterministic", action="escalate_to_dunning",
        reasoning_text="test", confidence=None, was_gated=False, amount_inr=100, outcome="pending"))
    db.add(RecoveryOutcomeRow(transaction_id="origin", action="escalate_to_dunning", execution_status="PENDING",
        actual_recovered_inr=None, observed_success=None, variance_inr=None, outcome_timestamp=datetime.now(timezone.utc),
        provider="razorpay", provider_reference="plink_1", mode="REAL_RAZORPAY_ACTION", amount_attempted=100,
        action_cost_inr=4, risk_penalty_inr=0, net_recovered_inr=None, outcome_source="executor"))
    db.commit()


def test_paid_link_completes_once_and_marks_partial_recovery():
    db = _session(); _seed(db)
    payload = {"payload": {"payment_link": {"entity": {"id": "plink_1", "amount_paid": 5000}}}}
    assert _complete_link_payment(db, payload)["status"] == "outcome_completed"
    outcome = db.query(RecoveryOutcomeRow).one()
    assert outcome.execution_status == "SUCCEEDED" and outcome.actual_recovered_inr == 50
    assert outcome.outcome_source == "razorpay.payment_link.paid"
    assert db.query(AuditEntry).one().outcome == "partial_recovery"
    assert _complete_link_payment(db, payload)["status"] == "duplicate"


def test_expired_or_unknown_link_is_safe_and_traceable():
    db = _session(); _seed(db)
    expired = {"payload": {"payment_link": {"entity": {"id": "plink_1"}}}}
    assert _complete_link_failure(db, expired)["status"] == "outcome_completed"
    assert db.query(RecoveryOutcomeRow).one().observed_success is False
    assert db.query(AuditEntry).one().outcome == "not_recovered"
    assert _complete_link_payment(db, {"payload": {"payment_link": {"entity": {"id": "missing"}}}})["status"] == "ignored"
