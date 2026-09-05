#!/usr/bin/env python
"""Comparable action-level evaluation; does not expose holdout outcomes to policy.

The policy functions below receive a Transaction only. Hidden potential
outcomes are read exclusively by ``_record`` after an action is selected.
"""
import json, random, statistics, sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path: sys.path.insert(0, str(REPO_ROOT))

from app.agent.economics.scoring import score_recovery_options
from app.agent.rules.decline_taxonomy import FAST_PATH_TABLE
from app.core.config import get_settings
from app.models.transaction import Transaction
from app.schemas.recovery import RecoveryContext
from app.schemas.triage import TriageAction
from scripts.generate_synthetic_data import generate

HOLDOUT_PATH = REPO_ROOT / "data" / "eval" / "holdout.json"
REPORT_PATH = REPO_ROOT / "data" / "eval" / "latest_report.json"
CANONICAL_SEED = 42
ROBUSTNESS_SEEDS = (42, 7, 19, 73, 101)
POLICIES = ("retry_all_same_rail", "fixed_rule_policy", "recovr")
ACTION_COSTS = {"retry_same_rail": 8.0, "retry_alt_rail": 10.0, "hold_for_review": 6.0, "escalate_to_dunning": 4.0, "no_action": 0.0}


def _transaction(row):
    txn = Transaction(id=row["id"], amount_inr=row["amount_inr"], decline_reason_raw=row["decline_reason_raw"],
        decline_reason=row["decline_reason"], customer_id=row["customer_id"], customer_history=row["customer_history"],
        failed_at=datetime.fromisoformat(row["failed_at"]), is_synthetic=True, ground_truth_label=row["ground_truth_label"], data_split="holdout")
    txn.action_outcomes = row["action_outcomes"]
    return txn


def _load_holdout():
    return [_transaction(row) for row in json.loads(HOLDOUT_PATH.read_text())]


def _seed_holdout(seed):
    """In-memory robustness population; never writes or changes the canonical holdout."""
    rows = generate(200, seed)
    rng = random.Random(seed); rng.shuffle(rows)
    return [_transaction({**row.__dict__, "data_split": "holdout"}) for row in rows[int(len(rows) * .7):]]


def _context(txn):
    h = txn.customer_history
    return RecoveryContext(amount_inr=txn.amount_inr, decline_reason=txn.decline_reason,
        customer_prior_success_rate=h.get("prior_success_rate", h.get("success_rate")), customer_account_age_days=h.get("account_age_days"),
        customer_most_recent_decline=h.get("most_recent_decline_reason", h.get("most_recent_decline")), last_successful_rail=h.get("last_successful_rail"),
        recent_retry_count=h.get("recent_retry_count"), failure_hour=txn.failed_at.hour)


def _recovr(txn, llm_insights=None, db=None, **kwargs):
    # LLM prose is not an action input: the existing economics layer selects
    # the executable action. Avoiding provider calls makes evaluation repeatable.
    context = _context(txn).model_copy(update={"llm_insights": llm_insights})
    
    if db:
        from app.agent.economics.historical_evidence import query_historical_evidence
        evidence = query_historical_evidence(db=db, decline_reason=txn.decline_reason, customer_history=txn.customer_history)
    else:
        evidence = None
        
    decision = score_recovery_options(transaction_id=txn.id, permitted_actions=list(TriageAction), context=context, historical_evidence=evidence)
    selected_option = next(option for option in decision.options if option.action == decision.selected_action)
    return decision.selected_action, selected_option.expected_net_recovery_inr, selected_option.estimated_probability


def _fixed(txn, **kwargs):
    return (FAST_PATH_TABLE.get(txn.decline_reason, (TriageAction.RETRY_SAME_RAIL,))[0], None, None)


def _retry_all(txn, **kwargs): return TriageAction.RETRY_SAME_RAIL, None, None

POLICY_SELECTORS = {"retry_all_same_rail": _retry_all, "fixed_rule_policy": _fixed, "recovr": _recovr}


