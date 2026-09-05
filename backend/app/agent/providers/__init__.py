from app.core.config import get_settings
from .anthropic_provider import get_triage_decision_anthropic
from .groq_provider import get_triage_decision_groq

def get_reasoning_provider():
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return get_triage_decision_anthropic
    elif settings.llm_provider == "groq":
        return get_triage_decision_groq
    else:
        raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")
