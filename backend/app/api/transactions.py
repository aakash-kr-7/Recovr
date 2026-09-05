"""
Read-only endpoints the dashboard uses for the live decision feed and the
audit trail view. No write endpoints here — all writes happen through the
webhook intake path or the evaluation script, never directly via this API.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_entry import AuditEntry
from app.models.recovery_decision import RecoveryDecisionRow
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _serialize_options(options_json: list[dict] | None) -> list[dict] | None:
    """Return the saved economic ranking exactly as it was scored.

    This is a read-only API projection.  Keeping every component visible
    lets the operations console distinguish expected gross, cost, risk and
    expected net instead of inventing a client-side calculation.
    """
    if not options_json:
        return None
    return [
        opt
        for opt in options_json
    ]


@router.get("/recent")
def get_recent_transactions(limit: int = 50, db: Session = Depends(get_db)):
    """Feeds the dashboard's live decision feed. Joins transaction,
    audit_entry, and (outer) recovery_decision so the frontend gets
    decline reason + decision + reasoning + economic ranking in one
    call rather than needing multiple round trips."""
    stmt = (
        select(Transaction, AuditEntry, RecoveryDecisionRow, RecoveryOutcomeRow)
        .join(AuditEntry, AuditEntry.transaction_id == Transaction.id)
        .outerjoin(
            RecoveryDecisionRow,
            RecoveryDecisionRow.transaction_id == Transaction.id,
        )
        .outerjoin(
            RecoveryOutcomeRow,
            RecoveryOutcomeRow.transaction_id == Transaction.id,
        )
        .order_by(AuditEntry.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "transaction_id": txn.id,
            "amount_inr": txn.amount_inr,
            "decline_reason": txn.decline_reason,
            "decline_reason_raw": txn.decline_reason_raw,
            "is_synthetic": txn.is_synthetic,
            "path_taken": entry.path_taken,
            "action": entry.action,
            "reasoning_text": entry.reasoning_text,
            "confidence": entry.confidence,
            "was_gated": entry.was_gated,
            "outcome": entry.outcome,
            "created_at": entry.created_at.isoformat(),
            # Economic layer fields — null when no RecoveryDecisionRow
            # exists (pre-economic-layer transactions).
            "recovery_options": (
                _serialize_options(decision.options_json)
                if decision is not None
                else None
            ),
            "selected_expected_net_recovery_inr": (
                decision.selected_expected_net_recovery_inr
                if decision is not None
                else None
            ),
            "value_advantage_vs_next_best_inr": (
                decision.value_advantage_vs_next_best_inr
                if decision is not None
                else None
            ),
            "recovery_outcome": (
                {
                    "execution_status": outcome.execution_status,
                    "actual_recovered_inr": outcome.actual_recovered_inr,
                    "observed_success": outcome.observed_success,
                    "variance_inr": outcome.variance_inr,
                    "outcome_timestamp": outcome.outcome_timestamp.isoformat(),
                    "provider": outcome.provider,
                    "provider_reference": outcome.provider_reference,
                    "mode": outcome.mode,
                    "net_recovered_inr": outcome.net_recovered_inr,
                    "error_code": outcome.error_code,
                    "error_message": outcome.error_message,
                }
                if outcome is not None
                else None
            ),
        }
        for txn, entry, decision, outcome in rows
    ]


@router.get("/audit/{transaction_id}")
def get_audit_entry(transaction_id: str, db: Session = Depends(get_db)):
    """Full audit detail for a single transaction — used by the
    dashboard's audit trail detail view."""
    stmt = (
        select(Transaction, AuditEntry, RecoveryDecisionRow, RecoveryOutcomeRow)
        .join(AuditEntry, AuditEntry.transaction_id == Transaction.id)
        .outerjoin(RecoveryDecisionRow, RecoveryDecisionRow.transaction_id == Transaction.id)
        .outerjoin(RecoveryOutcomeRow, RecoveryOutcomeRow.transaction_id == Transaction.id)
        .where(Transaction.id == transaction_id)
    )
    row = db.execute(stmt).one_or_none()
    if row is None:
        return {"error": "not_found"}
    txn, entry, decision, outcome = row
    return {
        "transaction_id": entry.transaction_id,
        "path_taken": entry.path_taken,
        "action": entry.action,
        "reasoning_text": entry.reasoning_text,
        "confidence": entry.confidence,
        "was_gated": entry.was_gated,
        "outcome": entry.outcome,
        "amount_inr": entry.amount_inr,
        "created_at": entry.created_at.isoformat(),
        "payment_id": txn.razorpay_payment_id,
        "failed_at": txn.failed_at.isoformat(),
        "decline_reason": txn.decline_reason,
        "decline_reason_raw": txn.decline_reason_raw,
        "customer_id": txn.customer_id,
        "customer_history": txn.customer_history,
        "is_synthetic": txn.is_synthetic,
        "recovery_options": _serialize_options(decision.options_json) if decision else None,
        "selected_expected_net_recovery_inr": (
            decision.selected_expected_net_recovery_inr if decision else None
        ),
        "value_advantage_vs_next_best_inr": (
            decision.value_advantage_vs_next_best_inr if decision else None
        ),
        "recovery_outcome": (
            {
                "execution_status": outcome.execution_status,
                "actual_recovered_inr": outcome.actual_recovered_inr,
                "observed_success": outcome.observed_success,
                "variance_inr": outcome.variance_inr,
                "outcome_timestamp": outcome.outcome_timestamp.isoformat(),
                "provider": outcome.provider,
                "provider_reference": outcome.provider_reference,
                "mode": outcome.mode,
                "net_recovered_inr": outcome.net_recovered_inr,
                "error_code": outcome.error_code,
                "error_message": outcome.error_message,
            }
            if outcome else None
        ),
    }
