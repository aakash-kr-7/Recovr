import json
from groq import Groq
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.transaction import Transaction
from app.schemas.triage import TriageAction
from app.agent.reasoning import ReasoningResult

logger = get_logger(__name__)

def get_triage_decision_groq(transaction: Transaction, system_prompt: str, user_message: str) -> ReasoningResult:
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key, max_retries=settings.llm_max_retries, timeout=settings.llm_timeout_seconds)

    import re
    # The available models on this restricted API key do not support native
    # tool calling robustly, so we append JSON instructions to the system prompt
    # and use JSON mode instead.
    json_instructions = (
        "\n\nYou MUST return your decision as a raw JSON object with exactly three fields:\n"
        "- 'action': a string (must be one of: 'retry_same_rail', 'retry_alt_rail', "
        "'hold_for_review', 'escalate_to_dunning', 'no_action')\n"
        "- 'reasoning': a string explaining your decision\n"
        "- 'confidence': a float between 0.0 and 1.0\n"
        "- optional 'insights': object with version 'v1', transient_failure_probability, alternate_rail_evidence, review_worthiness, interpretation_confidence (all 0..1), and evidence_basis containing only raw_decline_text, customer_history, failure_time. Use null when evidence is weak.\n"
        "Output ONLY valid JSON. Do not include markdown code blocks, backticks, or any other text."
    )

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt + json_instructions},
            {"role": "user", "content": user_message}
        ],
        max_tokens=250,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"Empty response from Groq for transaction {transaction.id}")
    
    # Strip markdown if the model hallucinates it despite instructions
    match = re.search(r'\{.*\}', content.strip(), re.DOTALL)
    if match:
        content = match.group(0)

    try:
        args = json.loads(content)
        return ReasoningResult(
            action=args["action"],
            reasoning_text=args["reasoning"],
            confidence=args["confidence"],
            insights=args.get("insights"),
        )
    except (KeyError, ValueError, ValidationError) as e:
        raise ValueError(
            f"Malformed triage decision from Groq for transaction "
            f"{transaction.id}: {e}\nContent: {content}"
        ) from e
