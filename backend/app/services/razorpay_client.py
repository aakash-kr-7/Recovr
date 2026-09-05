"""
Thin wrapper around the official `razorpay` Python SDK, scoped to
test-mode operations this project needs: creating a retry attempt on an
existing order, and fetching payment status.

Deliberately thin — this is not meant to be a general-purpose Razorpay
client. It exposes exactly the operations app/agent/executor.py needs and
nothing else, so it's obvious from this file alone what money-moving
capability this project actually has.

SAFETY: this client must only ever be constructed with test-mode keys
(rzp_test_... key IDs). There is no code-level enforcement of this beyond
the .env.example warning — do not add production key support to this
class as part of this project.
"""

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RazorpayTestModeClient:
    def __init__(self) -> None:
        # Import lazily so the application can still receive and safely hold
        # webhooks when the optional provider SDK is not installed.
        import razorpay
        settings = get_settings()
        if not settings.razorpay_key_id.startswith("rzp_test_"):
            raise RuntimeError(
                "Refusing to initialize: RAZORPAY_KEY_ID does not look like "
                "a test-mode key (expected prefix 'rzp_test_'). This "
                "project must never run against live Razorpay keys."
            )
        self._client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )

    def fetch_payment(self, payment_id: str) -> dict:
        return self._client.payment.fetch(payment_id)

    def create_collection_link(self, original_payment_id: str, amount_inr: float, customer_id: str) -> dict:
        """Create a standard Payment Link: an issued collection request.

        Payments cannot retry or collect a failed payment in place. Customer
        notifications are disabled; this client has no arbitrary messaging.
        """
        amount_paise = int(round(amount_inr * 100))
        return self._client.payment_link.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "reference_id": f"recovr-{original_payment_id}"[:40],
                "description": "RECOVR recovery collection request",
                "reminder_enable": False,
                "notes": {"recovery_for_payment": original_payment_id, "customer_id": customer_id},
            }
        )
