"""Unit tests for app/agent/gate.py — the fast-path/reasoning-path split.

These tests don't need a database or API keys; they exercise the routing
logic in isolation, which is exactly what a unit test for a gate should
do.
"""

from datetime import datetime, timezone

from app.agent.gate import route
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction, TriagePath


def _make_transaction(decline_reason: str) -> Transaction:
    return Transaction(
        id="test-txn-1",
        amount_inr=1000.0,
        decline_reason=decline_reason,
        decline_reason_raw=decline_reason,
        customer_id="test-customer",
        customer_history={},
        failed_at=datetime.now(timezone.utc),
        is_synthetic=True,
    )


def test_unambiguous_code_routes_to_deterministic_path():
    txn = _make_transaction("card_reported_lost_or_stolen")
    decision = route(txn)
    assert decision.path == TriagePath.DETERMINISTIC
    assert decision.fast_path_action == TriageAction.ESCALATE_TO_DUNNING
    assert decision.fast_path_reasoning is not None


def test_context_dependent_code_routes_to_reasoning_path():
    txn = _make_transaction("insufficient_funds")
    decision = route(txn)
    assert decision.path == TriagePath.REASONING
    assert decision.fast_path_action is None


def test_unrecognized_code_routes_to_reasoning_path():
    """A decline reason the fast-path table has never seen must fall
    through to the reasoning path, never to a silent default action. This
    is the specific claim made in docs/POSITIONING.md, item #2."""
    txn = _make_transaction("some_totally_novel_bank_specific_code_xyz")
    decision = route(txn)
    assert decision.path == TriagePath.REASONING
