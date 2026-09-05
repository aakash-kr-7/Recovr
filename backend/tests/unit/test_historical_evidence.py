"""
Unit tests for historical evidence lookup and holdout isolation.

Covers:
1. Zero historical matches returns low_confidence=True and no fabricated rate.
2. Historical matches below threshold (N < 5) returns low_confidence=True.
3. Sufficient historical matches returns real, arithmetically exact rates.
4. CRITICAL: Outcomes tagged with data_split='holdout' are NEVER queried or returned.
5. Outcomes with observed_success=None are excluded.
6. Dissimilar customer history patterns are filtered out.
7. Probability heuristics integration: shifts when confident, falls back when low_confidence.
8. Supporting evidence formatting on RecoveryOption.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agent.economics.historical_evidence import (
    MIN_SAMPLE_SIZE,
    HistoricalEvidence,
    is_similar_customer_history,
    query_historical_evidence,
)
from app.agent.economics.probability_heuristics import estimate_probabilities
from app.agent.economics.scoring import score_recovery_options
from app.db.session import Base
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction


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


def _create_txn_and_outcome(
    db: Session,
    txn_id: str,
    decline_reason: str,
    action: str,
    observed_success: bool | None,
    customer_history: dict,
    data_split: str = "working",
) -> tuple[Transaction, RecoveryOutcomeRow]:
    """Helper to insert a transaction and corresponding outcome."""
    txn = Transaction(
        id=txn_id,
        amount_inr=1500.0,
        decline_reason=decline_reason,
        decline_reason_raw=decline_reason.replace("_", " ").title(),
        customer_id=f"cust_{txn_id}",
        customer_history=customer_history,
        failed_at=datetime.now(timezone.utc),
        is_synthetic=True,
        data_split=data_split,
    )
    db.add(txn)

    outcome = RecoveryOutcomeRow(
        transaction_id=txn_id,
        action=action,
        execution_status="executed" if observed_success is not None else "pending",
        actual_recovered_inr=1500.0 if observed_success else 0.0 if observed_success is False else None,
        observed_success=observed_success,
        variance_inr=0.0 if observed_success is not None else None,
        outcome_timestamp=datetime.now(timezone.utc),
    )
    db.add(outcome)
    db.commit()
    return txn, outcome


def test_zero_matches_returns_low_confidence_and_no_fabricated_rate(db_session):
    """A case with zero historical matches returns low_confidence=True
    and does not crash or return a fabricated rate."""
    result = query_historical_evidence(
        db=db_session,
        decline_reason="insufficient_funds",
        customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
    )

    assert result.low_confidence is True
    assert result.sample_size == 0
    assert result.count_recovered == 0
    assert result.count_not_recovered == 0
    assert result.recovery_rate_by_action == {}
    assert "0 similar cases" in result.summary


def test_below_threshold_matches_returns_low_confidence(db_session):
    """A case with historical matches below sample-size threshold (N=3 < 5)
    returns low_confidence=True and an empty recovery_rate_by_action dict."""
    for i in range(3):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"working_below_{i}",
            decline_reason="bank_timeout",
            action="retry_same_rail",
            observed_success=(i < 2),  # 2 success, 1 fail
            customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
            data_split="working",
        )

    result = query_historical_evidence(
        db=db_session,
        decline_reason="bank_timeout",
        customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
    )

    assert result.sample_size == 3
    assert result.low_confidence is True
    assert result.count_recovered == 2
    assert result.count_not_recovered == 1
    # Empty rate dict ensures caller cannot use a misleadingly precise rate
    assert result.recovery_rate_by_action == {}
    assert "Low confidence: only 3 historical matches" in result.summary


def test_sufficient_matches_computes_arithmetically_correct_rates(db_session):
    """A case with sufficient historical matches (N=6 >= 5) returns real
    computed rates that are arithmetically correct given fixture data."""
    # 4 cases for retry_same_rail: 3 success, 1 fail -> 3/4 = 0.75 (75%)
    for i in range(4):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"same_rail_{i}",
            decline_reason="bank_timeout",
            action="retry_same_rail",
            observed_success=(i < 3),
            customer_history={"prior_success_rate": 0.85, "most_recent_decline_reason": None},
            data_split="working",
        )

    # 2 cases for retry_alt_rail: 2 success, 0 fail -> 2/2 = 1.00 (100%)
    for i in range(2):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"alt_rail_{i}",
            decline_reason="bank_timeout",
            action="retry_alt_rail",
            observed_success=True,
            customer_history={"prior_success_rate": 0.85, "most_recent_decline_reason": None},
            data_split="working",
        )

    result = query_historical_evidence(
        db=db_session,
        decline_reason="bank_timeout",
        customer_history={"prior_success_rate": 0.80, "most_recent_decline_reason": None},
    )

    assert result.sample_size == 6
    assert result.low_confidence is False
    assert result.count_recovered == 5
    assert result.count_not_recovered == 1

    # Arithmetic checks on action recovery rates
    assert result.recovery_rate_by_action["retry_same_rail"] == pytest.approx(0.75, abs=1e-4)
    assert result.recovery_rate_by_action["retry_alt_rail"] == pytest.approx(1.00, abs=1e-4)

    # Property accessors
    assert result.retry_same_rail_rate == pytest.approx(0.75, abs=1e-4)
    assert result.retry_alt_rail_rate == pytest.approx(1.00, abs=1e-4)
    assert result.dunning_recovery_rate is None

    # Summary verification: 5/6 = 83.3%, switch_rail was most successful
    assert "6 similar cases, 5 recovered (83.3%)" in result.summary
    assert "switch_rail was the most successful action" in result.summary


def test_holdout_outcomes_never_queried(db_session):
    """CRITICAL REQUIREMENT:
    Outcomes tagged as belonging to the held-out evaluation set are NEVER
    returned by this function, even if they would otherwise match.
    """
    # 1. Seed 10 matching outcomes in the HOLDOUT set (all successes)
    for i in range(10):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"holdout_txn_{i}",
            decline_reason="insufficient_funds",
            action="retry_same_rail",
            observed_success=True,
            customer_history={"prior_success_rate": 0.90, "most_recent_decline_reason": None},
            data_split="holdout",  # <--- CRITICAL HOLDOUT SPLIT
        )

    # 2. Seed only 2 matching outcomes in the WORKING set (both failures)
    for i in range(2):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"working_txn_{i}",
            decline_reason="insufficient_funds",
            action="retry_same_rail",
            observed_success=False,
            customer_history={"prior_success_rate": 0.90, "most_recent_decline_reason": None},
            data_split="working",
        )

    # Query for matching transactions
    result = query_historical_evidence(
        db=db_session,
        decline_reason="insufficient_funds",
        customer_history={"prior_success_rate": 0.90, "most_recent_decline_reason": None},
    )

    # Assert: NONE of the 10 holdout outcomes were queried!
    # If holdout had leaked, sample_size would be 12 and count_recovered would be 10.
    assert result.sample_size == 2
    assert result.count_recovered == 0  # Holdout successes were completely excluded
    assert result.count_not_recovered == 2
    assert result.low_confidence is True  # Only 2 working samples, so low confidence

    # Delete the 2 working records to prove holdout alone returns zero
    db_session.query(Transaction).filter(Transaction.data_split == "working").delete()
    db_session.commit()

    pure_holdout_result = query_historical_evidence(
        db=db_session,
        decline_reason="insufficient_funds",
        customer_history={"prior_success_rate": 0.90, "most_recent_decline_reason": None},
    )
    assert pure_holdout_result.sample_size == 0
    assert pure_holdout_result.low_confidence is True


def test_unobserved_outcomes_excluded(db_session):
    """Rows with observed_success=None (execution pending) are not counted."""
    # 5 transactions, but only 2 have known outcomes
    for i in range(3):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"pending_{i}",
            decline_reason="bank_timeout",
            action="retry_same_rail",
            observed_success=None,  # Not known yet
            customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
            data_split="working",
        )
    for i in range(2):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"finished_{i}",
            decline_reason="bank_timeout",
            action="retry_same_rail",
            observed_success=True,
            customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
            data_split="working",
        )

    result = query_historical_evidence(
        db=db_session,
        decline_reason="bank_timeout",
        customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
    )
    assert result.sample_size == 2
    assert result.low_confidence is True


def test_dissimilar_customer_history_excluded(db_session):
    """Transactions with dissimilar customer history patterns are filtered out."""
    # 5 cases with different decline reason history
    for i in range(5):
        _create_txn_and_outcome(
            db=db_session,
            txn_id=f"dissimilar_{i}",
            decline_reason="insufficient_funds",
            action="retry_same_rail",
            observed_success=True,
            customer_history={
                "prior_success_rate": 0.8,
                "most_recent_decline_reason": "card_expired",  # Doesn't match None
            },
            data_split="working",
        )

    result = query_historical_evidence(
        db=db_session,
        decline_reason="insufficient_funds",
        customer_history={"prior_success_rate": 0.8, "most_recent_decline_reason": None},
    )
    assert result.sample_size == 0
    assert result.low_confidence is True


def test_probability_heuristics_shift_with_evidence():
    """Probability heuristics measurably shift when confident historical evidence exists,
    and fall back to the original heuristic when evidence is absent or low_confidence."""
    # 1. Base heuristics without evidence
    base_probs = estimate_probabilities(
        decline_reason="insufficient_funds",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
        historical_evidence=None,
    )
    assert base_probs["retry_same_rail"] == pytest.approx(0.26, abs=1e-2)

    # 2. Evidence with low_confidence=True -> MUST fall back to original heuristic
    low_conf_evidence = HistoricalEvidence(
        sample_size=3,
        count_recovered=3,
        count_not_recovered=0,
        recovery_rate_by_action={"retry_same_rail": 0.99},
        low_confidence=True,
    )
    low_conf_probs = estimate_probabilities(
        decline_reason="insufficient_funds",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
        historical_evidence=low_conf_evidence,
    )
    # Must NOT shift to 0.99; falls back to original heuristic exactly
    assert low_conf_probs["retry_same_rail"] == base_probs["retry_same_rail"]

    # 3. Confident evidence (low_confidence=False) -> Measurably shifts probability
    high_conf_evidence = HistoricalEvidence(
        sample_size=18,
        count_recovered=14,
        count_not_recovered=4,
        recovery_rate_by_action={
            "retry_same_rail": 0.65,
            "retry_alt_rail": 0.778,
        },
        low_confidence=False,
        summary="18 similar cases, 14 recovered (77.8%), switch_rail was the most successful action",
    )
    high_conf_probs = estimate_probabilities(
        decline_reason="insufficient_funds",
        customer_prior_success_rate=0.5,
        customer_account_age_days=100,
        customer_most_recent_decline=None,
        historical_evidence=high_conf_evidence,
    )
    # Measurably shifted:
    assert high_conf_probs["retry_same_rail"] == pytest.approx(0.65, abs=1e-4)
    assert high_conf_probs["retry_alt_rail"] == pytest.approx(0.778, abs=1e-4)


def test_supporting_evidence_string_format():
    """RecoveryOption.supporting_evidence includes the human-readable summary
    matching the spec's exact example format."""
    evidence = HistoricalEvidence(
        sample_size=18,
        count_recovered=14,
        count_not_recovered=4,
        recovery_rate_by_action={"retry_alt_rail": 0.778, "retry_same_rail": 0.50},
        low_confidence=False,
        summary="18 similar cases, 14 recovered (77.8%), switch_rail was the most successful action",
    )

    decision = score_recovery_options(
        transaction_id="txn-evidence-1",
        amount_inr=2000.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.8,
        customer_account_age_days=120,
        customer_most_recent_decline=None,
        permitted_actions=list(TriageAction),
        historical_evidence=evidence,
    )

    # Check that the summary was fed into supporting_evidence
    top_option = decision.options[0]
    expected_substring = "18 similar cases, 14 recovered (77.8%), switch_rail was the most successful action"
    assert expected_substring in top_option.supporting_evidence
