"""
Builds the customer_history context passed to the reasoning path.

LIMITATION: We cannot use Razorpay's test-mode customer API as the primary source 
because it does not track our internal `recovery_outcome` states (like prior_success_rate 
based on our internal recovery actions). Querying it for this data is not supported 
by their API. Therefore, we use the local DB query as the sole source.
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.models.transaction import Transaction
from app.models.recovery_outcome import RecoveryOutcomeRow

logger = get_logger(__name__)


def get_customer_history(db: Session, customer_id: str) -> dict:
    stmt = (
        select(Transaction, RecoveryOutcomeRow)
        .outerjoin(RecoveryOutcomeRow, RecoveryOutcomeRow.transaction_id == Transaction.id)
        .where(Transaction.customer_id == customer_id)
        .order_by(Transaction.failed_at.desc())
    )
    rows = db.execute(stmt).all()
    
    prior_transaction_count = len(set(txn.id for txn, _ in rows))
    
    outcomes = [outcome for _, outcome in rows if outcome is not None and outcome.observed_success is not None]
    if outcomes:
        successes = sum(1 for o in outcomes if o.observed_success)
        prior_success_rate = successes / len(outcomes)
    else:
        prior_success_rate = None
        
    most_recent_decline_reason = rows[0][0].decline_reason if rows else None
    
    if rows:
        earliest_txn = rows[-1][0]
        account_age_days = (datetime.utcnow() - earliest_txn.failed_at).days
    else:
        account_age_days = None
        
    return {
        "customer_id": customer_id,
        "prior_transaction_count": prior_transaction_count,
        "prior_success_rate": prior_success_rate,
        "most_recent_decline_reason": most_recent_decline_reason,
        "account_age_days": account_age_days,
    }
