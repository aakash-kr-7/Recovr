#!/usr/bin/env python
"""
Generates the labeled synthetic dataset used for development and
evaluation. See docs/architecture/evaluation.md for the full methodology
this script implements.

Usage:
    python scripts/generate_synthetic_data.py [--count N] [--seed S]

Writes:
    data/synthetic/transactions.json   (70% — development/working set)
    data/eval/holdout.json             (30% — never read outside
                                         run_evaluation.py; the checksum
                                         printed on generation is logged
                                         so any later regeneration is
                                         visible)

IMPORTANT: the labeling function below (`assign_ground_truth`) is
deliberately kept separate from anything app/agent/* uses, so the label
can't accidentally encode the same assumptions the system being graded
makes. If you find yourself importing from app.agent in this file, stop
— that would quietly invalidate the evaluation.
"""

import argparse
import hashlib
import json
import random
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

# Decline reason distribution. Rough weights based on commonly discussed
# failure-category proportions in payment recovery write-ups (Razorpay's
# and Stripe's own blogs) — NOT a precise citation, just a plausible
# starting shape. Documented here so it's clear this is a modeling choice,
# not a measured fact.
DECLINE_REASONS_WEIGHTED = [
    ("insufficient_funds", 0.28),
    ("bank_timeout", 0.18),
    ("authentication_failed", 0.14),
    ("issuer_unavailable", 0.10),
    ("card_expired", 0.10),
    ("card_reported_lost_or_stolen", 0.06),
    ("account_closed", 0.05),
    ("invalid_card_number", 0.05),
    ("compliance_block", 0.02),
    ("some_unmapped_bank_specific_code_47B", 0.02),  # deliberately novel/unmapped
]

HISTORY_PATTERNS = ["clean_history", "first_time_customer", "repeat_insufficient_funds",
                     "mixed_history", "long_dormant_then_active"]

# These are *synthetic environment* parameters, not RECOVR probability
# heuristics.  They describe how the simulated world responds to each action
# after a failure.  They intentionally live in the data generator so the
# decision engine cannot import or observe them.
ACTION_VALUES = (
    "retry_same_rail",
    "retry_alt_rail",
    "hold_for_review",
    "escalate_to_dunning",
    "no_action",
)

_ACTION_COSTS = {
    "retry_same_rail": 8.0,
    "retry_alt_rail": 10.0,
    "hold_for_review": 6.0,       # simulated manual-review operating cost
    "escalate_to_dunning": 4.0,   # simulated message/collections cost
    "no_action": 0.0,
}

_BASE_SUCCESS_PROBABILITIES = {
    "insufficient_funds": {
        "retry_same_rail": 0.30, "retry_alt_rail": 0.12,
        "hold_for_review": 0.10, "escalate_to_dunning": 0.18,
    },
    "bank_timeout": {
        "retry_same_rail": 0.36, "retry_alt_rail": 0.31,
        "hold_for_review": 0.12, "escalate_to_dunning": 0.06,
    },
    "authentication_failed": {
        "retry_same_rail": 0.16, "retry_alt_rail": 0.25,
        "hold_for_review": 0.28, "escalate_to_dunning": 0.10,
    },
    "issuer_unavailable": {
        "retry_same_rail": 0.31, "retry_alt_rail": 0.27,
        "hold_for_review": 0.14, "escalate_to_dunning": 0.05,
    },
    "card_expired": {
        "retry_same_rail": 0.01, "retry_alt_rail": 0.10,
        "hold_for_review": 0.14, "escalate_to_dunning": 0.38,
    },
    "card_reported_lost_or_stolen": {
        "retry_same_rail": 0.0, "retry_alt_rail": 0.06,
        "hold_for_review": 0.27, "escalate_to_dunning": 0.22,
    },
    "account_closed": {
        "retry_same_rail": 0.0, "retry_alt_rail": 0.0,
        "hold_for_review": 0.03, "escalate_to_dunning": 0.04,
    },
    "invalid_card_number": {
        "retry_same_rail": 0.0, "retry_alt_rail": 0.03,
        "hold_for_review": 0.17, "escalate_to_dunning": 0.04,
    },
    "compliance_block": {
        "retry_same_rail": 0.0, "retry_alt_rail": 0.0,
        "hold_for_review": 0.24, "escalate_to_dunning": 0.0,
    },
    "some_unmapped_bank_specific_code_47B": {
        "retry_same_rail": 0.08, "retry_alt_rail": 0.10,
        "hold_for_review": 0.31, "escalate_to_dunning": 0.07,
    },
}


@dataclass
class SyntheticTransaction:
    id: str
    amount_inr: float
    decline_reason_raw: str
    decline_reason: str
    customer_id: str
    customer_history: dict
    failed_at: str
    is_synthetic: bool
    ground_truth_label: str
    action_outcomes: dict
    generator_seed: int
    data_split: str = "working"


