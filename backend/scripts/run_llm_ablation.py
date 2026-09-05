#!/usr/bin/env python
"""LLM contribution ablation without letting prose control recovery action.

By design, the current LLM contract is observational: economics remains the
only action selector. ``--live`` is intentionally opt-in because it sends the
holdout's transaction context to the configured external provider.
"""
import argparse, json, statistics, sys, time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path: sys.path.insert(0, str(REPO_ROOT))

from app.agent.reasoning import get_triage_decision
from scripts.run_evaluation import CANONICAL_SEED, ROBUSTNESS_SEEDS, _load_holdout, _seed_holdout, _record, _recovr, _summary

REPORT_PATH = Path(__file__).parent.parent / "data" / "eval" / "llm_ablation_report.json"


def evaluate(transactions, reasoner=None):
    """Compare economics-only with current LLM-informed architecture.

    A reasoner's recommendation is recorded, but cannot replace calibrated
    scoring or executor policy. Provider errors are explicit fallback events.
    """
    off, on, observations, latencies = [], [], [], []
    for txn in transactions:
        economic_action, economic_expected, *_ = _recovr(txn)
        off_row = _record(txn, economic_action, economic_expected)
        start = time.perf_counter()
        recommendation, error = None, None
        if reasoner is None:
            error = "live_provider_not_requested"
        else:
            try:
                recommendation = reasoner(txn)
            except Exception as exc:  # provider/timeout/malformed all safely fall back
                # Do not persist provider payloads: they can contain account
                # metadata and add no value to an ablation result.
                error = type(exc).__name__
        latencies.append((time.perf_counter() - start) * 1000)
        informed_action, informed_expected, *_ = _recovr(txn, recommendation.insights if recommendation else None)
        on_row = _record(txn, informed_action, informed_expected)
        llm_action = recommendation.action.value if recommendation else None
        observations.append({"transaction_id": txn.id, "economic_action": economic_action.value,
            "llm_action": llm_action, "final_action": informed_action.value,
            "predicted_expected_value_inr": informed_expected, "realized_net_recovery_inr": on_row["net_recovered_inr"],
            "true_hidden_expected_value_inr": on_row["true_expected_net_inr"], "expected_regret_inr": on_row["expected_regret_inr"],
            "realized_regret_inr": on_row["realized_regret_inr"],
            "llm_changed_decision": informed_action != economic_action, "economics_overrode_llm": bool(llm_action and llm_action != informed_action.value),
            "improved_expected_value": on_row["true_expected_net_inr"] > off_row["true_expected_net_inr"], "improved_realized_outcome": on_row["net_recovered_inr"] > off_row["net_recovered_inr"], "worsened_decision": on_row["true_expected_net_inr"] < off_row["true_expected_net_inr"], "error": error})
        off.append(off_row); on.append(on_row)
    failures = sum(item["error"] is not None for item in observations)
    return {"economics_only": _summary(off), "llm_informed_recovr": _summary(on),
        "decision_effect": {"llm_changed_decision_count": sum(item["llm_changed_decision"] for item in observations), "improved_expected_value_count": sum(item["improved_expected_value"] for item in observations), "improved_realized_outcome_count": sum(item["improved_realized_outcome"] for item in observations),
            "worsened_decision_count": sum(item["worsened_decision"] for item in observations), "economics_overrode_llm_count": sum(item["economics_overrode_llm"] for item in observations),
            "net_value_added_by_llm_inr": round(sum(row["net_recovered_inr"] for row in on) - sum(row["net_recovered_inr"] for row in off), 2)},
        "reliability": {"request_count": len(transactions), "failure_count": failures, "failure_rate": round(failures / len(transactions), 4) if transactions else 0.0,
            "fallback_count": failures, "average_latency_ms": round(statistics.mean(latencies), 3) if latencies else 0.0}, "records": observations}


def run_ablation(live=False):
    provider_failed = False
    def reasoner(txn):
        nonlocal provider_failed
        if provider_failed:
            raise RuntimeError("provider_circuit_open_after_prior_failure")
        try:
            return get_triage_decision(txn)
        except Exception:
            provider_failed = True
            raise
    if not live:
        reasoner = None
    canonical = evaluate(_load_holdout(), reasoner)
    per_seed = {}
    for seed in ROBUSTNESS_SEEDS:
        txns = _load_holdout() if seed == CANONICAL_SEED else _seed_holdout(seed)
        per_seed[str(seed)] = evaluate(txns, reasoner)
    status = "provider_unavailable_all_requests_fell_back" if live and canonical["reliability"]["failure_count"] else ("completed" if live else "not_run_without_explicit_holdout-data egress approval")
    return {"ablation_version": "llm_observational_v1", "canonical_seed": CANONICAL_SEED,
        "live_provider_requested": live, "architecture": "LLM action/reasoning/confidence is audit-only; economics selects final action.",
        "canonical": canonical, "multi_seed_economics_only_reference": per_seed,
        "live_measurement_status": status,
        "minimum_change_for_value_test": "Add a versioned, schema-validated, context-grounded structured signal with a bounded economics modifier, then re-run this ablation. Do not use free-form action text as a modifier."}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--live", action="store_true")
    args = parser.parse_args(); report = run_ablation(args.live)
    REPORT_PATH.write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))
if __name__ == "__main__": main()