def _true_expected(outcome):
    return round(outcome["success_probability"] * outcome["recovery_amount_if_success_inr"] - outcome["action_cost_inr"] - outcome["risk_penalty_inr"], 2)


def _record(txn, action, model_expected=None, held=False, model_prob=None):
    outcomes, selected = txn.action_outcomes, txn.action_outcomes[action.value]
    expected_values = {name: _true_expected(value) for name, value in outcomes.items()}
    best_expected, best_realized = max(expected_values.values()), max(value["net_recovered_inr"] for value in outcomes.values())
    return {"transaction_id": txn.id, "amount_inr": txn.amount_inr, "action": action.value, "held": held,
        "model_expected_net_inr": model_expected, "model_prob": model_prob, "true_expected_net_inr": expected_values[action.value],
        "true_best_expected_net_inr": best_expected, "expected_regret_inr": round(best_expected - expected_values[action.value], 2),
        "gross_recovered_inr": selected["recovered_amount_inr"], "action_cost_inr": selected["action_cost_inr"],
        "risk_penalty_inr": selected["risk_penalty_inr"], "net_recovered_inr": selected["net_recovered_inr"],
        "best_realized_net_inr": best_realized, "realized_regret_inr": round(best_realized - selected["net_recovered_inr"], 2),
        "recovered": selected["recovered"], "unnecessary_retry": action.value in {"retry_same_rail", "retry_alt_rail"} and not selected["recovered"]}


def _apply_policy(transactions, policy, constrained, cap, db=None):
    records, spent = [], 0.0
    for txn in transactions:
        selected, model_expected, model_prob = POLICY_SELECTORS[policy](txn, db=db)
        # Same deterministic action-cost budget for every policy. The cost is
        # known policy semantics, not a hidden outcome; no policy sees outcome.
        planned_cost = ACTION_COSTS[selected.value]
        held = constrained and spent + planned_cost > cap
        if held: selected, model_expected, model_prob = TriageAction.HOLD_FOR_REVIEW, None, None
        else: spent += planned_cost
        records.append(_record(txn, selected, model_expected, held, model_prob))
    return records


def _summary(records):
    count, at_risk = len(records), sum(row["amount_inr"] for row in records)
    gross, costs, risk, net = (sum(row[key] for row in records) for key in ("gross_recovered_inr", "action_cost_inr", "risk_penalty_inr", "net_recovered_inr"))
    expected_regret, realized_regret = sum(row["expected_regret_inr"] for row in records), sum(row["realized_regret_inr"] for row in records)
    return {"transaction_count": count, "total_amount_at_risk_inr": round(at_risk, 2), "gross_recovered_inr": round(gross, 2),
        "recovery_rate_by_inr": round(gross / at_risk, 4) if at_risk else 0.0, "recovery_rate_by_transaction": round(sum(row["recovered"] for row in records) / count, 4) if count else 0.0,
        "action_cost_inr": round(costs, 2), "risk_penalty_inr": round(risk, 2), "net_recovery_inr": round(net, 2),
        "true_expected_net_value_inr": round(sum(row["true_expected_net_inr"] for row in records), 2),
        "model_expected_net_value_inr": round(sum(row["model_expected_net_inr"] or 0 for row in records), 2),
        "expected_regret_inr": round(expected_regret, 2), "realized_regret_inr": round(realized_regret, 2), "opportunity_loss_inr": round(realized_regret, 2),
        "unnecessary_retry_count": sum(row["unnecessary_retry"] for row in records),
        "missed_recovery_value_inr": round(sum(max(0, row["best_realized_net_inr"] - row["net_recovered_inr"]) for row in records), 2),
        "held_count": sum(row["held"] for row in records), "action_distribution": {action.value: sum(row["action"] == action.value for row in records) for action in TriageAction}}


def _view(transactions, constrained, cap, db=None): return {policy: _summary(_apply_policy(transactions, policy, constrained, cap, db)) for policy in POLICIES}


