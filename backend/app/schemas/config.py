"""Schemas for public non-secret configuration contracts."""

from pydantic import BaseModel, Field


class PublicConfigResponse(BaseModel):
    """Safe, non-secret operational configuration exposed for inspection.

    API keys, webhook secrets, provider secrets, and database connection
    strings are strictly excluded.
    """

    llm_provider: str = Field(description="Currently active LLM provider (e.g. groq)")
    batch_spend_cap_inr: float = Field(
        description="Bounded executor batch spend ceiling in INR"
    )
    min_auto_execute_confidence: float = Field(
        description="Threshold required for automated execution vs review"
    )
    max_customer_recovery_attempts: int = Field(
        description="Maximum recovery attempts per customer before gating"
    )
    has_real_razorpay_credentials: bool = Field(
        description="Whether valid test-mode Razorpay keys are configured"
    )
    has_real_groq_credentials: bool = Field(
        description="Whether a valid Groq API key is configured for the reasoning path"
    )
    razorpay_mode: str = Field(
        description="Data and execution mode: 'demo_seeded_data' or 'real_test_credentials'"
    )
    data_mode_label: str = Field(
        description="Human-readable description of current credential/data mode"
    )
    environment: str = Field(description="Current application environment")
    active_model: str = Field(
        description="Active model name used by the currently active LLM provider"
    )
    groq_model: str | None = Field(
        default=None,
        description="Configured Groq model (only present when Groq is the active provider)",
    )
    reasoning_model: str | None = Field(
        default=None,
        description="Configured Anthropic reasoning model (only present when Anthropic is the active provider)",
    )
    wasted_retry_cost_inr: float = Field(
        description="Model cost constant: wasted retry"
    )
    alternate_rail_cost_inr: float = Field(
        description="Model cost constant: alternate rail"
    )
    review_cost_inr: float = Field(description="Model cost constant: manual review")
    dunning_cost_inr: float = Field(
        description="Model cost constant: dunning collection"
    )
