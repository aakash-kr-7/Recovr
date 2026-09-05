import json
from anthropic import Anthropic
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction
from app.agent.reasoning import ReasoningResult
from app.schemas.recovery import LLMInsights

logger = get_logger(__name__)

_TRIAGE_TOOL = {
    "name": "submit_triage_decision",
    "description": "Submit the triage decision for this failed transaction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Plain-language explanation of the decision, "
                "citing specific signals from the provided context.",
            },
            "action": {
                "type": "string",
                "enum": [a.value for a in TriageAction],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "insights": {"anyOf": [{"type": "object", "properties": {"version": {"const": "v1"}, "transient_failure_probability": {"type": "number", "minimum": 0, "maximum": 1}, "alternate_rail_evidence": {"type": "number", "minimum": 0, "maximum": 1}, "review_worthiness": {"type": "number", "minimum": 0, "maximum": 1}, "interpretation_confidence": {"type": "number", "minimum": 0, "maximum": 1}, "evidence_basis": {"type": "array", "items": {"enum": ["raw_decline_text", "customer_history", "failure_time"]}}}, "required": ["version", "transient_failure_probability", "alternate_rail_evidence", "review_worthiness", "interpretation_confidence", "evidence_basis"]}, {"type": "null"}]},
        },
        "required": ["reasoning", "action", "confidence"],
    },
}

def get_triage_decision_anthropic(transaction: Transaction, system_prompt: str, user_message: str) -> ReasoningResult:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key, max_retries=settings.llm_max_retries, timeout=settings.llm_timeout_seconds)

    response = client.messages.create(
        model=settings.reasoning_model,
        max_tokens=1024,
        system=system_prompt,
        tools=[_TRIAGE_TOOL],
        tool_choice={"type": "tool", "name": "submit_triage_decision"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise ValueError(
            f"No tool_use block in Claude response for transaction "
            f"{transaction.id}. Raw response: {response.content}"
        )

    try:
        return ReasoningResult(
            action=tool_use_block.input["action"],
            reasoning_text=tool_use_block.input["reasoning"],
            confidence=tool_use_block.input["confidence"],
            insights=tool_use_block.input.get("insights"),
        )
    except (KeyError, ValidationError) as e:
        raise ValueError(
            f"Malformed triage decision from Claude for transaction "
            f"{transaction.id}: {e}"
        ) from e
