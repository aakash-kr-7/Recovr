"""Pydantic schemas for the economic decision layer.

These models capture the expected-value reasoning the system performs
*after* triage selects a path but *before* the executor acts.  They are
the data contracts between the scoring formula (next prompt), the
executor, and the dashboard/audit trail.

Three separate models on purpose:
  RecoveryOption  — one candidate action's economics (there are several)
  RecoveryDecision — the chosen action + why, referencing the full set
  RecoveryOutcome  — the measured result after execution

RecoveryDecision and RecoveryOutcome are deliberately kept apart so an
expected recovery value is never silently overwritten by a measured one.
See docs/decisions/0006-economic-decision-layer.md for the full
reasoning.
"""

from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal

from app.schemas.triage import TriageAction, TriagePath


class LLMInsights(BaseModel):
    """Versioned, context-grounded evidence; never direct probabilities."""
    version: Literal["v1"] = "v1"
    transient_failure_probability: float = Field(ge=0.0, le=1.0, description="Interpretation that raw failure text describes a temporary issuer/rail condition.")
    alternate_rail_evidence: float = Field(ge=0.0, le=1.0, description="Evidence that another known rail is more plausible than repeating the failed rail.")
    review_worthiness: float = Field(ge=0.0, le=1.0, description="Evidence that ambiguous raw context merits review rather than automatic retry.")
    interpretation_confidence: float = Field(ge=0.0, le=1.0)
    evidence_basis: list[Literal["raw_decline_text", "customer_history", "failure_time"]] = Field(min_length=1, max_length=3)


class RecoveryContext(BaseModel):
    """Pre-action, structured information available to economic scoring.

    This deliberately excludes LLM prose and every measured/hidden outcome.
    It is the complete typed boundary between transaction context and the
    deterministic probability/economic layer.
    """

    amount_inr: float
    decline_reason: str
    customer_prior_success_rate: float | None = None
    customer_account_age_days: float | None = None
    customer_most_recent_decline: str | None = None
    last_successful_rail: str | None = None
    recent_retry_count: int | None = Field(default=None, ge=0)
    failure_hour: int | None = Field(default=None, ge=0, le=23)
    llm_insights: LLMInsights | None = None


class RecoveryOption(BaseModel):
    """One candidate action evaluated by the scoring formula.

    The dashboard and audit trail display `supporting_evidence` directly,
    so it must be a human-readable sentence, not a raw JSON dump of model
    internals.
    """

    action: TriageAction
    estimated_probability: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability that this action leads to a successful "
        "recovery, as estimated by the scoring formula. Bounded 0–1 "
        "because it feeds a multiplication — an unconstrained float "
        "would silently produce nonsensical expected values.",
    )
    expected_recovery_inr: float = Field(
        description="probability × transaction amount. The gross upside "
        "if this action succeeds, ignoring cost and risk.",
    )
    action_cost_inr: float = Field(
        description="Direct cost of executing this action (e.g. a "
        "Razorpay retry fee, a dunning-email send cost). Zero is a "
        "valid value — some actions are free to attempt.",
    )
    risk_penalty_inr: float = Field(
        description="Estimated downside of a failed attempt (customer "
        "churn cost, goodwill damage). Modeled as a positive number "
        "subtracted from the net, not a negative cost, so that the "
        "formula reads naturally: net = recovery − cost − risk.",
    )
    expected_net_recovery_inr: float = Field(
        description="expected_recovery_inr − action_cost_inr − "
        "risk_penalty_inr. Stored redundantly rather than computed on "
        "read so the audit trail shows the exact number the system "
        "used at decision time, even if the formula changes later.",
    )
    supporting_evidence: str = Field(
        description="Human-readable explanation of why this option "
        "received its probability and cost estimates. This is what "
        "the dashboard and audit trail display — never a raw data dump.",
    )


class RecoveryDecision(BaseModel):
    """The system's selected action for a specific transaction, with the
    full set of options it evaluated and the reason it picked the winner.

    Maps 1-to-1 with a RecoveryDecisionRow in the ORM layer.
    """

    transaction_id: str
    options: list[RecoveryOption] = Field(
        description="Every action the scoring formula evaluated. Stored "
        "in full so the audit trail can show not just what the system "
        "chose, but what it rejected and why the winner beat them.",
    )
    selected_action: TriageAction
    selected_expected_net_recovery_inr: float = Field(
        description="The expected_net_recovery_inr of the selected "
        "option. Denormalized here so the dashboard and evaluation "
        "report can query it without unpacking the options JSON.",
    )
    value_advantage_vs_next_best_inr: float = Field(
        description="Gap between the selected option's net recovery and "
        "the second-best option's net recovery. A near-zero gap "
        "signals a close call worth flagging; a large gap signals a "
        "clear winner.",
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence from the reasoning path, if applicable. "
        "Null for deterministic-path decisions, matching the convention "
        "in app/models/audit_entry.py — rendering this as 1.0 would "
        "misrepresent a rule-based decision as model-reasoned.",
    )
    reasoning_text: str = Field(
        description="Natural-language explanation of why this action was "
        "selected. For the reasoning path: the model's own words. For "
        "the deterministic path: a templated sentence naming the rule "
        "and the economic ranking.",
    )
    decision_path: TriagePath
    was_gated: bool = Field(
        default=False,
        description="True if the confidence gate routed this decision to "
        "hold_for_review instead of auto-executing. Mirrors the "
        "was_gated field on AuditEntry / TriageDecision.",
    )


class RecoveryOutcome(BaseModel):
    """The measured result of an executed recovery action.

    Populated asynchronously — for real transactions, when Razorpay
    reports the retry result; for synthetic eval data, from the
    ground_truth_label.  All 'actual' and 'observed' fields are null
    until the outcome is known, so this model is safe to create at
    decision time and update later.
    """

    transaction_id: str
    action: TriageAction
    execution_status: str = Field(
        description="Current execution state: 'pending', 'executed', "
        "'failed_to_execute', 'skipped'. Not an enum yet because the "
        "executor may need to add states as new action types appear "
        "— constraining it now would force a schema migration for "
        "each new state.",
    )
    actual_recovered_inr: float | None = Field(
        default=None,
        description="Amount actually recovered, in INR. Null until the "
        "execution outcome is known — never zero as a placeholder, "
        "since zero is a valid recovery amount (attempted and failed).",
    )
    observed_success: bool | None = Field(
        default=None,
        description="True if the recovery action succeeded, False if it "
        "failed, None if outcome is not yet known. Kept as a separate "
        "boolean rather than inferred from actual_recovered_inr > 0, "
        "because a partial recovery can still count as a success "
        "depending on business rules.",
    )
    variance_inr: float | None = Field(
        default=None,
        description="actual_recovered_inr minus the expected recovery "
        "from the RecoveryDecision at decision time. Null until the "
        "outcome is known. Positive = better than expected, negative = "
        "worse. This is the core feedback signal for calibration.",
    )
    outcome_timestamp: datetime = Field(
        description="When the outcome was recorded. For real transactions "
        "this is the Razorpay webhook timestamp; for synthetic eval "
        "data this is the evaluation run timestamp.",
    )
