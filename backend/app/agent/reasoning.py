"""
The reasoning path: calls the LLM API with the transaction's decline
context and customer history, and parses a structured triage decision out
of the response.

See app/agent/prompts/triage_system_prompt.md for the system prompt, and
docs/decisions/0002-no-custom-model.md for why this is a direct API call
against structured context rather than a fine-tuned classifier.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from app.core.logging import get_logger
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction
from app.schemas.recovery import LLMInsights

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "triage_system_prompt.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text()


class ReasoningResult(BaseModel):
    action: TriageAction
    reasoning_text: str
    confidence: float
    insights: LLMInsights | None = None


_INSIGHT_CACHE: dict[str, ReasoningResult] = {}


def _build_user_message(transaction: Transaction) -> str:
    return json.dumps(
        {
            "decline_reason_raw": transaction.decline_reason_raw,
            "decline_reason_normalized": transaction.decline_reason,
            "amount_inr": transaction.amount_inr,
            "customer_history": transaction.customer_history,
            "failed_at": transaction.failed_at.isoformat(),
        },
        indent=2,
    )


def get_triage_decision(transaction: Transaction) -> ReasoningResult:
    """Calls the configured LLM with the transaction context and returns a parsed,
    validated ReasoningResult.

    Raises ValueError if the model's tool call output doesn't validate —
    callers should treat this as "route to hold_for_review", never as
    "retry the API call until it produces something parseable". A
    persistent validation failure is a signal worth surfacing, not
    papering over.
    """
    cached = _INSIGHT_CACHE.get(transaction.id)
    if cached is not None:
        return cached
    from app.agent.providers import get_reasoning_provider
    provider_fn = get_reasoning_provider()
    result = provider_fn(transaction, _SYSTEM_PROMPT, _build_user_message(transaction))
    _INSIGHT_CACHE[transaction.id] = result
    return result