def _calibration(records):
    valid = [r for r in records if r.get("model_prob") is not None]
    if not valid: return []
    bins = [[] for _ in range(5)]
    for r in valid:
        idx = min(int(r["model_prob"] / 0.2), 4)
        bins[idx].append(r)
    stats = []
    for i, b in enumerate(bins):
        if not b: continue
        avg_pred = sum(r["model_prob"] for r in b) / len(b)
        avg_obs = sum(1 for r in b if r["recovered"]) / len(b)
        stats.append({
            "bin": f"[{i*0.2:.2f}, {(i+1)*0.2:.2f})",
            "count": len(b),
            "expected_probability": round(avg_pred, 4),
            "observed_recovery_rate": round(avg_obs, 4)
        })
    return stats


def _increment(recovr, baseline):
    delta = recovr["net_recovery_inr"] - baseline["net_recovery_inr"]
    return {"inr": round(delta, 2), "percent_vs_baseline": round((delta / abs(baseline["net_recovery_inr"])) * 100, 2) if baseline["net_recovery_inr"] else None}

def _binary(records):
    buckets = {key: [] for key in ("tp", "fp", "fn", "tn")}
    for row in records:
        predicted = row["action"] in {"retry_same_rail", "retry_alt_rail"}
        truth = row["best_realized_net_inr"] > 0
        buckets["tp" if predicted and truth else "fp" if predicted else "fn" if truth else "tn"].append(row)
    tp, fp, fn, tn = (buckets[key] for key in ("tp", "fp", "fn", "tn"))
    return {"confusion_matrix": {"true_positive_count": len(tp), "false_positive_count": len(fp), "false_negative_count": len(fn), "true_negative_count": len(tn)},
        "precision": len(tp) / (len(tp) + len(fp)) if tp or fp else None, "recall": len(tp) / (len(tp) + len(fn)) if tp or fn else None,
        "false_positive_transaction_ids": [r["transaction_id"] for r in fp], "false_negative_transaction_ids": [r["transaction_id"] for r in fn]}


def _robustness(cap, db=None):
    results = {policy: [] for policy in POLICIES}
    for seed in ROBUSTNESS_SEEDS:
        view = _view(_load_holdout() if seed == CANONICAL_SEED else _seed_holdout(seed), False, cap, db)
        for policy in POLICIES: results[policy].append(view[policy])
    output = {}
    for policy, rows in results.items():
        output[policy] = {"seeds": list(ROBUSTNESS_SEEDS), "mean_net_recovery_inr": round(statistics.mean(r["net_recovery_inr"] for r in rows), 2),
            "stddev_net_recovery_inr": round(statistics.pstdev(r["net_recovery_inr"] for r in rows), 2),
            "mean_expected_regret_inr": round(statistics.mean(r["expected_regret_inr"] for r in rows), 2),
            "stddev_expected_regret_inr": round(statistics.pstdev(r["expected_regret_inr"] for r in rows), 2),
            "mean_recovery_rate_by_inr": round(statistics.mean(r["recovery_rate_by_inr"] for r in rows), 4), "per_seed": rows}
    ordering = [max(POLICIES, key=lambda p: results[p][i]["net_recovery_inr"]) for i in range(len(ROBUSTNESS_SEEDS))]
    return output, {"net_recovery_winner_by_seed": dict(zip(ROBUSTNESS_SEEDS, ordering)), "recovr_wins_every_seed": all(winner == "recovr" for winner in ordering)}


