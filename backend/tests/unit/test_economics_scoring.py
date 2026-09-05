"""Unit tests for the economic scoring engine.

Follows the same testing philosophy as tests/unit/test_executor.py:
no database fixture, no API calls, no external dependencies. The
scoring module is a pure function layer — these tests verify its
decision logic in complete isolation.
"""

from app.agent.economics.scoring import score_recovery_options
from app.agent.economics.historical_evidence import HistoricalEvidence
from app.schemas.triage import TriageAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_ACTIONS = list(TriageAction)
"""All five actions from the allow-list, used when we want no filtering."""


def test_scorer_selects_highest_net_action_when_given_accurate_probabilities():
    """Controlled isolation test: economics must rank correct inputs correctly.

    HistoricalEvidence provides action-specific probabilities without changing
    production heuristics. The expected net values are retry_same=₹2,
    retry_alt=₹20, and dunning=₹11, so alternate rail must win.
    """
    decision = score_recovery_options(
        transaction_id="known-probabilities",
        amount_inr=100.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=None,
        customer_account_age_days=None,
        customer_most_recent_decline=None,
        permitted_actions=[
            TriageAction.RETRY_SAME_RAIL,
            TriageAction.RETRY_ALT_RAIL,
            TriageAction.ESCALATE_TO_DUNNING,
        ],
        historical_evidence=HistoricalEvidence(
            sample_size=100,
            count_recovered=0,
            count_not_recovered=0,
            recovery_rate_by_action={
                "retry_same_rail": 0.10,
                "retry_alt_rail": 0.30,
                "escalate_to_dunning": 0.15,
            },
            low_confidence=False,
        ),
    )
    assert decision.selected_action == TriageAction.RETRY_ALT_RAIL
    # 0.30 × 100 × 1.00 (alt-rail fraction) - 10 (cost) = ₹20.00
    assert abs(decision.selected_expected_net_recovery_inr - 20.00) < 0.01


# ---------------------------------------------------------------------------
# Test 1: highest expected-net-recovery permitted action is selected
# ---------------------------------------------------------------------------

def test_highest_net_recovery_action_is_selected():
    """For a soft decline with a reasonable amount, a retry action should
    have the highest expected net recovery and be selected."""
    decision = score_recovery_options(
        transaction_id="test-net-1",
        amount_inr=2000.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.85,
        customer_account_age_days=180,
        customer_most_recent_decline=None,
        permitted_actions=ALL_ACTIONS,
    )

    # The selected action should have the highest net recovery among
    # all options.
    selected_net = decision.selected_expected_net_recovery_inr
    for option in decision.options:
        assert option.expected_net_recovery_inr <= selected_net, (
            f"Option {option.action.value} has net ₹{option.expected_net_recovery_inr:.2f} "
            f"which is higher than the selected action's ₹{selected_net:.2f}"
        )

    # With a ₹2000 bank_timeout and strong customer history, a retry
    # should beat hold/no_action.
    assert decision.selected_action in (
        TriageAction.RETRY_SAME_RAIL,
        TriageAction.RETRY_ALT_RAIL,
    )


# ---------------------------------------------------------------------------
# Test 2: higher raw probability can lose due to cost/risk
# ---------------------------------------------------------------------------

