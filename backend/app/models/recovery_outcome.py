"""
ORM model for a recovery outcome.

Stores the measured result of an executed recovery action: what was
actually recovered, whether it succeeded, and the variance against the
expected recovery at decision time.

This table is deliberately SEPARATE from recovery_decisions — per the
project's principle (docs/architecture/overview.md) of never letting
an expected value and a measured outcome share a row.  When they share
a row it is too easy to silently overwrite an expectation with a
result, which makes calibration analysis unreliable because you can
no longer compare what the system predicted with what actually happened.

Populated asynchronously: for real transactions, when Razorpay reports
the retry result via webhook; for synthetic eval data, from the
ground_truth_label in the evaluation script.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RecoveryOutcomeRow(Base):
    __tablename__ = "recovery_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    transaction_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    """References transactions.id. Indexed for the same reason as in
    recovery_decisions — evaluation queries join on this column.
    No formal ForeignKey constraint, matching the project's existing
    convention (see recovery_decision.py and audit_entry.py)."""

    action: Mapped[str] = mapped_column(String)
    """The action that was actually executed (one of the TriageAction
    enum values). Stored as a plain string matching the convention in
    audit_entry.py and recovery_decision.py."""

    execution_status: Mapped[str] = mapped_column(String)
    """Current execution state: 'pending', 'executed',
    'failed_to_execute', 'skipped'. Kept as a plain string rather than
    a SQL enum — the executor may need to add states as new action
    types appear, and a string column avoids a schema migration for
    each new state."""

    actual_recovered_inr: Mapped[float] = mapped_column(Float, nullable=True)
    """Amount actually recovered, in INR. Null until the execution
    outcome is known — never zero as a placeholder, because zero is a
    valid recovery amount (attempted and genuinely recovered nothing)."""

    observed_success: Mapped[bool] = mapped_column(Boolean, nullable=True)
    """True if the recovery action succeeded, False if it failed, null
    if the outcome is not yet known.  Kept as an explicit boolean
    rather than inferred from actual_recovered_inr > 0, because a
    partial recovery can still count as a success depending on
    business rules configured per-merchant."""

    variance_inr: Mapped[float] = mapped_column(Float, nullable=True)
    """actual_recovered_inr minus the expected recovery from the
    RecoveryDecision at decision time.  Null until the outcome is
    known.  Positive means the system under-estimated recovery;
    negative means it over-estimated.  This is the core feedback
    signal for calibration — without it, the system cannot learn
    whether its probability estimates are systematically biased."""

    outcome_timestamp: Mapped[datetime] = mapped_column(DateTime)
    """When the outcome was recorded.  For real transactions, this is
    the Razorpay webhook timestamp; for synthetic eval data, this is
    the evaluation run timestamp.  Not defaulted to utcnow() because
    the timestamp must reflect the real event time, not the DB write
    time."""

    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    mode: Mapped[str] = mapped_column(String, default="BOUNDED_SIMULATION")
    amount_attempted: Mapped[float] = mapped_column(Float, default=0.0)
    action_cost_inr: Mapped[float] = mapped_column(Float, default=0.0)
    risk_penalty_inr: Mapped[float] = mapped_column(Float, default=0.0)
    net_recovered_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome_source: Mapped[str] = mapped_column(String, default="executor")