def run_evaluation():
    settings, transactions = get_settings(), _load_holdout()
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        unconstrained, constrained = _view(transactions, False, settings.batch_spend_cap_inr, db), _view(transactions, True, settings.batch_spend_cap_inr, db)
        robustness, consistency = _robustness(settings.batch_spend_cap_inr, db)
        recovr_records = _apply_policy(transactions, "recovr", True, settings.batch_spend_cap_inr, db)
    binary = _binary(recovr_records)
    recovr = constrained["recovr"]
    report = {"generated_at": datetime.utcnow().isoformat(), "evaluation_version": "comparable_action_economics_v3", "canonical_seed": CANONICAL_SEED,
        "holdout_set_size": len(transactions), "policy_definitions": {"retry_all_same_rail": "Retries every holdout payment on the same rail.", "fixed_rule_policy": "Uses FAST_PATH_TABLE where defined; otherwise retries same rail.", "recovr": "Existing calibrated economics scoring selects an allowed action; no hidden outcome is supplied."},
        "methodology": {"unconstrained": "No spend budget override.", "constrained": "Every policy is processed in the identical holdout order under the same action-cost budget. Over-budget actions become hold_for_review.", "expected_regret": "Best hidden conditional expected net value minus the selected action's hidden conditional expected net value. Realized regret remains separate and uses sampled realized net values."},
        "unconstrained": unconstrained, "constrained": constrained,
        "incremental_net_recovery": {"unconstrained": {"vs_retry_all": _increment(unconstrained["recovr"], unconstrained["retry_all_same_rail"]), "vs_fixed_rule": _increment(unconstrained["recovr"], unconstrained["fixed_rule_policy"])}, "constrained": {"vs_retry_all": _increment(constrained["recovr"], constrained["retry_all_same_rail"]), "vs_fixed_rule": _increment(constrained["recovr"], constrained["fixed_rule_policy"])}},
        "multi_seed_robustness": robustness, "multi_seed_consistency": consistency,
        "evaluation_views": {"unconstrained_decision_quality": unconstrained["recovr"], "constrained_execution_quality": constrained["recovr"], "cap_induced_execution_overrides": constrained["recovr"]["held_count"] - unconstrained["recovr"]["held_count"]},
        "secondary_binary_retry_diagnostics": {**binary, "note": "Legacy binary diagnostics are secondary; action economics and expected regret are primary."},
        # Compatibility aliases for the unchanged Results page. They retain
        # the RECOVR constrained view, while the comparable views above are
        # the authoritative evaluation.
        "confusion_matrix": binary["confusion_matrix"], "precision": binary["precision"], "recall": binary["recall"],
        "false_positive_transaction_ids": binary["false_positive_transaction_ids"], "false_negative_transaction_ids": binary["false_negative_transaction_ids"],
        "money": {"total_at_risk_inr": recovr["total_amount_at_risk_inr"], "recovered_inr": recovr["gross_recovered_inr"], "missed_recovery_inr": recovr["missed_recovery_value_inr"], "false_positive_cost_inr": recovr["risk_penalty_inr"], "net_recovered_inr": recovr["net_recovery_inr"]},
        "economic_evaluation": {"total_at_risk_inr": recovr["total_amount_at_risk_inr"], "total_expected_recovery_inr": recovr["model_expected_net_value_inr"], "total_actual_recovered_inr": recovr["gross_recovered_inr"], "expected_vs_actual_variance_inr": round(recovr["net_recovery_inr"] - recovr["model_expected_net_value_inr"], 2), "average_expected_value_per_decision_inr": round(recovr["model_expected_net_value_inr"] / len(transactions), 2), "average_realized_value_per_decision_inr": round(recovr["net_recovery_inr"] / len(transactions), 2), "recovery_rate": recovr["recovery_rate_by_inr"], "wasted_retry_cost_inr": recovr["action_cost_inr"], "missed_recovery_inr": recovr["missed_recovery_value_inr"], "amount_band_breakdown": []},
        "calibration": _calibration(recovr_records),
        "note": "Comparable action-level views are primary; legacy binary fields are secondary."}
    # Assertions catch population, conservation, and constraint drift.
    for view in (unconstrained, constrained):
        assert {row["transaction_count"] for row in view.values()} == {len(transactions)}
        assert {row["total_amount_at_risk_inr"] for row in view.values()} == {round(sum(t.amount_inr for t in transactions), 2)}
        for metrics in view.values(): assert metrics["realized_regret_inr"] == metrics["opportunity_loss_inr"]
    return report


def main():
    report = run_evaluation(); REPORT_PATH.write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))
if __name__ == "__main__": main()
