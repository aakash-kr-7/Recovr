"""
ORM model for an incoming failed transaction.

Populated either by a real Razorpay test-mode webhook
(app/api/webhooks.py) or by the synthetic data generator
(scripts/generate_synthetic_data.py) — same schema either way, so the
triage pipeline never needs to know which source produced a given row.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    razorpay_payment_id: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    amount_inr: Mapped[float] = mapped_column(Float)
    decline_reason: Mapped[str] = mapped_column(String, index=True)
    decline_reason_raw: Mapped[str] = mapped_column(String)
    """Verbatim decline text as received. Kept separate from
    `decline_reason` (the normalized/mapped version) so the reasoning path
    can be given the raw text even when it doesn't match any known
    taxonomy entry — see decline_taxonomy.py for why this matters."""

    customer_id: Mapped[str] = mapped_column(String, index=True)
    customer_history: Mapped[dict] = mapped_column(JSON)
    """Serialized summary of this customer's prior transactions: count,
    success rate, most recent decline (if any), account age in days. Built
    by app/services/customer_history.py from either real Razorpay data or
    synthetic generation."""

    failed_at: Mapped[datetime] = mapped_column(DateTime)
    is_synthetic: Mapped[bool] = mapped_column(default=False)
    """True for synthetic/eval-generated rows, False for rows from a real
    webhook. Kept so the dashboard can clearly label demo data as demo
    data — never blur synthetic and real transactions together silently."""

    ground_truth_label: Mapped[str] = mapped_column(String, nullable=True)
    """Only populated for synthetic evaluation data. The action a careful
    human labeler assigned independently of the system's own output. Never
    populated for real transactions — there is no ground truth for a real
    payment until time has passed and we know what actually happened."""

    data_split: Mapped[str] = mapped_column(String, default="production", index=True)
    """Dataset partition this transaction belongs to:
    - 'working': synthetic development / training data used for rule tuning
      and available for historical evidence lookups.
    - 'holdout': synthetic evaluation data that must NEVER be queried or seen
      by the agent outside evaluation scripts.
    - 'production': live transactions from real webhook traffic.
    Indexed so historical evidence lookups can filter out 'holdout' directly
    at the database query level rather than relying on application convention."""
