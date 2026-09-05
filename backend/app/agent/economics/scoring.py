"""
Economic scoring engine: pure-function layer that ranks candidate
recovery actions by expected net recovery.

This module does NOT call Claude/Groq and does NOT touch the database.
It is a pure function layer, deliberately, so it can be unit-tested in
complete isolation — following the same testing philosophy as
app/agent/executor.py (see tests/unit/test_executor.py).

How it works:
  1. For each permitted TriageAction, compute a RecoveryOption with:
       expected_recovery = probability × amount × recovery_fraction
       net = expected_recovery − cost − risk_penalty
  2. Select the option with the highest expected_net_recovery_inr.
  3. Compute value_advantage_vs_next_best_inr (margin of victory).
  4. Return a RecoveryDecision (with decision_path, was_gated,
     confidence, reasoning_text left unpopulated for the caller to fill,
     since this module doesn't know which triage path invoked it).

Critical design property — cost/risk can change the winner:
--------------------------------------------------------------------------
An action with a HIGHER raw probability can lose to an action with a
LOWER raw probability because of cost/risk.

Example:  RETRY_SAME_RAIL has p=0.30 for a ₹50 transaction.
  expected_recovery = 0.30 × 50 = ₹15
  cost = ₹8 (wasted_retry_cost_inr from config)
  risk = ₹5 (conservative penalty for repeated-decline pattern)
  net = 15 − 8 − 5 = ₹2

HOLD_FOR_REVIEW has an independently estimated human-workflow recovery
probability and a review cost.

Here retry still barely wins.  But add a second risk factor (e.g. the
customer has a compliance-adjacent decline pattern, bumping risk to ₹10):
  net = 15 − 8 − 10 = −₹3

Now review can beat RETRY_SAME_RAIL because cost and risk still matter.
"""

from __future__ import annotations

from app.agent.economics.probability_heuristics import (
    HistoricalEvidence,
    estimate_probabilities,
)
from app.core.config import get_settings
from app.schemas.recovery import RecoveryContext, RecoveryDecision, RecoveryOption
from app.schemas.triage import TriageAction, TriagePath


# ---------------------------------------------------------------------------
# Recovery fraction constants
# ---------------------------------------------------------------------------
# On success, not every action recovers the full transaction amount.
# While direct automated payment retries capture the full transaction amount
# (1.00), manual review and automated dunning nudges frequently result in partial
# recovery (e.g., negotiated settlements, fee concessions, or partial payments).
#
# Empirical sourcing from training data (backend/data/synthetic/transactions.json, N=140):
#   - retry_same_rail: 1.0000 observed recovery fraction (N=140, 25 realized recoveries).
#     A successful direct retry recovers the full principal charge amount (100%).
#   - retry_alt_rail: 1.0000 domain constant per specification (a successful payment retry
#     on an alternate rail recovers the full transaction amount).
#   - hold_for_review: 0.9000 observed recovery fraction (N=140, 28 realized recoveries).
#     Empirically, every successful manual review resolution yields 90% of the principal amount
#     due to manual dispute resolution, customer concessions, or partial payment arrangements.
#   - escalate_to_dunning: 0.8200 observed recovery fraction (N=140, 23 realized recoveries).
#     Empirically, every successful dunning case recovers 82% of the principal amount,
#     reflecting delayed collection discounts, partial plan updates, and collection costs.
#   - no_action: 0.0000 (no intervention taken).

_RECOVERY_FRACTION: dict[TriageAction, float] = {
    TriageAction.RETRY_SAME_RAIL: 1.00,
    TriageAction.RETRY_ALT_RAIL: 1.00,
    TriageAction.HOLD_FOR_REVIEW: 0.90,
    TriageAction.ESCALATE_TO_DUNNING: 0.82,
    TriageAction.NO_ACTION: 0.0,
}


# ---------------------------------------------------------------------------
# Action cost constants
# ---------------------------------------------------------------------------
# Retry actions have a real cost: the gateway processing fee for a wasted
# attempt.  Sourced from the EXISTING settings.wasted_retry_cost_inr in
# app/core/config.py — we do NOT invent a new constant.
#
# Non-retry actions (hold, escalate, no_action) have zero direct cost.
# Dunning has a small cost (email/SMS send) but it's negligible compared
# to retry fees, so we set it to 0 and note why.

def _action_cost_inr(action: TriageAction) -> float:
    """Direct cost of executing this action, in INR.

    Uses the existing wasted_retry_cost_inr from settings for retry
    actions.  Other actions are free — documented per-action below.
    """
    settings = get_settings()

    if action == TriageAction.RETRY_SAME_RAIL:
        # Gateway processing fee + card-network penalty risk for a
        # wasted retry.  This is the figure from config.py.
        return settings.wasted_retry_cost_inr

    if action == TriageAction.RETRY_ALT_RAIL:
        return settings.alternate_rail_cost_inr

    if action == TriageAction.ESCALATE_TO_DUNNING:
        return settings.dunning_cost_inr

    if action == TriageAction.HOLD_FOR_REVIEW:
        return settings.review_cost_inr

    # NO_ACTION costs nothing to execute.
    return 0.0