def test_higher_probability_action_loses_due_to_cost_risk():
    """Construct a fixture where RETRY_SAME_RAIL has higher probability
    than HOLD_FOR_REVIEW but loses because cost + risk exceeds the
    expected recovery for a small transaction amount.

    This is the core economic property the feature is built to
    demonstrate: probability alone does not determine the best action.
    """
    # Very small transaction (₹20) with a decline reason that carries
    # a compliance-adjacent risk penalty and a customer with poor
    # payment history (adds ₹5 risk penalty).
    # With compliance_block decline and poor history:
    #   - RETRY_SAME_RAIL: p≈0.0 for compliance_block, so retry is
    #     already unfavorable.
    #
    # Use bank_timeout with poor customer history and
    # a tiny amount to create the cost/risk > recovery scenario.
    decision = score_recovery_options(
        transaction_id="test-cost-risk-1",
        amount_inr=20.0,  # Very small transaction
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.1,  # Poor history -> ₹5 risk penalty
        customer_account_age_days=10,     # New account -> dampened probabilities
        customer_most_recent_decline=None,
        permitted_actions=[
            TriageAction.RETRY_SAME_RAIL,
            TriageAction.HOLD_FOR_REVIEW,
        ],
    )

    # Find the retry option and the hold option.
    retry_option = next(
        o for o in decision.options
        if o.action == TriageAction.RETRY_SAME_RAIL
    )
    hold_option = next(
        o for o in decision.options
        if o.action == TriageAction.HOLD_FOR_REVIEW
    )

    # RETRY has a higher probability, but review remains a distinct,
    # recovery-producing action with its own lower probability and cost.
    assert retry_option.estimated_probability > hold_option.estimated_probability, (
        "Setup error: retry should have higher probability than hold"
    )

    # But HOLD should win because retry's cost+risk exceeds its
    # expected recovery for this tiny amount.
    assert retry_option.expected_net_recovery_inr < 0, (
        f"Setup error: retry's net should be negative for this fixture, "
        f"got ₹{retry_option.expected_net_recovery_inr:.2f}"
    )
    assert hold_option.expected_net_recovery_inr > retry_option.expected_net_recovery_inr

    # The decision should select HOLD despite its lower probability.
    assert decision.selected_action == TriageAction.HOLD_FOR_REVIEW, (
        f"Expected HOLD_FOR_REVIEW to win over RETRY_SAME_RAIL because "
        f"cost+risk exceeds expected recovery, but got {decision.selected_action.value}"
    )


# ---------------------------------------------------------------------------
# Test 3: unpermitted action is entirely absent from output
# ---------------------------------------------------------------------------

def test_unpermitted_action_is_absent_from_options():
    """An action NOT in the permitted list must never appear in the
    output options at all — not just 'not selected', but absent entirely.
    """
    # Only permit two actions — the other three must be absent.
    permitted = [TriageAction.RETRY_SAME_RAIL, TriageAction.HOLD_FOR_REVIEW]
    decision = score_recovery_options(
        transaction_id="test-absent-1",
        amount_inr=1000.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=90,
        customer_most_recent_decline=None,
        permitted_actions=permitted,
    )

    output_actions = {o.action for o in decision.options}

    # Permitted actions must all be present.
    for action in permitted:
        assert action in output_actions, (
            f"Permitted action {action.value} is missing from output options"
        )

    # Unpermitted actions must be entirely absent.
    unpermitted = set(TriageAction) - set(permitted)
    for action in unpermitted:
        assert action not in output_actions, (
            f"Unpermitted action {action.value} appeared in output options — "
            f"this is a security/correctness violation"
        )


# ---------------------------------------------------------------------------
# Test 4: zero-amount transaction produces valid results (no NaN/inf)
# ---------------------------------------------------------------------------

def test_zero_amount_transaction_produces_valid_results():
    """A zero-amount transaction should not produce NaN, inf, or
    negative probabilities — it should produce a valid RecoveryDecision
    where all expected_recovery values are zero or negative (due to
    action cost) and probabilities remain in [0, 1].
    """
    decision = score_recovery_options(
        transaction_id="test-zero-1",
        amount_inr=0.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=60,
        customer_most_recent_decline=None,
        permitted_actions=ALL_ACTIONS,
    )

    for option in decision.options:
        # Probabilities must be valid.
        assert 0.0 <= option.estimated_probability <= 1.0, (
            f"Invalid probability {option.estimated_probability} for "
            f"{option.action.value}"
        )
        # No NaN or inf.
        assert option.expected_recovery_inr == option.expected_recovery_inr, (
            f"NaN in expected_recovery_inr for {option.action.value}"
        )
        assert option.expected_net_recovery_inr == option.expected_net_recovery_inr, (
            f"NaN in expected_net_recovery_inr for {option.action.value}"
        )
        assert abs(option.expected_recovery_inr) != float("inf"), (
            f"Inf in expected_recovery_inr for {option.action.value}"
        )
        assert abs(option.expected_net_recovery_inr) != float("inf"), (
            f"Inf in expected_net_recovery_inr for {option.action.value}"
        )

    # A zero-amount transaction means expected_recovery is 0 for all
    # actions, and retry actions have a positive cost, so they should
    # have negative net recovery.
    assert decision.selected_action in (
        TriageAction.HOLD_FOR_REVIEW,
        TriageAction.NO_ACTION,
        TriageAction.ESCALATE_TO_DUNNING,
    ), (
        f"A zero-amount transaction should select a zero-cost action, "
        f"not {decision.selected_action.value}"
    )