def _weighted_choice(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in weighted)
    r = rng.uniform(0, total)
    upto = 0.0
    for value, weight in weighted:
        upto += weight
        if upto >= r:
            return value
    return weighted[-1][0]


def _build_customer_history(rng: random.Random, pattern: str) -> dict:
    if pattern == "first_time_customer":
        return {
            "prior_transaction_count": 0,
            "prior_success_rate": None,
            "most_recent_decline_reason": None,
            "account_age_days": rng.randint(0, 3),
            "last_successful_rail": None,
            "recent_retry_count": 0,
        }
    if pattern == "clean_history":
        count = rng.randint(3, 15)
        return {
            "prior_transaction_count": count,
            "prior_success_rate": round(rng.uniform(0.9, 1.0), 2),
            "most_recent_decline_reason": None,
            "account_age_days": rng.randint(60, 800),
            "last_successful_rail": rng.choice(["card", "upi"]),
            "recent_retry_count": rng.randint(0, 1),
        }
    if pattern == "repeat_insufficient_funds":
        count = rng.randint(2, 8)
        return {
            "prior_transaction_count": count,
            "prior_success_rate": round(rng.uniform(0.2, 0.5), 2),
            "most_recent_decline_reason": "insufficient_funds",
            "account_age_days": rng.randint(10, 200),
            "last_successful_rail": rng.choice(["card", "upi"]),
            "recent_retry_count": rng.randint(1, 3),
        }
    if pattern == "mixed_history":
        count = rng.randint(4, 20)
        return {
            "prior_transaction_count": count,
            "prior_success_rate": round(rng.uniform(0.5, 0.85), 2),
            "most_recent_decline_reason": rng.choice(
                ["bank_timeout", "authentication_failed", None]
            ),
            "account_age_days": rng.randint(30, 600),
            "last_successful_rail": rng.choice(["card", "upi"]),
            "recent_retry_count": rng.randint(0, 2),
        }
    # long_dormant_then_active
    return {
        "prior_transaction_count": rng.randint(1, 3),
        "prior_success_rate": 1.0,
        "most_recent_decline_reason": None,
        "account_age_days": rng.randint(400, 1200),
        "last_successful_rail": rng.choice(["card", "upi"]),
        "recent_retry_count": rng.randint(0, 1),
    }


def _clamp_probability(value: float) -> float:
    return max(0.0, min(0.95, value))


def generate_action_outcomes(
    decline_reason: str,
    customer_history: dict,
    amount_inr: float,
    failure_hour: int,
    rng: random.Random,
) -> dict[str, dict]:
    """Generate hidden potential outcomes for every permitted action.

    This is the synthetic world's ground truth.  It is deliberately
    independent of app.agent: RECOVR receives only the transaction context,
    never this dictionary.  Each outcome is a realized counterfactual for
    one action, allowing evaluation to compare a selected action with the
    best action that could have been taken on that same transaction.
    """
    base = _BASE_SUCCESS_PROBABILITIES[decline_reason]
    prior_success = customer_history.get("prior_success_rate")
    repeats = customer_history.get("recent_retry_count", 0)
    recent_same_decline = (
        customer_history.get("most_recent_decline_reason") == decline_reason
    )
    off_hours = failure_hour < 6 or failure_hour >= 22
    outcomes: dict[str, dict] = {}

    for action in ACTION_VALUES:
        if action == "no_action":
            outcomes[action] = {
                "success_probability": 0.0,
                "recovered": False,
                "recovery_amount_if_success_inr": 0.0,
                "recovered_amount_inr": 0.0,
                "action_cost_inr": 0.0,
                "risk_penalty_inr": 0.0,
                "net_recovered_inr": 0.0,
            }
            continue

        probability = base[action]
        if prior_success is not None:
            if prior_success >= 0.8 and action in {"retry_same_rail", "retry_alt_rail"}:
                probability += 0.10
            elif prior_success < 0.35 and action in {"retry_same_rail", "retry_alt_rail"}:
                probability -= 0.10
            if prior_success >= 0.75 and action == "escalate_to_dunning":
                probability += 0.05
        if recent_same_decline:
            if action == "retry_same_rail":
                probability -= 0.14
            elif action == "retry_alt_rail":
                probability += 0.08
            elif action == "escalate_to_dunning":
                probability += 0.08
        if repeats >= 2 and action == "retry_same_rail":
            probability -= 0.10
        if customer_history.get("last_successful_rail") == "upi" and action == "retry_alt_rail":
            probability += 0.08
        if off_hours:
            if action == "retry_same_rail" and decline_reason in {"bank_timeout", "issuer_unavailable"}:
                probability += 0.07
            if action == "hold_for_review":
                probability -= 0.05
        if amount_inr < 500 and action == "hold_for_review":
            probability -= 0.08
        if amount_inr > 5000 and action == "hold_for_review":
            probability += 0.07

        probability = _clamp_probability(probability + rng.uniform(-0.06, 0.06))
        recovered = rng.random() < probability
        # The simulated recovery amount is action-specific: dunning/review
        # may collect a partial amount, while a successful retry is near-full.
        recovery_fraction = {
            "retry_same_rail": 1.0,
            "retry_alt_rail": 0.98,
            "hold_for_review": 0.90,
            "escalate_to_dunning": 0.82,
        }[action]
        recovery_amount_if_success = round(amount_inr * recovery_fraction, 2)
        recovered_amount = recovery_amount_if_success if recovered else 0.0
        risk_penalty = 0.0
        if action in {"retry_same_rail", "retry_alt_rail"} and (
            decline_reason in {"compliance_block", "card_reported_lost_or_stolen"}
        ):
            risk_penalty = 50.0
        elif action == "retry_same_rail" and (recent_same_decline or repeats >= 2):
            risk_penalty = 5.0
        elif action == "hold_for_review" and amount_inr > 5000:
            risk_penalty = 2.0  # simulated delay/opportunity cost

        cost = _ACTION_COSTS[action]
        outcomes[action] = {
            "success_probability": round(probability, 4),
            "recovered": recovered,
            "recovery_amount_if_success_inr": recovery_amount_if_success,
            "recovered_amount_inr": recovered_amount,
            "action_cost_inr": cost,
            "risk_penalty_inr": risk_penalty,
            "net_recovered_inr": round(recovered_amount - cost - risk_penalty, 2),
        }
    return outcomes