# ---------------------------------------------------------------------------
# Risk penalty heuristics
# ---------------------------------------------------------------------------
# These penalize actions that carry compliance or customer-relationship
# risk if the action turns out to be wrong.  The penalty is subtracted
# from expected net recovery, so a risky action needs to have a
# correspondingly higher expected recovery to be selected.
#
# If we cannot honestly justify a non-zero penalty for an action, we
# set it to 0 and say so in a comment.

def _risk_penalty_inr(
    action: TriageAction,
    decline_reason: str,
    customer_prior_success_rate: float | None,
) -> float:
    """Estimate the downside risk, in INR, of a wrong action.

    This is a conservative heuristic, not a calibrated model.  Each
    non-zero penalty is explained inline.
    """

    # HOLD_FOR_REVIEW: no risk — holding preserves optionality, it
    # cannot make anything worse.
    if action == TriageAction.HOLD_FOR_REVIEW:
        return 0.0

    # NO_ACTION: no risk — we're explicitly choosing not to act.
    if action == TriageAction.NO_ACTION:
        return 0.0

    # ESCALATE_TO_DUNNING: very low risk.  The worst case is an
    # unnecessary email/SMS to a customer, which is mildly annoying
    # but not harmful.  Penalty: ₹0.  We cannot honestly justify a
    # non-zero number here.
    if action == TriageAction.ESCALATE_TO_DUNNING:
        return 0.0

    # RETRY_SAME_RAIL and RETRY_ALT_RAIL carry real risk:
    penalty = 0.0

    # Risk 1: compliance-adjacent pattern.  If the decline reason is
    # compliance_block or card_reported_lost_or_stolen, retrying is
    # actively dangerous — it could trigger card-network penalties
    # and is potentially a compliance violation.
    compliance_adjacent = {
        "compliance_block",
        "card_reported_lost_or_stolen",
    }
    if decline_reason in compliance_adjacent:
        # Heavy penalty: ₹50.  This should make retry lose to hold
        # for any reasonable transaction amount, which is the correct
        # behavior — a compliance-adjacent retry should never win on
        # economics alone.
        penalty += 50.0

    # Risk 2: customer with poor payment history + immediate retry.
    # Retrying aggressively for a customer who rarely pays
    # successfully risks burning goodwill with someone who may be in
    # financial distress.
    if customer_prior_success_rate is not None and customer_prior_success_rate < 0.3:
        # Moderate penalty: ₹5.  Enough to tip the balance against
        # retry for small transactions where the expected recovery is
        # marginal.
        penalty += 5.0

    # Risk 3: expired card retry — retrying on the same card that
    # already failed because it's expired wastes a retry attempt and
    # potentially annoys the customer with a duplicate failure
    # notification.
    if decline_reason == "card_expired" and action == TriageAction.RETRY_SAME_RAIL:
        # Same-rail retry on an expired card is almost certainly
        # wasted.  Penalty to push toward alt-rail or dunning.
        penalty += 15.0

    return penalty


def _build_evidence(
    action: TriageAction,
    decline_reason: str,
    probability: float,
    cost: float,
    risk: float,
    historical_evidence: HistoricalEvidence | None = None,
) -> str:
    """Build a human-readable supporting_evidence string.

    This is what the dashboard and audit trail display — it must be a
    sentence a human can read, not a raw data dump.
    """
    action_label = action.value.replace("_", " ").title()

    if probability == 0.0:
        base = (
            f"{action_label}: no recovery probability (this action does "
            f"not attempt recovery). Cost ₹{cost:.2f}, risk ₹{risk:.2f}."
        )
    else:
        parts = [
            f"{action_label}: estimated {probability:.0%} chance of recovery.",
        ]
        if cost > 0:
            parts.append(f"Direct cost: ₹{cost:.2f}.")
        if risk > 0:
            parts.append(f"Risk penalty: ₹{risk:.2f} ({decline_reason}).")
        base = " ".join(parts)

    if (
        historical_evidence is not None
        and not historical_evidence.low_confidence
        and historical_evidence.summary
    ):
        return f"{historical_evidence.summary}. {base}"

    return base


