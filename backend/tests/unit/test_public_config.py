"""Unit tests for the safe public config endpoint."""

from fastapi.testclient import TestClient
from app.main import app
from app.api.config import check_real_razorpay_credentials

client = TestClient(app)

FORBIDDEN_SECRET_FIELDS = [
    "razorpay_key_id",
    "razorpay_key_secret",
    "razorpay_webhook_secret",
    "anthropic_api_key",
    "groq_api_key",
    "database_url",
]


def test_public_config_endpoint_success_and_safety():
    response = client.get("/config/public")
    assert response.status_code == 200

    data = response.json()

    # Verify expected operational fields
    assert data["llm_provider"] == "groq"
    assert "batch_spend_cap_inr" in data
    assert "min_auto_execute_confidence" in data
    assert "has_real_razorpay_credentials" in data
    assert "razorpay_mode" in data
    assert "data_mode_label" in data
    assert isinstance(data["has_real_razorpay_credentials"], bool)

    # Explicitly check that no secrets are leaked
    for secret_field in FORBIDDEN_SECRET_FIELDS:
        assert secret_field not in data, f"Secret field {secret_field} leaked in /config/public!"

    # Ensure no values in the payload match sensitive patterns
    for k, v in data.items():
        assert "secret" not in k.lower() or k == "razorpay_mode"


def test_check_real_razorpay_credentials():
    assert not check_real_razorpay_credentials("dummy", "dummy")
    assert not check_real_razorpay_credentials("rzp_test_xxxx", "xxxx")
    assert not check_real_razorpay_credentials("", "")
    assert not check_real_razorpay_credentials("rzp_live_12345", "secret123")
    assert check_real_razorpay_credentials("rzp_test_valid12345", "real_secret_token_123")