# ---------------------------------------------------------------------------
# Test 5: all-zero probabilities → HOLD wins by default
# ---------------------------------------------------------------------------

def test_all_zero_probabilities_selects_hold():
    """When all probabilities are effectively zero (hard decline with
    compliance block), HOLD_FOR_REVIEW should win because it has zero
    cost and zero risk, while retry actions have positive cost.
    """
    decision = score_recovery_options(
        transaction_id="test-all-zero-1",
        amount_inr=500.0,
        decline_reason="compliance_block",
        customer_prior_success_rate=None,
        customer_account_age_days=None,
        customer_most_recent_decline=None,
        permitted_actions=ALL_ACTIONS,
    )

    # For compliance_block, retry probabilities should be 0.0.
    retry_options = [
        o for o in decision.options
        if o.action in (TriageAction.RETRY_SAME_RAIL, TriageAction.RETRY_ALT_RAIL)
    ]
    for opt in retry_options:
        assert opt.estimated_probability == 0.0, (
            f"{opt.action.value} should have 0% probability for "
            f"compliance_block, got {opt.estimated_probability}"
        )

    # HOLD should win: it has net=0, while retries have net=-cost
    # (negative due to the wasted retry cost + compliance risk penalty).
    assert decision.selected_action in (
        TriageAction.HOLD_FOR_REVIEW,
        TriageAction.NO_ACTION,
        TriageAction.ESCALATE_TO_DUNNING,
    ), (
        f"Expected a zero-cost action to win for compliance_block, "
        f"got {decision.selected_action.value}"
    )

    # The decision must be valid — a RecoveryDecision was returned.
    assert decision.transaction_id == "test-all-zero-1"
    assert len(decision.options) == len(ALL_ACTIONS)


# ---------------------------------------------------------------------------
# Test 6: value advantage is correctly computed
# ---------------------------------------------------------------------------

def test_value_advantage_is_gap_between_top_two():
    """value_advantage_vs_next_best_inr must be the gap between the
    selected option's net and the second-best option's net."""
    decision = score_recovery_options(
        transaction_id="test-advantage-1",
        amount_inr=1000.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.9,
        customer_account_age_days=365,
        customer_most_recent_decline=None,
        permitted_actions=ALL_ACTIONS,
    )

    # Sort options by net recovery descending.
    sorted_options = sorted(
        decision.options,
        key=lambda o: o.expected_net_recovery_inr,
        reverse=True,
    )
    expected_advantage = (
        sorted_options[0].expected_net_recovery_inr
        - sorted_options[1].expected_net_recovery_inr
    )

    assert abs(decision.value_advantage_vs_next_best_inr - expected_advantage) < 0.01, (
        f"Value advantage should be ₹{expected_advantage:.2f}, "
        f"got ₹{decision.value_advantage_vs_next_best_inr:.2f}"
    )


# ---------------------------------------------------------------------------
# Test 7: single permitted action works correctly
# ---------------------------------------------------------------------------

def test_single_permitted_action():
    """When only one action is permitted, it must be selected regardless
    of its net recovery value, and value advantage equals its own net."""
    decision = score_recovery_options(
        transaction_id="test-single-1",
        amount_inr=100.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=60,
        customer_most_recent_decline=None,
        permitted_actions=[TriageAction.HOLD_FOR_REVIEW],
    )

    assert decision.selected_action == TriageAction.HOLD_FOR_REVIEW
    assert len(decision.options) == 1
    assert decision.value_advantage_vs_next_best_inr == decision.selected_expected_net_recovery_inr


# ---------------------------------------------------------------------------
# Test 8: options list contains only RecoveryOptions for permitted actions
# ---------------------------------------------------------------------------

def test_options_count_matches_permitted_count():
    """The number of options in the output must exactly match the number
    of permitted actions — no extras, no missing."""
    permitted = [
        TriageAction.RETRY_SAME_RAIL,
        TriageAction.RETRY_ALT_RAIL,
        TriageAction.HOLD_FOR_REVIEW,
    ]
    decision = score_recovery_options(
        transaction_id="test-count-1",
        amount_inr=500.0,
        decline_reason="bank_timeout",
        customer_prior_success_rate=0.5,
        customer_account_age_days=60,
        customer_most_recent_decline=None,
        permitted_actions=permitted,
    )

    assert len(decision.options) == len(permitted)


# ---------------------------------------------------------------------------
# Test 9: recovery fractions differentiate equal-probability actions and flip ranking
# ---------------------------------------------------------------------------

