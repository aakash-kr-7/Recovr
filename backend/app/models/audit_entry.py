"""
ORM model for the audit trail.

This table is the audit trail — not a log file, not a separate export.
The dashboard's audit view (frontend/src/pages/AuditTrailPage.tsx) reads
this table directly. See docs/architecture/overview.md, "why the executor
is a separate component from the reasoning", for why every entry captures
both the decision and the reasoning that produced it.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String, index=True)

    path_taken: Mapped[str] = mapped_column(String)
    """'deterministic' or 'reasoning' — which path in the two-path agent
    produced this decision. See docs/decisions/0003-two-path-agent.md."""

    action: Mapped[str] = mapped_column(String)
    """One of the allow-listed actions defined in app/agent/executor.py.
    Never free text — the executor rejects anything outside this set
    before it reaches this table."""

    reasoning_text: Mapped[str] = mapped_column(String)
    """For the reasoning path: the model's own natural-language
    explanation, stored verbatim. For the deterministic path: a
    templated string naming which rule fired and why (see
    decline_taxonomy.py) — kept in the same field so the dashboard can
    render both paths identically without a null-handling special case."""

    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    """Only populated for the reasoning path. Null for deterministic-path
    entries, since a fixed rule has no meaningful confidence score —
    rendering this as 1.0 would misrepresent it as the model having
    reasoned about the case."""

    was_gated: Mapped[bool] = mapped_column(default=False)
    """True if this decision was routed to hold_for_review by the
    confidence gate rather than auto-executed. See executor.py."""

    outcome: Mapped[str] = mapped_column(String, nullable=True)
    """'recovered', 'not_recovered', 'pending', or null if not yet known.
    For synthetic eval data this is derived from ground_truth_label; for
    real transactions it is updated asynchronously as Razorpay reports
    the retry result."""

    amount_inr: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
