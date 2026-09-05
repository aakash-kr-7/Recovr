import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.models.transaction import Transaction
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.services.customer_history import get_customer_history
from app.agent.economics.historical_evidence import query_historical_evidence

@pytest.fixture
def db_session():
    """Create an isolated, in-memory SQLite database session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_closed_loop_customer_history_and_evidence(db_session):
    """
    Integration test proving the loop is closed.
    Seeds two synthetic transactions for the same customer_id with a known outcome
    on the first, then confirms get_customer_history() and query_historical_evidence()
    both reflect that first transaction when processing the second.
    """
    customer_id = "test_closed_loop_customer"
    decline_reason = "insufficient_funds"

    # Seed the first transaction
    txn1_id = str(uuid.uuid4())
    
    # We pre-compute what the history will look like after this transaction
    # so that it matches when we query for historical evidence for the second transaction.
    expected_history = {
        "prior_transaction_count": 1,
        "prior_success_rate": 1.0,
        "most_recent_decline_reason": decline_reason,
        "account_age_days": 2,
    }
    
    txn1 = Transaction(
        id=txn1_id,
        amount_inr=1000.0,
        decline_reason=decline_reason,
        decline_reason_raw="Insufficient Funds",
        customer_id=customer_id,
        customer_history=expected_history,
        failed_at=datetime.now(timezone.utc) - timedelta(days=2),
        is_synthetic=True,
        data_split="working",
    )
    db_session.add(txn1)
    
    # Seed the outcome for the first transaction
    outcome1 = RecoveryOutcomeRow(
        transaction_id=txn1_id,
        action="retry_same_rail",
        execution_status="executed",
        actual_recovered_inr=1000.0,
        observed_success=True,
        variance_inr=0.0,
        outcome_timestamp=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(outcome1)
    db_session.commit()

    # Now, process the second transaction
    # First, get the customer history for this customer
    history = get_customer_history(db_session, customer_id)
    
    # Assert get_customer_history reflects the first transaction
    assert history["prior_transaction_count"] == 1
    assert history["prior_success_rate"] == 1.0
    assert history["most_recent_decline_reason"] == decline_reason
    assert history["account_age_days"] >= 2  # The earliest transaction was 2 days ago

    # Second, check if query_historical_evidence reflects the outcome
    evidence = query_historical_evidence(
        db=db_session,
        decline_reason=decline_reason,
        customer_history=history,
        min_sample_size=1,  # Set to 1 just to bypass the threshold for this test and get actual rates
    )
    
    # Assert query_historical_evidence reflects the first transaction's outcome
    assert evidence.sample_size == 1
    assert evidence.count_recovered == 1
    assert evidence.count_not_recovered == 0
    assert evidence.retry_same_rail_rate == 1.0
