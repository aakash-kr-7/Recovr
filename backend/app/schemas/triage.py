"""Pydantic schemas for a triage decision, shared between the agent
internals and the API responses the dashboard consumes."""

from enum import Enum

from pydantic import BaseModel, Field


class TriageAction(str, Enum):
    """The complete allow-list of actions the executor may take.

    This is the bound referenced throughout docs/architecture/overview.md.
    Adding a new action here is a deliberate architectural change, not a
    quick edit — any new value must be handled in
    app/agent/executor.py::execute() and app/services/razorpay_client.py.
    """

    RETRY_SAME_RAIL = "retry_same_rail"
    RETRY_ALT_RAIL = "retry_alt_rail"
    HOLD_FOR_REVIEW = "hold_for_review"
    ESCALATE_TO_DUNNING = "escalate_to_dunning"
    NO_ACTION = "no_action"


class TriagePath(str, Enum):
    DETERMINISTIC = "deterministic"
    REASONING = "reasoning"


class TriageDecision(BaseModel):
    transaction_id: str
    path_taken: TriagePath
    action: TriageAction
    reasoning_text: str
    confidence: float | None = Field(
        default=None,
        description="Only set for the reasoning path. See "
        "app/models/audit_entry.py for why this is null, not 1.0, "
        "for deterministic-path decisions.",
    )
    was_gated: bool = False
