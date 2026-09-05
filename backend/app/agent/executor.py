"""Policy-enforced recovery execution.

Razorpay cannot retry a failed payment through its Payments API. The sole
real operation exposed here is a standard Payment Link collection request for
``escalate_to_dunning``. It is never called a recovered payment until a
later Razorpay event confirms payment.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction
from app.schemas.recovery import RecoveryDecision, RecoveryOption
from app.schemas.triage import TriageAction, TriagePath
from app.services.razorpay_client import RazorpayTestModeClient

logger = get_logger(__name__)


class ExecutionMode(str, Enum):
    REAL_RAZORPAY_ACTION = "REAL_RAZORPAY_ACTION"
    BOUNDED_SIMULATION = "BOUNDED_SIMULATION"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    HELD = "HELD"
    SIMULATED = "SIMULATED"


@dataclass
class BatchSpendTracker:
    """Tracks actual known provider action cost, never transaction amount."""
    cap_inr: float
    spent_inr: float = field(default=0.0)
    def can_spend(self, amount_inr: float) -> bool: return self.spent_inr + amount_inr <= self.cap_inr
    def record(self, amount_inr: float) -> None: self.spent_inr += amount_inr


@dataclass
class ExecutionResult:
    decision: RecoveryDecision
    action: TriageAction
    status: ExecutionStatus
    provider: str | None
    provider_reference: str | None
    attempted_at: datetime
    completed_at: datetime | None
    amount_attempted: float
    action_cost_inr: float
    error_code: str | None = None
    error_message: str | None = None
    mode: ExecutionMode = ExecutionMode.BOUNDED_SIMULATION

    # Temporary compatibility for the unchanged evaluation harness.
    def __getattr__(self, name): return getattr(self.decision, name)


def _decision(txn, path, action, text, confidence, options, expected, advantage, gated=False):
    return RecoveryDecision(transaction_id=txn.id, options=options, selected_action=action,
        selected_expected_net_recovery_inr=expected, value_advantage_vs_next_best_inr=advantage,
        decision_path=path, reasoning_text=text, confidence=confidence, was_gated=gated)


def _retry_limit_reached(db: Session | None, txn: Transaction, limit: int) -> bool:
    if db is None:
        return False
    attempts = db.scalar(select(func.count()).select_from(RecoveryOutcomeRow).join(
        Transaction, RecoveryOutcomeRow.transaction_id == Transaction.id
    ).where(Transaction.customer_id == txn.customer_id,
            RecoveryOutcomeRow.mode == ExecutionMode.REAL_RAZORPAY_ACTION.value,
            RecoveryOutcomeRow.action == TriageAction.ESCALATE_TO_DUNNING.value)) or 0
    return attempts >= limit


def execute(transaction: Transaction, path: TriagePath, action: TriageAction, reasoning_text: str,
            confidence: float | None, spend_tracker: BatchSpendTracker, options: list[RecoveryOption],
            selected_expected_net_recovery_inr: float, value_advantage_vs_next_best_inr: float,
            db: Session | None = None, client: RazorpayTestModeClient | None = None) -> ExecutionResult:
    settings, now = get_settings(), datetime.now(timezone.utc)
    final_action, gated, suffix = action, False, ""
    if path == TriagePath.REASONING and confidence is not None and confidence < settings.min_auto_execute_confidence:
        final_action, gated, suffix = TriageAction.HOLD_FOR_REVIEW, True, " [Gated: confidence below auto-execute threshold.]"
    elif action == TriageAction.ESCALATE_TO_DUNNING and _retry_limit_reached(db, transaction, settings.max_customer_recovery_attempts):
        final_action, gated, suffix = TriageAction.HOLD_FOR_REVIEW, True, " [Gated: per-customer recovery attempt limit reached.]"
    decision = _decision(transaction, path, final_action, reasoning_text + suffix, confidence, options,
                         selected_expected_net_recovery_inr, value_advantage_vs_next_best_inr, gated)
    if final_action == TriageAction.HOLD_FOR_REVIEW:
        return ExecutionResult(decision, final_action, ExecutionStatus.HELD, None, None, now, now, 0.0, 0.0)
    # Only allowed real mapping. Retry-in-place and rail switching are not Razorpay APIs.
    if final_action != TriageAction.ESCALATE_TO_DUNNING or transaction.is_synthetic:
        return ExecutionResult(decision, final_action, ExecutionStatus.SIMULATED, None, None, now, now,
                               0.0, 0.0, mode=ExecutionMode.BOUNDED_SIMULATION)
    # Payment-link creation has no provider fee at request time; simulations never count.
    actual_provider_cost = 0.0
    if not spend_tracker.can_spend(actual_provider_cost):
        held = _decision(transaction, path, TriageAction.HOLD_FOR_REVIEW, reasoning_text + " [Gated: provider spend cap.]", confidence, options, selected_expected_net_recovery_inr, value_advantage_vs_next_best_inr, True)
        return ExecutionResult(held, TriageAction.HOLD_FOR_REVIEW, ExecutionStatus.HELD, None, None, now, now, 0.0, 0.0)
    try:
        link = (client or RazorpayTestModeClient()).create_collection_link(
            transaction.razorpay_payment_id or transaction.id, transaction.amount_inr, transaction.customer_id)
        if not isinstance(link, dict) or not isinstance(link.get("id"), str) or not link["id"]:
            raise ValueError("Razorpay Payment Link response lacks a usable id")
        spend_tracker.record(actual_provider_cost)
        return ExecutionResult(decision, final_action, ExecutionStatus.PENDING, "razorpay", link["id"], now,
            datetime.now(timezone.utc), transaction.amount_inr, actual_provider_cost, mode=ExecutionMode.REAL_RAZORPAY_ACTION)
    except Exception as exc:
        logger.exception("Razorpay collection-link creation failed for %s", transaction.id)
        return ExecutionResult(decision, final_action, ExecutionStatus.FAILED, "razorpay", None, now,
            datetime.now(timezone.utc), transaction.amount_inr, actual_provider_cost, "razorpay_request_failed", str(exc),
            ExecutionMode.REAL_RAZORPAY_ACTION)
