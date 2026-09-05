"""Focused tests for the real/simulated execution boundary."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.agent.executor import BatchSpendTracker, ExecutionMode, ExecutionStatus, execute
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction, TriagePath
from app.services.razorpay_client import RazorpayTestModeClient


def _transaction(synthetic=False):
    return Transaction(id="txn-loop", razorpay_payment_id="pay_loop", amount_inr=250.0,
        decline_reason="bank_timeout", decline_reason_raw="timeout", customer_id="customer-loop",
        customer_history={}, failed_at=datetime.now(timezone.utc), is_synthetic=synthetic, data_split="production")


def test_collection_link_is_the_only_real_executor_mapping():
    fake = SimpleNamespace(create_collection_link=lambda *_: {"id": "plink_loop"})
    result = execute(_transaction(), TriagePath.DETERMINISTIC, TriageAction.ESCALATE_TO_DUNNING,
        "collection request", None, BatchSpendTracker(1), [], 0, 0, client=fake)
    assert result.status is ExecutionStatus.PENDING
    assert result.mode is ExecutionMode.REAL_RAZORPAY_ACTION
    assert result.provider_reference == "plink_loop"
    assert result.action_cost_inr == 0.0


def test_provider_failure_is_a_structured_failed_result():
    fake = SimpleNamespace(create_collection_link=lambda *_: (_ for _ in ()).throw(TimeoutError("timeout")))
    result = execute(_transaction(), TriagePath.DETERMINISTIC, TriageAction.ESCALATE_TO_DUNNING,
        "collection request", None, BatchSpendTracker(1), [], 0, 0, client=fake)
    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == "razorpay_request_failed"


def test_retry_is_explicitly_bounded_simulation():
    result = execute(_transaction(), TriagePath.DETERMINISTIC, TriageAction.RETRY_SAME_RAIL,
        "not an API retry", None, BatchSpendTracker(1), [], 0, 0)
    assert result.status is ExecutionStatus.SIMULATED
    assert result.mode is ExecutionMode.BOUNDED_SIMULATION


def test_client_uses_payment_link_api_and_safe_payload():
    captured = {}
    def create(payload):
        captured["payload"] = payload
        return {"id": "plink"}
    client = RazorpayTestModeClient.__new__(RazorpayTestModeClient)
    client._client = SimpleNamespace(payment_link=SimpleNamespace(create=create))
    client.create_collection_link("pay_one", 12.34, "cust")
    assert captured["payload"]["amount"] == 1234
    assert captured["payload"]["reminder_enable"] is False
    assert captured["payload"]["notes"]["recovery_for_payment"] == "pay_one"
