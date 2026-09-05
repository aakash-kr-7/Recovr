#!/usr/bin/env python
"""Read-only diagnostic for action-level evaluation failures.

It writes compact per-transaction traces after decisions have been made.
`action_outcomes` are never supplied to gate, reasoning, or scoring.
Run with LLM_PROVIDER=disabled to diagnose the fallback/economic path.
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent.economics.scoring import score_recovery_options
from app.agent.executor import BatchSpendTracker, execute
from app.agent.gate import route
from app.agent.reasoning import get_triage_decision
from app.core.config import get_settings
from app.schemas.triage import TriageAction, TriagePath
from app.schemas.recovery import RecoveryContext
from scripts.run_evaluation import _load_holdout, _record, _summary

TRACE_PATH = REPO_ROOT / "data" / "eval" / "decision_traces.json"
REPORT_PATH = REPO_ROOT / "data" / "eval" / "latest_diagnostic.json"


def _rank(values: dict[str, float]) -> list[str]:
    return sorted(values, key=lambda action: (-values[action], action))


def _rank_agreement(left: list[str], right: list[str]) -> float:
    """Normalized Spearman agreement for five actions; 1 means same order."""
    n = len(left)
    left_pos, right_pos = ({item: i + 1 for i, item in enumerate(order)} for order in (left, right))
    squared_distance = sum((left_pos[action] - right_pos[action]) ** 2 for action in left)
    return 1 - (6 * squared_distance) / (n * (n * n - 1))


def _true_expected_values(transaction) -> dict[str, float]:
    return {
        action: round(
            outcome["success_probability"] * outcome["recovery_amount_if_success_inr"]
            - outcome["action_cost_inr"] - outcome["risk_penalty_inr"],
            2,
        )
        for action, outcome in transaction.action_outcomes.items()
    }


def _classify(trace: dict) -> str:
    """Exclusive primary attribution; supporting mechanisms are reported too."""
    if trace["final_selected_action"] != trace["economic_selected_action"]:
        return "G_execution_safety_override"
    if trace["economic_selected_action"] == trace["true_expected_best_action"]:
        return "F_realization_variance"
    if trace["cost_risk_corrected_best_action"] == trace["true_expected_best_action"]:
        return "B_cost_or_risk_assumption"
    if trace["probability_corrected_best_action"] == trace["true_expected_best_action"]:
        return "A_probability_estimate"
    return "F_generator_feature_or_model_gap"


def build_diagnostics() -> tuple[list[dict], dict]:
    settings = get_settings()
    transactions = _load_holdout()
    tracker = BatchSpendTracker(cap_inr=settings.batch_spend_cap_inr)
    traces, full_records, economic_records, deterministic_records = [], [], [], []

    for txn in transactions:
        gate = route(txn)
        candidate, confidence, reasoning_status = None, None, "not_called"
        if gate.path == TriagePath.DETERMINISTIC:
            candidate, reasoning_status = gate.fast_path_action, "deterministic"
        else:
            try:
                response = get_triage_decision(txn)
                candidate, confidence, reasoning_status = response.action, response.confidence, "available"
            except Exception as exc:
                reasoning_status = f"unavailable: {type(exc).__name__}"

        economics = score_recovery_options(
            transaction_id=txn.id, permitted_actions=list(TriageAction),
            context=RecoveryContext(
                amount_inr=txn.amount_inr, decline_reason=txn.decline_reason,
                customer_prior_success_rate=txn.customer_history.get("prior_success_rate", txn.customer_history.get("success_rate")),
                customer_account_age_days=txn.customer_history.get("account_age_days"),
                customer_most_recent_decline=txn.customer_history.get("most_recent_decline_reason", txn.customer_history.get("most_recent_decline")),
                last_successful_rail=txn.customer_history.get("last_successful_rail"),
                recent_retry_count=txn.customer_history.get("recent_retry_count"), failure_hour=txn.failed_at.hour,
            ),
        )
        decision = execute(
            transaction=txn, path=gate.path, action=economics.selected_action,
            reasoning_text="diagnostic", confidence=confidence, spend_tracker=tracker,
            options=economics.options,
            selected_expected_net_recovery_inr=economics.selected_expected_net_recovery_inr,
            value_advantage_vs_next_best_inr=economics.value_advantage_vs_next_best_inr,
        )

        predicted = {option.action.value: option.model_dump() for option in economics.options}
        predicted_values = {action: option["expected_net_recovery_inr"] for action, option in predicted.items()}
        realized_values = {action: outcome["net_recovered_inr"] for action, outcome in txn.action_outcomes.items()}
        true_expected = _true_expected_values(txn)
        # Counterfactual diagnostics isolate the score's cost/risk model and
        # its action-specific probability model without exposing truth to it.
        cost_corrected = {
            action: predicted[action]["estimated_probability"] * txn.action_outcomes[action]["recovery_amount_if_success_inr"]
            - txn.action_outcomes[action]["action_cost_inr"] - txn.action_outcomes[action]["risk_penalty_inr"]
            for action in predicted
        }
        probability_corrected = {
            action: txn.action_outcomes[action]["success_probability"] * txn.action_outcomes[action]["recovery_amount_if_success_inr"]
            - predicted[action]["action_cost_inr"] - predicted[action]["risk_penalty_inr"]
            for action in predicted
        }
        predicted_ranking, realized_ranking, expected_ranking = (_rank(values) for values in (predicted_values, realized_values, true_expected))
        trace = {
            "transaction_id": txn.id, "amount_inr": txn.amount_inr,
            "decline_reason": txn.decline_reason, "customer_context": txn.customer_history,
            "failed_at": txn.failed_at.isoformat(), "gate_result": gate.path.value,
            "reasoning_status": reasoning_status, "candidate_action": candidate.value if candidate else None,
            "confidence": confidence, "predicted_options": predicted,
            "predicted_ranking": predicted_ranking, "realized_outcomes": txn.action_outcomes,
            "realized_ranking": realized_ranking, "true_expected_action_values": true_expected,
            "true_expected_ranking": expected_ranking,
            "economic_selected_action": economics.selected_action.value,
            "final_selected_action": decision.selected_action.value, "was_gated": decision.was_gated,
            "best_realized_action": realized_ranking[0], "best_realized_net_inr": realized_values[realized_ranking[0]],
            "true_expected_best_action": expected_ranking[0],
            "regret_inr": round(realized_values[realized_ranking[0]] - realized_values[decision.selected_action.value], 2),
            "selected_is_optimal": decision.selected_action.value == realized_ranking[0],
            "ranking_agreement_spearman": round(_rank_agreement(predicted_ranking, realized_ranking), 4),
            "expected_ranking_agreement_spearman": round(_rank_agreement(predicted_ranking, expected_ranking), 4),
            "cost_risk_corrected_best_action": _rank(cost_corrected)[0],
            "probability_corrected_best_action": _rank(probability_corrected)[0],
        }
        trace["primary_error_cause"] = None if trace["selected_is_optimal"] else _classify(trace)
        traces.append(trace)
        full_records.append(_record(txn, decision.selected_action))
        economic_records.append(_record(txn, economics.selected_action))
        deterministic_action = gate.fast_path_action if gate.path == TriagePath.DETERMINISTIC else TriageAction.HOLD_FOR_REVIEW
        deterministic_records.append(_record(txn, deterministic_action))

    failed = [trace for trace in traces if not trace["selected_is_optimal"]]
    causes = {key: sum(trace["primary_error_cause"] == key for trace in failed) for key in (
        "A_probability_estimate", "B_cost_or_risk_assumption", "C_gate_restricting", "D_deterministic_rule", "E_scorer_input_optimization", "F_realization_variance", "F_generator_feature_or_model_gap", "G_execution_safety_override",
    )}
    probability_audit = {}
    for action in (item.value for item in TriageAction):
        differences = [trace["predicted_options"][action]["estimated_probability"] - trace["realized_outcomes"][action]["success_probability"] for trace in traces]
        probability_audit[action] = {
            "mean_error": round(sum(differences) / len(differences), 4),
            "mean_absolute_error": round(sum(abs(value) for value in differences) / len(differences), 4),
            "semantic_note": "Action-specific success probability; evaluated against the generator's pre-action conditional probability, never realized amount.",
        }
    report = {
        "evaluation_label": "RECOVR fallback/economic evaluation without LLM reasoning",
        "transaction_count": len(traces), "failed_decision_count": len(failed),
        "full_fallback": _summary(full_records), "economic_only_all_actions": _summary(economic_records),
        "deterministic_gate_policy_only": _summary(deterministic_records),
        "gate_contribution": {
            "final_vs_economic_only_regret_inr": round(_summary(full_records)["total_regret_inr"] - _summary(economic_records)["total_regret_inr"], 2),
            "executor_overrides": sum(trace["final_selected_action"] != trace["economic_selected_action"] for trace in traces),
            "routing_restrictions": 0,
            "note": "Scoring receives all five actions after both gate paths, so route() does not restrict the fallback scorer. Any delta is the executor spend-cap safety override, not a gate candidate action.",
        },
        "ranking_agreement": {
            "mean_predicted_vs_realized_spearman": round(sum(trace["ranking_agreement_spearman"] for trace in traces) / len(traces), 4),
            "mean_predicted_vs_true_expected_spearman": round(sum(trace["expected_ranking_agreement_spearman"] for trace in traces) / len(traces), 4),
            "top_action_matches_realized": sum(trace["predicted_ranking"][0] == trace["realized_ranking"][0] for trace in traces),
            "top_action_matches_true_expected": sum(trace["predicted_ranking"][0] == trace["true_expected_ranking"][0] for trace in traces),
        },
        "probability_audit": probability_audit,
        "error_decomposition": {
            "denominator": len(failed),
            "exclusive_primary_counts": causes,
            "exclusive_primary_percentages": {key: round(value / len(failed) * 100, 2) if failed else 0.0 for key, value in causes.items()},
            "scorer_optimized_its_own_inputs_count": sum(trace["final_selected_action"] == trace["economic_selected_action"] for trace in traces),
            "visible_generator_features_consumed_by_economics": ["failed_at hour", "customer_history.last_successful_rail", "customer_history.recent_retry_count"],
            "unobservable_realization_component": sum(trace["economic_selected_action"] == trace["true_expected_best_action"] and not trace["selected_is_optimal"] for trace in failed),
        },
        "worst_decisions": sorted((trace for trace in failed), key=lambda item: item["regret_inr"], reverse=True)[:10],
        "trace_path": str(TRACE_PATH),
    }
    return traces, report


def main() -> None:
    traces, report = build_diagnostics()
    TRACE_PATH.write_text(json.dumps(traces, indent=2))
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    # The CLI default is intentionally no live LLM: this diagnostic labels
    # itself as fallback performance unless the caller explicitly configures one.
    os.environ.setdefault("LLM_PROVIDER", "disabled")
    main()