def score_recovery_options(
    transaction_id: str,
    amount_inr: float | None = None,
    decline_reason: str | None = None,
    customer_prior_success_rate: float | None = None,
    customer_account_age_days: float | None = None,
    customer_most_recent_decline: str | None = None,
    permitted_actions: list[TriageAction] | None = None,
    historical_evidence: HistoricalEvidence | None = None,
    context: RecoveryContext | None = None,
) -> RecoveryDecision:
    """Score each permitted action and return a RecoveryDecision.

    This is the main entry point for the economic scoring layer.

    Parameters
    ----------
    transaction_id : str
        The transaction being scored.
    amount_inr : float
        Transaction amount in INR.
    decline_reason : str
        Normalized decline reason string.
    customer_prior_success_rate : float | None
        From customer_history on Transaction.  None if unknown.
    customer_account_age_days : float | None
        From customer_history on Transaction.  None if unknown.
    customer_most_recent_decline : str | None
        From customer_history on Transaction.  None if unknown.
    permitted_actions : list[TriageAction]
        Only these actions will be scored.  An action NOT in this list
        will never appear in the output — not just "not selected", but
        absent entirely.  This is enforced by construction (we iterate
        over permitted_actions only), not by a post-filter.
    historical_evidence : HistoricalEvidence | None
        Optional externally-sourced recovery rates.  When absent, all
        probabilities come from the hand-picked heuristics.

    Returns
    -------
    RecoveryDecision
        With decision_path, was_gated, confidence, and reasoning_text
        set to placeholder defaults.  The caller (executor integration,
        next prompt) fills these in based on which triage path is active.

    Example where cost/risk changes the winner
    -------------------------------------------
    RETRY_SAME_RAIL has p=0.30, amount=₹40:
      expected_recovery = 0.30 × 40 = ₹12
      cost = ₹8, risk = ₹5
      net = 12 − 8 − 5 = −₹1

    HOLD_FOR_REVIEW has a separately estimated human-workflow probability
    and review cost, so it can win when its expected net exceeds retry.
    """
    if context is not None:
        amount_inr = context.amount_inr
        decline_reason = context.decline_reason
        customer_prior_success_rate = context.customer_prior_success_rate
        customer_account_age_days = context.customer_account_age_days
        customer_most_recent_decline = context.customer_most_recent_decline
    if amount_inr is None or decline_reason is None or not permitted_actions:
        raise ValueError(
            "permitted_actions must not be empty — the executor must "
            "always have at least one action to choose from."
        )

    # Get probability estimates for all actions.
    probabilities = estimate_probabilities(
        decline_reason=decline_reason,
        customer_prior_success_rate=customer_prior_success_rate,
        customer_account_age_days=customer_account_age_days,
        customer_most_recent_decline=customer_most_recent_decline,
        amount_inr=amount_inr,
        last_successful_rail=context.last_successful_rail if context else None,
        recent_retry_count=context.recent_retry_count if context else None,
        failure_hour=context.failure_hour if context else None,
        historical_evidence=historical_evidence,
        llm_insights=context.llm_insights if context else None,
    )

    # Build a RecoveryOption for each PERMITTED action only.
    options: list[RecoveryOption] = []
    for action in permitted_actions:
        prob = probabilities.get(action.value, 0.0)
        cost = _action_cost_inr(action)
        risk = _risk_penalty_inr(
            action=action,
            decline_reason=decline_reason,
            customer_prior_success_rate=customer_prior_success_rate,
        )
        fraction = _RECOVERY_FRACTION.get(action, 1.0)
        expected_recovery = prob * amount_inr * fraction
        net = expected_recovery - cost - risk
        evidence = _build_evidence(
            action=action,
            decline_reason=decline_reason,
            probability=prob,
            cost=cost,
            risk=risk,
            historical_evidence=historical_evidence,
        )

        options.append(
            RecoveryOption(
                action=action,
                estimated_probability=prob,
                expected_recovery_inr=expected_recovery,
                action_cost_inr=cost,
                risk_penalty_inr=risk,
                expected_net_recovery_inr=net,
                supporting_evidence=evidence,
            )
        )

    # Sort by expected_net_recovery_inr descending to find the winner.
    options.sort(key=lambda o: o.expected_net_recovery_inr, reverse=True)

    selected = options[0]

    # Value advantage: gap between the winner and the second-best.
    # If there's only one permitted action, the advantage is the
    # winner's own net (it beats "nothing" by its full value).
    if len(options) >= 2:
        value_advantage = (
            selected.expected_net_recovery_inr
            - options[1].expected_net_recovery_inr
        )
    else:
        value_advantage = selected.expected_net_recovery_inr

    return RecoveryDecision(
        transaction_id=transaction_id,
        options=options,
        selected_action=selected.action,
        selected_expected_net_recovery_inr=selected.expected_net_recovery_inr,
        value_advantage_vs_next_best_inr=value_advantage,
        # --- Fields left for the caller to fill ---
        # The scoring module doesn't know which path (deterministic or
        # reasoning) invoked it, so these are set to safe defaults.
        confidence=None,
        reasoning_text=(
            f"Economic scoring selected {selected.action.value} with "
            f"expected net recovery ₹{selected.expected_net_recovery_inr:.2f}."
        ),
        decision_path=TriagePath.DETERMINISTIC,  # placeholder — caller overrides
        was_gated=False,  # placeholder — caller overrides
    )
