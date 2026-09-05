"""
Application settings, loaded from environment variables (see .env.example).

Cost and threshold constants below are deliberately kept here, next to a
citation or a stated rationale, rather than scattered as magic numbers
through the codebase. See docs/decisions/0004-baseline-sourcing.md for the
sourcing policy this file follows.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Razorpay (TEST MODE ONLY) ---
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str

    # --- Claude API ---
    anthropic_api_key: str
    # Model used for the reasoning path. Pin a specific version so eval
    # results are reproducible; update deliberately, not silently.
    reasoning_model: str = "claude-sonnet-4-5"

    # --- Groq API ---
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.6-27b"
    llm_max_retries: int = 2
    llm_timeout_seconds: float = 15.0

    # --- Database ---
    database_url: str = "sqlite:///./app.db"

    # --- Cost constants ---
    # Estimated cost, in INR, of a single wasted retry attempt: gateway
    # processing fee plus a conservative allowance for card-network
    # penalty risk on excessive retries. This is a deliberately
    # conservative placeholder — replace with a better-sourced figure if
    # one is found before submission, and update
    # docs/decisions/0004-baseline-sourcing.md when you do.
    wasted_retry_cost_inr: float = 8.0
    alternate_rail_cost_inr: float = 10.0
    review_cost_inr: float = 6.0
    dunning_cost_inr: float = 4.0

    # --- Bounded executor ---
    # Hard ceiling on total ₹ the executor may act on in a single
    # evaluation batch run. This exists so a reasoning-path bug cannot
    # cause runaway action-taking even in a demo/test-mode context.
    batch_spend_cap_inr: float = 50_000.0

    # Reasoning-path outputs below this confidence are routed to
    # hold_for_review rather than auto-executed. See
    # docs/architecture/overview.md, "bounded action executor".
    min_auto_execute_confidence: float = 0.75
    max_customer_recovery_attempts: int = 2

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Import this, not Settings() directly,
    so the whole app shares one parsed config."""
    return Settings()
