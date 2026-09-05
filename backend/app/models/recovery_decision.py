"""
ORM model for a recovery decision.

Stores the output of the economic scoring formula: which action was
selected, what its expected net recovery is, and the full set of
options the system evaluated (as JSON, matching the customer_history
JSON column pattern in transaction.py).

Scalar fields are real columns so the evaluation report can query them
directly (e.g. aggregate selected_expected_net_recovery_inr by path).
The options list is JSON because it's variable-length and only needs
to be unpacked for the audit-trail detail view, never filtered or
aggregated in SQL.

This table is deliberately SEPARATE from recovery_outcome — see
docs/decisions/0006-economic-decision-layer.md for why an expected
value and a measured outcome must never share a row.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RecoveryDecisionRow(Base):
    __tablename__ = "recovery_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    transaction_id: Mapped[str] = mapped_column(String, index=True)
    """Foreign key to transactions.id. Not declared as a formal
    ForeignKey constraint because the existing project tables (e.g.
    audit_entries.transaction_id) follow the same pattern — index only,
    no FK constraint — keeping SQLite setup zero-friction for anyone
    cloning the repo."""

    options_json: Mapped[dict] = mapped_column(JSON)
    """The full list[RecoveryOption] serialized to JSON. Stored so the
    audit trail can show every option the system considered, not just
    the winner.  Matches the customer_history JSON column pattern in
    transaction.py — variable-length nested data that doesn't need SQL
    filtering."""

    selected_action: Mapped[str] = mapped_column(String, index=True)
    """One of the TriageAction enum values. Stored as a plain string
    (not a SQL enum) matching the action column convention in
    audit_entry.py — the allow-list is enforced in Python, not in DDL,
    so adding a new action doesn't require a schema migration."""

    selected_expected_net_recovery_inr: Mapped[float] = mapped_column(Float)
    """The expected_net_recovery_inr of the winning option at decision
    time. Denormalized from options_json so aggregate queries (e.g.
    total expected recovery for a batch) don't require JSON parsing."""

    value_advantage_vs_next_best_inr: Mapped[float] = mapped_column(Float)
    """Gap between the selected option and the runner-up. Near-zero
    values signal close calls worth reviewing; large values signal
    clear winners.  Queryable as a real column so the evaluation report
    can histogram margin-of-victory distributions."""

    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    """Confidence from the reasoning path, if applicable. Null for
    deterministic-path decisions — same convention as
    audit_entry.py::confidence, and for the same reason: rendering a
    rule-based decision as 1.0 would misrepresent it as model-reasoned."""

    reasoning_text: Mapped[str] = mapped_column(String)
    """Natural-language explanation of the economic ranking. For the
    reasoning path: the model's own explanation. For the deterministic
    path: a templated sentence naming the rule and the economic
    ranking. Stored verbatim so the audit trail shows exactly what the
    system communicated."""

    decision_path: Mapped[str] = mapped_column(String)
    """'deterministic' or 'reasoning' — which path produced the triage
    decision that this economic scoring was applied to. Stored as a
    plain string matching the path_taken convention in audit_entry.py."""

    was_gated: Mapped[bool] = mapped_column(Boolean, default=False)
    """True if the confidence gate routed this decision to
    hold_for_review instead of auto-executing. Mirrors the was_gated
    field on AuditEntry."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
