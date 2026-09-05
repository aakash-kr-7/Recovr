import json
import math
from pathlib import Path
from datetime import datetime
import sys

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.agent.economics.probability_heuristics import estimate_probabilities

train_path = backend_root / "data" / "synthetic" / "transactions.json"
train_data = json.loads(train_path.read_text())

actions = ["retry_same_rail", "retry_alt_rail", "hold_for_review", "escalate_to_dunning"]

print(f"Total training transactions: {len(train_data)}")

results = {a: [] for a in actions}

for row in train_data:
    decline = row["decline_reason"]
    amount = row["amount_inr"]
    cust = row["customer_history"]
    failed_at = datetime.fromisoformat(row["failed_at"])
    
    prior_success = cust.get("prior_success_rate", cust.get("success_rate"))
    account_age = cust.get("account_age_days")
    most_recent_decline = cust.get("most_recent_decline_reason", cust.get("most_recent_decline"))
    last_rail = cust.get("last_successful_rail")
    recent_retry_cnt = cust.get("recent_retry_count")
    failure_hour = failed_at.hour
    
    preds = estimate_probabilities(
        decline_reason=decline,
        customer_prior_success_rate=prior_success,
        customer_account_age_days=account_age,
        customer_most_recent_decline=most_recent_decline,
        amount_inr=amount,
        last_successful_rail=last_rail,
        recent_retry_count=recent_retry_cnt,
        failure_hour=failure_hour,
    )
    
    for a in actions:
        out = row["action_outcomes"][a]
        y_true = 1 if out["recovered"] else 0
        p_true = out["success_probability"]
        p_pred = preds.get(a, 0.0)
        results[a].append({
            "p_pred": p_pred,
            "y_true": y_true,
            "p_true": p_true,
            "decline_reason": decline,
            "amount_inr": amount,
            "cust": cust,
            "failure_hour": failure_hour,
        })

def compute_ece(p_preds, y_trues, n_bins=5):
    bins = [[] for _ in range(n_bins)]
    bin_size = 1.0 / n_bins
    for p, y in zip(p_preds, y_trues):
        idx = min(int(p / bin_size), n_bins - 1)
        bins[idx].append((p, y))
    
    ece = 0.0
    total = len(p_preds)
    bin_stats = []
    for i, b in enumerate(bins):
        if not b:
            continue
        avg_pred = sum(p for p, y in b) / len(b)
        avg_true = sum(y for p, y in b) / len(b)
        weight = len(b) / total
        ece += weight * abs(avg_pred - avg_true)
        bin_stats.append({
            "bin": f"[{i*bin_size:.2f}, {(i+1)*bin_size:.2f})",
            "count": len(b),
            "avg_pred": round(avg_pred, 4),
            "observed_rate": round(avg_true, 4),
            "gap": round(avg_pred - avg_true, 4),
        })
    return ece, bin_stats

for a in actions:
    data = results[a]
    n = len(data)
    y_trues = [d["y_true"] for d in data]
    p_preds = [d["p_pred"] for d in data]
    p_trues = [d["p_true"] for d in data]
    
    obs_rate = sum(y_trues) / n
    mean_pred = sum(p_preds) / n
    mean_true_p = sum(p_trues) / n
    
    brier = sum((p - y) ** 2 for p, y in zip(p_preds, y_trues)) / n
    mae_vs_true_p = sum(abs(p - pt) for p, pt in zip(p_preds, p_trues)) / n
    ece, bin_stats = compute_ece(p_preds, y_trues, n_bins=5)
    
    print(f"\n--- Action: {a} ---")
    print(f"Sample size: {n}")
    print(f"Observed success rate (binary): {obs_rate:.4f} ({sum(y_trues)}/{n})")
    print(f"Mean true hidden prob: {mean_true_p:.4f}")
    print(f"Predicted mean probability: {mean_pred:.4f}")
    print(f"Bias (mean_pred - obs_rate): {mean_pred - obs_rate:+.4f}")
    print(f"Bias vs hidden prob: {mean_pred - mean_true_p:+.4f}")
    print(f"Brier score (vs observed binary): {brier:.4f}")
    print(f"MAE vs hidden conditional probability: {mae_vs_true_p:.4f} ({mae_vs_true_p*100:.2f} pp)")
    print(f"Expected Calibration Error (ECE, 5 bins): {ece:.4f}")
    print("Calibration Bins:")
    for bs in bin_stats:
        print(f"  {bs['bin']}: N={bs['count']}, pred={bs['avg_pred']:.4f}, obs={bs['observed_rate']:.4f}, gap={bs['gap']:+.4f}")
