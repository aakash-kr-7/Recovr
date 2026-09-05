"""Operational configuration API routes.

Provides safe, public inspection of non-secret system settings for judges
and engineers evaluating the deployment.
"""

from fastapi import APIRouter
from app.core.config import get_settings
from app.schemas.config import PublicConfigResponse

router = APIRouter(prefix="/config", tags=["config"])


def check_real_razorpay_credentials(key_id: str, key_secret: str) -> bool:
    """Determine whether the system is configured with real Razorpay test keys

    versus placeholder / dummy / seeded data only.
    """
    kid = (key_id or "").strip()
    ksec = (key_secret or "").strip()
    if not kid.startswith("rzp_test_"):
        return False
    if "xxxx" in kid or "xxxx" in ksec:
        return False
    if kid in ("dummy", "rzp_test_placeholder") or ksec in ("dummy", ""):
        return False
    return True


@router.get("/public", response_model=PublicConfigResponse)
def get_public_config() -> PublicConfigResponse:
    """Return read-only, non-secret operational configuration.

    Guarantees secrets (razorpay_key_secret, razorpay_key_id,
    razorpay_webhook_secret, anthropic_api_key, groq_api_key, database_url)
    are strictly excluded from the response.
    """
    settings = get_settings()
    has_real_creds = check_real_razorpay_credentials(
        settings.razorpay_key_id, settings.razorpay_key_secret
    )
    mode = "real_test_credentials" if has_real_creds else "demo_seeded_data"
    mode_label = (
        "Real Razorpay test-mode credentials"
        if has_real_creds
        else "Demo / seeded data only (no live test credentials)"
    )

    return PublicConfigResponse(
        llm_provider=settings.llm_provider,
        batch_spend_cap_inr=settings.batch_spend_cap_inr,
        min_auto_execute_confidence=settings.min_auto_execute_confidence,
        max_customer_recovery_attempts=settings.max_customer_recovery_attempts,
        has_real_razorpay_credentials=has_real_creds,
        razorpay_mode=mode,
        data_mode_label=mode_label,
        environment=settings.environment,
        reasoning_model=settings.reasoning_model,
        groq_model=settings.groq_model,
        wasted_retry_cost_inr=settings.wasted_retry_cost_inr,
        alternate_rail_cost_inr=settings.alternate_rail_cost_inr,
        review_cost_inr=settings.review_cost_inr,
        dunning_cost_inr=settings.dunning_cost_inr,
    )
