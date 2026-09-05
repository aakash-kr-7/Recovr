"""
Pydantic schema for the subset of a Razorpay `payment.failed` webhook
payload this project actually uses.

NOTE: this is written against Razorpay's publicly documented webhook
payload shape as a starting point. Confirm field names against a real
captured payload during Day 1 setup (see backend/README.md) and adjust —
webhook payload shapes are exactly the kind of detail that should come
from the real API, not from this scaffold. Treat the fields below as a
best-effort starting point, not a verified contract.
"""

from pydantic import BaseModel


class RazorpayPaymentEntity(BaseModel):
    id: str
    amount: int  # paise, per Razorpay convention — convert to INR on ingest
    currency: str
    status: str
    error_code: str | None = None
    error_description: str | None = None
    contact: str | None = None
    email: str | None = None
    created_at: int  # unix timestamp


class RazorpayWebhookPayload(BaseModel):
    event: str
    payload: dict
    """Kept as a raw dict at this level; the nested `payment.entity`
    structure is extracted in app/api/webhooks.py using
    RazorpayPaymentEntity, rather than modeled fully here, since only a
    subset of the full webhook envelope is relevant to triage."""
