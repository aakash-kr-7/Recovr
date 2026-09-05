"""
Lightweight historical evidence lookup backed by SQLite.

Queries the recovery_outcomes table for past transactions with the same
decline reason and similar customer history.

CRITICAL ANTI-LEAKAGE CONSTRAINT:
This module must only ever query outcomes from the WORKING / DEVELOPMENT
partition (Transaction.data_split != 'holdout').  The evaluation holdout
set is strictly excluded at the SQL query level — never by convention or
post-filtering.  See docs/architecture/evaluation.md for the verification
protocol.

DESIGN PRINCIPLES:
1. No ML model: similarity is computed via a simple, transparent, documented
   rule (same most_recent_decline_reason bucket and prior_success_rate within
   a fixed tolerance band).
2. Honest confidence: if sample_size is below MIN_SAMPLE_SIZE (5), returns
   low_confidence=True with an empty rate dict rather than a misleadingly
   precise rate based on 1 or 2 cherry-picked cases.
3. Zero new infrastructure: uses existing SQLite session and tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction

# Minimum number of matching historical outcomes required before
# historical evidence is considered trustworthy enough to shift
# probability estimates. Below this threshold, low_confidence=True is
# returned and heuristics remain at their conservative defaults.
MIN_SAMPLE_SIZE: int = 5

# Tolerance band for customer prior_success_rate similarity.
# e.g., 0.80 matches candidates in [0.60, 1.00].
SUCCESS_RATE_TOLERANCE: float = 0.20

# Human-readable action names for supporting evidence summaries.
# Maps TriageAction values to natural-language descriptions matching the
# original spec example ("switch_rail was the most successful action").
_ACTION_DISPLAY_NAMES: dict[str, str] = {
    "retry_alt_rail": "switch_rail",
    "retry_same_rail": "retry_same_rail",
    "escalate_to_dunning": "escalate_to_dunning",
    "hold_for_review": "hold_for_review",
    "no_action": "no_action",
}


@dataclass(frozen=True)
class HistoricalEvidence:
    """Historical recovery outcome evidence for a decline pattern.

    Returned by query_historical_evidence().  Encapsulates aggregate
    metrics across past matching cases from the working dataset.
    """

    sample_size: int
    """Number of matching past transactions evaluated."""

    count_recovered: int
    """Number of matching transactions where recovery succeeded."""

    count_not_recovered: int
    """Number of matching transactions where recovery failed."""

    recovery_rate_by_action: dict[str, float] = field(default_factory=dict)
    """Observed recovery rate (0.0 to 1.0) for each executed action.
    Empty if low_confidence is True, preventing misleadingly precise
    rates on sparse data."""

    low_confidence: bool = True
    """True if sample_size is below MIN_SAMPLE_SIZE (5), signaling that
    heuristics should NOT be shifted by this sample."""

    summary: str = ""
    """Human-readable summary of the historical evidence, designed
    for display in RecoveryOption.supporting_evidence, e.g.
    '18 similar cases, 14 recovered (77.8%), switch_rail was the most successful action'."""

    @property
    def retry_same_rail_rate(self) -> float | None:
        """Historical success rate for retry_same_rail, or None."""
        return self.recovery_rate_by_action.get("retry_same_rail")

    @property
    def retry_alt_rail_rate(self) -> float | None:
        """Historical success rate for retry_alt_rail, or None."""
        return self.recovery_rate_by_action.get("retry_alt_rail")

    @property
    def dunning_recovery_rate(self) -> float | None:
        """Historical success rate for escalate_to_dunning, or None."""
        return self.recovery_rate_by_action.get("escalate_to_dunning")


def is_similar_customer_history(
    target_history: dict | None,
    candidate_history: dict | None,
    tolerance: float = SUCCESS_RATE_TOLERANCE,
) -> bool:
    """Determine whether candidate customer_history is similar to target.

    Rule:
    1. most_recent_decline_reason bucket:
       - Must match exactly (both None, or same decline reason string).
    2. prior_success_rate band:
       - If both are None (e.g. first-time customer), they match.
       - If one is None and the other is not None, they do not match.
       - If both are numbers, abs(target - candidate) <= tolerance (0.20).
    """
    target = target_history or {}
    candidate = candidate_history or {}

    # 1. most_recent_decline_reason check
    target_decline = target.get("most_recent_decline_reason") or target.get(
        "most_recent_decline"
    )
    cand_decline = candidate.get("most_recent_decline_reason") or candidate.get(
        "most_recent_decline"
    )
    if target_decline != cand_decline:
        return False

    # 2. prior_success_rate check
    target_rate = target.get("prior_success_rate")
    if target_rate is None:
        target_rate = target.get("success_rate")

    cand_rate = candidate.get("prior_success_rate")
    if cand_rate is None:
        cand_rate = candidate.get("success_rate")

    if target_rate is None and cand_rate is None:
        return True
    if target_rate is None or cand_rate is None:
        return False

    return abs(target_rate - cand_rate) <= tolerance


def query_historical_evidence(
    db: Session,
    decline_reason: str,
    customer_history: dict | None,
    min_sample_size: int = MIN_SAMPLE_SIZE,
) -> HistoricalEvidence:
    """Query recovery_outcomes for past cases with the same decline reason
    and similar customer history from the working dataset.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy database session.
    decline_reason : str
        Normalized decline reason of the incoming transaction.
    customer_history : dict | None
        Serialized customer history of the incoming transaction.
    min_sample_size : int, optional
        Sample size threshold below which low_confidence=True is returned,
        by default MIN_SAMPLE_SIZE (5).

    Returns
    -------
    HistoricalEvidence
        Aggregate sample size, recovery counts, action recovery rates,
        low_confidence flag, and human-readable summary string.
    """
    # CRITICAL ANTI-LEAKAGE QUERY:
    # Transaction.data_split != "holdout" is enforced in the SQL WHERE clause.
    # Rows belonging to the holdout set are never loaded into memory.
    stmt = (
        select(RecoveryOutcomeRow, Transaction.customer_history)
        .join(Transaction, RecoveryOutcomeRow.transaction_id == Transaction.id)
        .where(
            Transaction.data_split != "holdout",
            Transaction.decline_reason == decline_reason,
            RecoveryOutcomeRow.observed_success.is_not(None),
        )
    )
    rows = db.execute(stmt).all()

    # Defense-in-depth: filter by customer history similarity in Python
    matching_outcomes: list[RecoveryOutcomeRow] = []
    for outcome, cand_history in rows:
        if is_similar_customer_history(customer_history, cand_history):
            matching_outcomes.append(outcome)

    sample_size = len(matching_outcomes)
    if sample_size == 0:
        return HistoricalEvidence(
            sample_size=0,
            count_recovered=0,
            count_not_recovered=0,
            recovery_rate_by_action={},
            low_confidence=True,
            summary="0 similar cases found (low confidence).",
        )

    count_recovered = sum(
        1 for o in matching_outcomes if o.observed_success is True
    )
    count_not_recovered = sum(
        1 for o in matching_outcomes if o.observed_success is False
    )

    # If below sample-size threshold, flag low confidence and do NOT
    # return misleadingly precise rates.
    if sample_size < min_sample_size:
        return HistoricalEvidence(
            sample_size=sample_size,
            count_recovered=count_recovered,
            count_not_recovered=count_not_recovered,
            recovery_rate_by_action={},
            low_confidence=True,
            summary=(
                f"Low confidence: only {sample_size} historical matches "
                f"(minimum {min_sample_size} required)."
            ),
        )

    # Compute observed recovery rate for each attempted action
    action_attempts: dict[str, int] = {}
    action_successes: dict[str, int] = {}
    for o in matching_outcomes:
        action_attempts[o.action] = action_attempts.get(o.action, 0) + 1
        if o.observed_success is True:
            action_successes[o.action] = action_successes.get(o.action, 0) + 1

    recovery_rate_by_action = {
        action: round(action_successes.get(action, 0) / attempts, 4)
        for action, attempts in action_attempts.items()
    }

    # Identify most successful action among matching historical cases
    sorted_actions = sorted(
        recovery_rate_by_action.keys(),
        key=lambda a: (recovery_rate_by_action[a], action_attempts.get(a, 0)),
        reverse=True,
    )
    best_action = sorted_actions[0] if sorted_actions else "none"
    best_action_display = _ACTION_DISPLAY_NAMES.get(best_action, best_action)

    overall_rate = (count_recovered / sample_size) * 100.0
    summary = (
        f"{sample_size} similar cases, {count_recovered} recovered "
        f"({overall_rate:.1f}%), {best_action_display} was the most "
        f"successful action"
    )

    return HistoricalEvidence(
        sample_size=sample_size,
        count_recovered=count_recovered,
        count_not_recovered=count_not_recovered,
        recovery_rate_by_action=recovery_rate_by_action,
        low_confidence=False,
        summary=summary,
    )
