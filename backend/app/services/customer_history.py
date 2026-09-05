"""
Builds the customer_history context passed to the reasoning path.

For real webhook traffic, this should query Razorpay's test-mode API for
this customer's prior transactions. For synthetic evaluation data, the
generator (scripts/generate_synthetic_data.py) builds this dict directly
and this function is not called at all — synthetic transactions already
carry their history.

TODO (Day 1): implement the real Razorpay lookup. Left as a stub
returning an empty history so the webhook pipeline is runnable end to end
before that's wired up.
"""

from app.core.logging import get_logger

logger = get_logger(__name__)


def get_customer_history(customer_id: str) -> dict:
    logger.warning(
        "get_customer_history is a stub — returning empty history for %s. "
        "See TODO in app/services/customer_history.py.",
        customer_id,
    )
    return {
        "customer_id": customer_id,
        "prior_transaction_count": 0,
        "prior_success_rate": None,
        "most_recent_decline_reason": None,
        "account_age_days": None,
    }
