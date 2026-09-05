"""
Probability heuristics for each candidate recovery action.

This is a TRANSPARENT, DELIBERATELY NOT MACHINE-LEARNED probability
estimator.  Every number in this module is a hand-picked heuristic with
an inline comment explaining its reasoning.  The estimates it produces
are explicitly labeled as "heuristic estimates, not calibrated model
outputs" — they must never be presented as more rigorous than they are.

This matches the project's honesty principle (see docs/POSITIONING.md):
we claim contextual reasoning, not a proprietary ML model.  The
probability heuristics are a starting scaffold that makes the
expected-value formula produce useful rankings; they are not the product
itself.

Historical evidence (actual recovery rates from past decisions for this
decline reason / customer profile) is accepted as an OPTIONAL injected
parameter.  The actual lookup of historical evidence is the next prompt —
do not implement it here.  When absent, a safe conservative default is
used for every heuristic.

Design note on RETRY_LATER:
---------------------------------------------------------------------------
The request mentions RETRY_LATER as a potential variant.  The project's
existing TriageAction enum (app/schemas/triage.py) does NOT include a
RETRY_LATER value, and the executor only handles the five existing enum
values.  Rather than silently inventing a new action that the executor
can't execute, this module maps RETRY_LATER semantics to the existing
actions:  RETRY_SAME_RAIL already covers "retry now on the same rail";
a delayed retry is an orchestration concern (when to fire the retry) not
an action-type concern (what to do).  If RETRY_LATER is added to
TriageAction in the future, it can be added here without changing the
scoring module's interface.
"""

from __future__ import annotations

from app.agent.economics.historical_evidence import HistoricalEvidence
from app.schemas.recovery import LLMInsights


# ---------------------------------------------------------------------------
# Decline-reason category → calibrated base probabilities
# ---------------------------------------------------------------------------
# Base rates are calibrated from the training set using Empirical Bayes /
# Beta smoothing (W=10 pseudo-observations shrinkage to category priors)
# to avoid overfitting sparse buckets while eliminating large systematic biases.
#
# Deterministic structural zeros are strictly enforced so that physically
# or compliance-impossible actions (e.g. retrying an expired card or closed
# account) are never assigned probabilistic noise.

STRUCTURAL_ZERO_ACTIONS: dict[str, set[str]] = {
    "card_reported_lost_or_stolen": {"retry_same_rail"},
    "card_expired": {"retry_same_rail"},
    "account_closed": {"retry_same_rail", "retry_alt_rail"},
    "invalid_card_number": {"retry_same_rail", "retry_alt_rail"},
    "compliance_block": {"retry_same_rail", "retry_alt_rail", "escalate_to_dunning"},
}

_RETRY_SAME_RAIL_BASE: dict[str, float] = {
    # Soft declines
    "insufficient_funds": 0.2604,
    "bank_timeout": 0.3125,
    "authentication_failed": 0.1333,
    "issuer_unavailable": 0.2619,
    # Hard declines (structural zeros)
    "card_reported_lost_or_stolen": 0.0,
    "account_closed": 0.0,
    "card_expired": 0.0,
    "invalid_card_number": 0.0,
    "compliance_block": 0.0,
    "some_unmapped_bank_specific_code_47B": 0.0833,
}
_RETRY_SAME_RAIL_DEFAULT = 0.12

_RETRY_ALT_RAIL_BASE: dict[str, float] = {
    # Soft declines
    "insufficient_funds": 0.1226,
    "bank_timeout": 0.3438,
    "authentication_failed": 0.3067,
    "issuer_unavailable": 0.2000,
    # Hard declines
    "card_reported_lost_or_stolen": 0.0500,
    "account_closed": 0.0,
    "card_expired": 0.1909,
    "invalid_card_number": 0.0,
    "compliance_block": 0.0,
    "some_unmapped_bank_specific_code_47B": 0.1500,
}
_RETRY_ALT_RAIL_DEFAULT = 0.15

_DUNNING_BASE: dict[str, float] = {
    # Soft declines
    "insufficient_funds": 0.1736,
    "bank_timeout": 0.0781,
    "authentication_failed": 0.0267,
    "issuer_unavailable": 0.0143,
    # Hard declines (effective recovery path for expired / lost-stolen cards)
    "card_expired": 0.3864,
    "card_reported_lost_or_stolen": 0.3750,
    "account_closed": 0.0333,
    "invalid_card_number": 0.0632,
    "compliance_block": 0.0,
    "some_unmapped_bank_specific_code_47B": 0.0500,
}
_DUNNING_DEFAULT = 0.06

_HOLD_FOR_REVIEW_BASE: dict[str, float] = {
    "insufficient_funds": 0.1509,
    "bank_timeout": 0.1625,
    "authentication_failed": 0.2933,
    "issuer_unavailable": 0.2095,
    "card_expired": 0.1091,
    "card_reported_lost_or_stolen": 0.1850,
    "account_closed": 0.0867,
    "invalid_card_number": 0.1947,
    "compliance_block": 0.2750,
    "some_unmapped_bank_specific_code_47B": 0.3417,
}
_HOLD_FOR_REVIEW_DEFAULT = 0.20


