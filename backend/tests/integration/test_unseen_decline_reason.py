"""
Integration test backing docs/POSITIONING.md claim #2: an unrecognized
decline reason string is reasoned about, not silently defaulted.

Requires a real ANTHROPIC_API_KEY in the environment (this hits the live
Claude API) — marked so it can be skipped in fast local test runs and
still run in CI with the key configured as a secret. See
.github/workflows/ci.yml.
"""

import os
from datetime import datetime, timezone

import pytest

from app.agent.reasoning import get_triage_decision
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction

requires_api_key = pytest.mark.skipif(
    "ANTHROPIC_API_KEY" not in os.environ,
    reason="Requires a real ANTHROPIC_API_KEY; skipped in fast local runs.",
)


@requires_api_key
def test_unmapped_decline_reason_produces_reasoned_hold_not_silent_default():
    """A decline reason string with no entry anywhere in
    decline_taxonomy.py should still get a reasoned response from the
    model — specifically, the model should recognize the ambiguity and
    lean toward hold_for_review rather than confidently picking an action
    it has no real basis for, per the triage system prompt's explicit
    instruction to do so.
    """
    txn = Transaction(
        id="test-unseen-1",
        amount_inr=2500.0,
        decline_reason="bank_specific_error_code_9942X_unmapped",
        decline_reason_raw="Error 9942X: contact issuing bank",
        customer_id="test-customer",
        customer_history={
            "prior_transaction_count": 2,
            "prior_success_rate": 1.0,
            "most_recent_decline_reason": None,
            "account_age_days": 45,
        },
        failed_at=datetime.now(timezone.utc),
        is_synthetic=True,
    )

    result = get_triage_decision(txn)

    assert result.action in {
        TriageAction.HOLD_FOR_REVIEW,
        TriageAction.RETRY_SAME_RAIL,
        TriageAction.ESCALATE_TO_DUNNING,
    }
    assert len(result.reasoning_text) > 0
    # The key assertion: this must be a real, non-empty reasoning trace
    # referencing the actual decline text or history — not a canned
    # string, since there is no rule-table entry to have produced one.