def test_recovery_fraction_differentiates_equal_probability_actions_and_flips_ranking():
    """Prove that two actions with identical probability and amount but different
    recovery_fraction values produce different expected_net_recovery_inr, and
    that the ranking between them flips as a result.

    Scenario:
      Transaction amount = ₹100.00
      Permitted actions: RETRY_SAME_RAIL and ESCALATE_TO_DUNNING.
      Costs:
        - RETRY_SAME_RAIL: ₹8.00 direct cost
        - ESCALATE_TO_DUNNING: ₹4.00 direct cost
      Identical probability: p = 0.50 for both actions (injected via HistoricalEvidence).

    Without recovery fraction adjustment (uniform fraction = 1.00):
      - Dunning net = (0.50 × 100 × 1.00) - 4 = 50 - 4 = ₹46.00
      - Retry net   = (0.50 × 100 × 1.00) - 8 = 50 - 8 = ₹42.00
      -> Dunning would WIN because its cost is ₹4 lower.

    With calibrated recovery fractions (Retry = 1.00, Dunning = 0.82):
      - Dunning net = (0.50 × 100 × 0.82) - 4 = 41 - 4 = ₹37.00
      - Retry net   = (0.50 × 100 × 1.00) - 8 = 50 - 8 = ₹42.00
      -> Retry WINS with ₹42.00 vs ₹37.00.

    This proves:
      1. Different recovery fractions produce different expected_recovery_inr (₹50 vs ₹41).
      2. Different expected_net_recovery_inr is produced despite equal probability and amount.
      3. The ranking flips from ESCALATE_TO_DUNNING to RETRY_SAME_RAIL.
    """
    he = HistoricalEvidence(
        sample_size=50,
        count_recovered=25,
        count_not_recovered=25,
        recovery_rate_by_action={
            "retry_same_rail": 0.50,
            "escalate_to_dunning": 0.50,
        },
        low_confidence=False,
    )

    decision = score_recovery_options(
        transaction_id="test-fraction-flip-1",
        amount_inr=100.0,
        decline_reason="insufficient_funds",
        customer_prior_success_rate=0.5,
        customer_account_age_days=90,
        customer_most_recent_decline=None,
        permitted_actions=[
            TriageAction.RETRY_SAME_RAIL,
            TriageAction.ESCALATE_TO_DUNNING,
        ],
        historical_evidence=he,
    )

    options_by_action = {opt.action: opt for opt in decision.options}
    retry_opt = options_by_action[TriageAction.RETRY_SAME_RAIL]
    dunning_opt = options_by_action[TriageAction.ESCALATE_TO_DUNNING]

    # 1. Verify identical probability and amount
    assert retry_opt.estimated_probability == dunning_opt.estimated_probability == 0.50

    # 2. Verify different recovery values due to recovery fraction (1.00 vs 0.82)
    # Expected recovery: 0.50 * 100 * 1.00 = 50.0 vs 0.50 * 100 * 0.82 = 41.0
    assert abs(retry_opt.expected_recovery_inr - 50.00) < 0.01
    assert abs(dunning_opt.expected_recovery_inr - 41.00) < 0.01
    assert retry_opt.expected_recovery_inr != dunning_opt.expected_recovery_inr

    # 3. Verify expected net recovery values
    # Retry net: 50.0 - 8.0 = 42.00
    # Dunning net: 41.0 - 4.0 = 37.00
    assert abs(retry_opt.expected_net_recovery_inr - 42.00) < 0.01
    assert abs(dunning_opt.expected_net_recovery_inr - 37.00) < 0.01
    assert retry_opt.expected_net_recovery_inr != dunning_opt.expected_net_recovery_inr

    # 4. Prove that the ranking flips:
    # If fractions were 1.0 for both, dunning net (46.0) > retry net (42.0)
    unadjusted_dunning_net = (0.50 * 100.0 * 1.0) - dunning_opt.action_cost_inr
    assert unadjusted_dunning_net > retry_opt.expected_net_recovery_inr

    # With the recovery fraction model, retry wins over dunning
    assert retry_opt.expected_net_recovery_inr > dunning_opt.expected_net_recovery_inr
    assert decision.selected_action == TriageAction.RETRY_SAME_RAIL
    assert decision.options[0].action == TriageAction.RETRY_SAME_RAIL
    assert decision.options[1].action == TriageAction.ESCALATE_TO_DUNNING