def assign_ground_truth(action_outcomes: dict[str, dict]) -> str:
    """Return the canonical best realized action from hidden outcomes.

    `ground_truth_label` remains for compatibility, but now derives from
    action-level realized net outcomes rather than decline-code rules.
    Ties use a fixed order only to make the generated dataset reproducible;
    evaluation separately treats every tied max-net action as optimal.
    """
    return max(
        ACTION_VALUES,
        key=lambda action: action_outcomes[action]["net_recovered_inr"],
    )


def generate(count: int, seed: int) -> list[SyntheticTransaction]:
    rng = random.Random(seed)
    transactions = []
    base_time = datetime(2026, 8, 1)

    for _ in range(count):
        decline_reason = _weighted_choice(rng, DECLINE_REASONS_WEIGHTED)
        pattern = rng.choice(HISTORY_PATTERNS)
        history = _build_customer_history(rng, pattern)
        amount_inr = round(rng.uniform(199, 15000), 2)
        failure_time = base_time + timedelta(hours=rng.randint(0, 24 * 30))
        outcomes = generate_action_outcomes(
            decline_reason, history, amount_inr, failure_time.hour, rng
        )
        ground_truth = assign_ground_truth(outcomes)

        transactions.append(
            SyntheticTransaction(
                # IDs are derived from the seeded RNG too, so the complete
                # dataset (not merely its distributions) is reproducible.
                id=str(uuid.UUID(int=rng.getrandbits(128))),
                amount_inr=amount_inr,
                decline_reason_raw=decline_reason.replace("_", " ").title(),
                decline_reason=decline_reason,
                customer_id=f"synthetic_cust_{rng.getrandbits(32):08x}",
                customer_history=history,
                failed_at=failure_time.isoformat(),
                is_synthetic=True,
                ground_truth_label=ground_truth,
                action_outcomes=outcomes,
                generator_seed=seed,
            )
        )
    return transactions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    transactions = generate(args.count, args.seed)
    rng = random.Random(args.seed)
    rng.shuffle(transactions)

    split_idx = int(len(transactions) * 0.7)
    working_set = transactions[:split_idx]
    holdout_set = transactions[split_idx:]
    for t in working_set:
        t.data_split = "working"
    for t in holdout_set:
        t.data_split = "holdout"

    repo_root = Path(__file__).parent.parent
    synthetic_dir = repo_root / "data" / "synthetic"
    eval_dir = repo_root / "data" / "eval"
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    working_path = synthetic_dir / "transactions.json"
    holdout_path = eval_dir / "holdout.json"

    working_json = json.dumps([asdict(t) for t in working_set], indent=2)
    holdout_json = json.dumps([asdict(t) for t in holdout_set], indent=2)

    working_path.write_text(working_json)
    holdout_path.write_text(holdout_json)

    holdout_checksum = hashlib.sha256(holdout_json.encode()).hexdigest()[:16]

    print(f"Generated {len(transactions)} synthetic transactions "
          f"(seed={args.seed}).")
    print(f"  Working set: {len(working_set)} -> {working_path}")
    print(f"  Holdout set: {len(holdout_set)} -> {holdout_path}")
    print(f"  Holdout checksum (sha256, first 16 chars): {holdout_checksum}")
    print(
        "  Record this checksum. If it changes later without you "
        "deliberately regenerating, the holdout set was not held out."
    )


if __name__ == "__main__":
    sys.exit(main())
