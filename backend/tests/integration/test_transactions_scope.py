import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.transaction import Transaction
from app.models.audit_entry import AuditEntry
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.recovery_decision import RecoveryDecisionRow

client = TestClient(app)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def setup_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()


def test_funnel_summary_scope_consistency_and_honest_recovery_rate(db_session):
    now = datetime.now(timezone.utc)
    
    # Historical test run (demo split)
    hist_tx = Transaction(
        id="hist-1",
        razorpay_payment_id="pay_hist_1",
        amount_inr=50000.0,
        decline_reason="insufficient_funds",
        decline_reason_raw="Insufficient Funds",
        customer_id="cust_hist",
        customer_history={},
        failed_at=now,
        is_synthetic=True,
        data_split="demo",
    )
    hist_audit = AuditEntry(
        transaction_id="hist-1",
        path_taken="deterministic",
        action="retry_same_rail",
        reasoning_text="History retry",
        confidence=1.0,
        was_gated=False,
        amount_inr=50000.0,
        outcome="not_recovered",
        created_at=now,
    )
    hist_outcome = RecoveryOutcomeRow(
        transaction_id="hist-1",
        action="retry_same_rail",
        execution_status="FAILED",
        actual_recovered_inr=0.0,
        observed_success=False,
        variance_inr=0.0,
        outcome_timestamp=now,
        provider="mock",
        mode="BOUNDED_SIMULATION",
        amount_attempted=50000.0,
        action_cost_inr=8.0,
        risk_penalty_inr=0.0,
        net_recovered_inr=-8.0,
        outcome_source="test",
    )

    # Current session: Transaction 1 (Recovered retry)
    sess_tx1 = Transaction(
        id="sess-1",
        razorpay_payment_id="pay_sess_1",
        amount_inr=2500.0,
        decline_reason="bank_timeout",
        decline_reason_raw="Bank Timeout",
        customer_id="cust_sess",
        customer_history={},
        failed_at=now,
        is_synthetic=True,
        data_split="live_mode",
    )
    sess_audit1 = AuditEntry(
        transaction_id="sess-1",
        path_taken="reasoning",
        action="retry_same_rail",
        reasoning_text="Delayed retry",
        confidence=0.9,
        was_gated=False,
        amount_inr=2500.0,
        outcome="recovered",
        created_at=now,
    )
    sess_outcome1 = RecoveryOutcomeRow(
        transaction_id="sess-1",
        action="retry_same_rail",
        execution_status="SUCCEEDED",
        actual_recovered_inr=2500.0,
        observed_success=True,
        variance_inr=0.0,
        outcome_timestamp=now,
        provider="mock",
        mode="BOUNDED_SIMULATION",
        amount_attempted=2500.0,
        action_cost_inr=8.0,
        risk_penalty_inr=0.0,
        net_recovered_inr=2492.0,
        outcome_source="test",
    )

    # Current session: Transaction 2 (Held for review - Spend cap)
    # Should NOT be in recovery rate denominator as a failure!
    sess_tx2 = Transaction(
        id="sess-2",
        razorpay_payment_id="pay_sess_2",
        amount_inr=600000.0,
        decline_reason="bank_timeout",
        decline_reason_raw="Bank Timeout",
        customer_id="cust_sess_2",
        customer_history={},
        failed_at=now,
        is_synthetic=True,
        data_split="live_mode",
    )
    sess_audit2 = AuditEntry(
        transaction_id="sess-2",
        path_taken="reasoning",
        action="hold_for_review",
        reasoning_text="Gated: spend cap",
        confidence=0.9,
        was_gated=True,
        amount_inr=600000.0,
        outcome="held_for_review",
        created_at=now,
    )
    sess_outcome2 = RecoveryOutcomeRow(
        transaction_id="sess-2",
        action="hold_for_review",
        execution_status="HELD",
        actual_recovered_inr=None,
        observed_success=None,
        variance_inr=None,
        outcome_timestamp=now,
        provider="mock",
        mode="BOUNDED_SIMULATION",
        amount_attempted=0.0,
        action_cost_inr=0.0,
        risk_penalty_inr=0.0,
        net_recovered_inr=None,
        outcome_source="test",
    )

    db_session.add_all([
        hist_tx, hist_audit, hist_outcome,
        sess_tx1, sess_audit1, sess_outcome1,
        sess_tx2, sess_audit2, sess_outcome2,
    ])
    db_session.commit()

    # 1. Test Session Scope (Default)
    resp_session = client.get("/transactions/funnel-summary?scope=session")
    assert resp_session.status_code == 200
    data_session = resp_session.json()
    assert data_session["scope"] == "session"
    assert data_session["transaction_count"] == 2
    assert data_session["attempted_volume_inr"] == 602500.0
    assert data_session["recovered_volume_inr"] == 2500.0
    assert data_session["pending_review_count"] == 1
    assert data_session["pending_review_volume_inr"] == 600000.0
    assert data_session["resolved_count"] == 1
    assert data_session["resolved_volume_inr"] == 2500.0
    # Honest recovery rate: 2500 / 2500 = 100%, NOT 2500 / 602500 = 0.4%
    assert data_session["recovery_rate_pct"] == 100.0

    # 2. Test All-Time Scope
    resp_all = client.get("/transactions/funnel-summary?scope=all")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert data_all["scope"] == "all"
    assert data_all["transaction_count"] == 3
    assert data_all["attempted_volume_inr"] == 652500.0
    assert data_all["recovered_volume_inr"] == 2500.0
    assert data_all["pending_review_count"] == 1
    assert data_all["pending_review_volume_inr"] == 600000.0
    assert data_all["resolved_count"] == 2
    assert data_all["resolved_volume_inr"] == 52500.0  # 50000 + 2500
    # 2500 / 52500 = 4.8%
    assert round(data_all["recovery_rate_pct"], 1) == 4.8

    # 3. Test Recent Transactions Scoping
    recent_sess = client.get("/transactions/recent?scope=session").json()
    assert len(recent_sess) == 2
    assert set(t["transaction_id"] for t in recent_sess) == {"sess-1", "sess-2"}

    recent_all = client.get("/transactions/recent?scope=all").json()
    assert len(recent_all) == 3