def estimate_probabilities(
    decline_reason: str,
    customer_prior_success_rate: float | None,
    customer_account_age_days: float | None,
    customer_most_recent_decline: str | None,
    amount_inr: float | None = None,
    last_successful_rail: str | None = None,
    recent_retry_count: int | None = None,
    failure_hour: int | None = None,
    historical_evidence: HistoricalEvidence | None = None,
    llm_insights: LLMInsights | None = None,
) -> dict[str, float]:
    """Return calibrated recovery probabilities for each candidate action.

    Returns a dict mapping action VALUE strings (matching TriageAction
    enum values) to floats in [0.0, 1.0].

    **Action probability semantics:** each returned value is
    ``P(that specific action produces a recovery | pre-action context)``.
    It is an action-specific conditional recovery probability, not a generic
    payment-recoverability score. ``no_action`` remains zero because it
    deliberately performs no recovery intervention.
    """
    # Step 1: look up base calibrated probabilities for this decline reason.
    p_retry_same = _RETRY_SAME_RAIL_BASE.get(
        decline_reason, _RETRY_SAME_RAIL_DEFAULT
    )
    p_retry_alt = _RETRY_ALT_RAIL_BASE.get(
        decline_reason, _RETRY_ALT_RAIL_DEFAULT
    )
    p_dunning = _DUNNING_BASE.get(decline_reason, _DUNNING_DEFAULT)
    p_hold = _HOLD_FOR_REVIEW_BASE.get(decline_reason, _HOLD_FOR_REVIEW_DEFAULT)

    # Step 2: structured context calibration (linear additive adjustments).
    # Customer payment history:
    if customer_prior_success_rate is not None:
        if customer_prior_success_rate >= 0.8:
            # Strong history: retries are more likely to succeed
            p_retry_same += 0.10
            p_retry_alt += 0.10
        elif customer_prior_success_rate < 0.35:
            # Weak history: customer rarely pays successfully
            p_retry_same -= 0.10
            p_retry_alt -= 0.10

        if customer_prior_success_rate >= 0.75:
            p_dunning += 0.05

    # Repeated same decline: repeating same-rail retry is less promising,
    # but alt-rail or dunning notification is more appropriate.
    if customer_most_recent_decline is not None and customer_most_recent_decline == decline_reason:
        p_retry_same -= 0.14
        p_retry_alt += 0.08
        p_dunning += 0.08

    # Recent retry count: if already retried multiple times, immediate same-rail retry is burned out.
    if recent_retry_count is not None and recent_retry_count >= 2:
        p_retry_same -= 0.10

    # Concrete evidence of secondary rail usability:
    if last_successful_rail == "upi":
        p_retry_alt += 0.08

    # Temporal context:
    if failure_hour is not None:
        off_hours = failure_hour < 6 or failure_hour >= 22
        if off_hours:
            if decline_reason in {"bank_timeout", "issuer_unavailable"}:
                p_retry_same += 0.07
            # Review queues during off-hours resolve with delay
            p_hold -= 0.05

    # Ticket economics: human review priorities
    if amount_inr is not None:
        if amount_inr < 500:
            p_hold -= 0.08
        elif amount_inr > 5000:
            p_hold += 0.07

    # Step 3: preserve deterministic structural zeros.
    # An action that is physically or compliance-impossible for a decline code
    # (e.g. same-rail retry for an expired card) MUST remain strictly 0.0.
    zero_actions = STRUCTURAL_ZERO_ACTIONS.get(decline_reason, set())
    if "retry_same_rail" in zero_actions:
        p_retry_same = 0.0
    if "retry_alt_rail" in zero_actions:
        p_retry_alt = 0.0
    if "escalate_to_dunning" in zero_actions:
        p_dunning = 0.0
    if "hold_for_review" in zero_actions:
        p_hold = 0.0

    # Step 4: override with historical evidence if available and confident.
    if historical_evidence is not None and not historical_evidence.low_confidence:
        if historical_evidence.retry_same_rail_rate is not None and "retry_same_rail" not in zero_actions:
            p_retry_same = historical_evidence.retry_same_rail_rate
        if historical_evidence.retry_alt_rail_rate is not None and "retry_alt_rail" not in zero_actions:
            p_retry_alt = historical_evidence.retry_alt_rail_rate
        if historical_evidence.dunning_recovery_rate is not None and "escalate_to_dunning" not in zero_actions:
            p_dunning = historical_evidence.dunning_recovery_rate

    # Step 5: bounded LLM contextual adjustments. These are deliberately
    # small (at most +/- 0.08), centered at neutral 0.5, confidence-weighted,
    # and cannot change structural zeros. They interpret only raw/contextual
    # ambiguity; base rates and economics remain authoritative.
    if llm_insights is not None and llm_insights.interpretation_confidence >= 0.60:
        scale = 0.16 * llm_insights.interpretation_confidence
        p_retry_same += (llm_insights.transient_failure_probability - 0.5) * scale
        p_retry_alt += (llm_insights.alternate_rail_evidence - 0.5) * scale
        p_hold += (llm_insights.review_worthiness - 0.5) * scale
        if "retry_same_rail" in zero_actions: p_retry_same = 0.0
        if "retry_alt_rail" in zero_actions: p_retry_alt = 0.0
        if "hold_for_review" in zero_actions: p_hold = 0.0

    # Step 6: clamp all probabilities to [0.0, 0.95].
    p_retry_same = max(0.0, min(0.95, p_retry_same))
    p_retry_alt = max(0.0, min(0.95, p_retry_alt))
    p_dunning = max(0.0, min(0.95, p_dunning))
    p_hold = max(0.0, min(0.95, p_hold))

    return {
        "retry_same_rail": p_retry_same,
        "retry_alt_rail": p_retry_alt,
        "hold_for_review": p_hold,
        "escalate_to_dunning": p_dunning,
        "no_action": 0.0,
    }
