"""Tests for hidden action-level ground truth used only by evaluation."""

from scripts.generate_synthetic_data import ACTION_VALUES, generate


def test_generated_transactions_have_complete_action_outcome_profiles():
    transactions = generate(count=200, seed=42)

    canonical_best_actions = set()
    for transaction in transactions:
        assert set(transaction.action_outcomes) == set(ACTION_VALUES)
        for outcome in transaction.action_outcomes.values():
            assert outcome["net_recovered_inr"] == round(
                outcome["recovered_amount_inr"]
                - outcome["action_cost_inr"]
                - outcome["risk_penalty_inr"],
                2,
            )
        best_net = max(
            outcome["net_recovered_inr"]
            for outcome in transaction.action_outcomes.values()
        )
        assert transaction.action_outcomes[transaction.ground_truth_label]["net_recovered_inr"] == best_net
        canonical_best_actions.add(transaction.ground_truth_label)

    # The fixed seed covers every intervention type; labels are derived from
    # realized action economics, not directly assigned from decline reason.
    assert canonical_best_actions == set(ACTION_VALUES)
