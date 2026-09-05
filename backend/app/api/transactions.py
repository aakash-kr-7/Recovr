"""
Read-only endpoints the dashboard uses for the live decision feed and the
audit trail view. No write endpoints here — all writes happen through the
webhook intake path or the evaluation script, never directly via this API.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, or_, select
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


@router.get("/funnel-summary")
def get_funnel_summary(scope: str = "session", db: Session = Depends(get_db)):
    """Aggregate the failure/recovery funnel for the selected scope.

    scope='session' (default): restricts aggregates to the active session
    (data_split == 'live_mode'), ensuring KPI cards, funnel, and timeline share
    the exact same session boundary without blending historical seed runs.
    scope='all': aggregates across all historical transactions ever recorded.

    RECOVERY RATE HONESTY:
    Transactions still sitting in hold_for_review awaiting resolution are
    explicitly excluded from the recovery rate denominator — they are pending,
    not failures. The recovery rate is computed over resolved cases only, and
    the pending review count/volume are returned alongside it.
    """
    is_session = scope.lower() == "session"

    failed_or_unresolved = or_(
        RecoveryOutcomeRow.observed_success.is_(None),
        RecoveryOutcomeRow.observed_success.is_(False),
    )

    # Pending review definition: transactions currently sitting in hold_for_review
    # awaiting resolution (observed_success is None). These are NOT failed recoveries.
    is_pending_review = and_(
        RecoveryOutcomeRow.observed_success.is_(None),
        or_(
            RecoveryOutcomeRow.action == "hold_for_review",
            RecoveryOutcomeRow.execution_status == "HELD",
            AuditEntry.action == "hold_for_review",
            RecoveryOutcomeRow.action.is_distinct_from("no_action"),
        ),
    )

    # Resolved definition: transactions with a known outcome (success or failure)
    # or confirmed non-recoverable (no_action), explicitly excluding pending review.
    is_resolved = or_(
        RecoveryOutcomeRow.observed_success.is_not(None),
        and_(
            RecoveryOutcomeRow.action == "no_action",
            ~is_pending_review,
        ),
    )

    query = select(
        func.coalesce(func.sum(Transaction.amount_inr), 0.0).label("attempted_volume_inr"),
        func.coalesce(
            func.sum(case((failed_or_unresolved, Transaction.amount_inr), else_=0.0)),
            0.0,
        ).label("failed_volume_inr"),
        func.coalesce(
            func.sum(
                case(
                    (
                        RecoveryOutcomeRow.observed_success.is_(True),
                        func.coalesce(RecoveryOutcomeRow.actual_recovered_inr, 0.0),
                    ),
                    else_=0.0,
                )
            ),
            0.0,
        ).label("recovered_volume_inr"),
        func.count(Transaction.id).label("transaction_count"),
        # Pending review metrics
        func.coalesce(
            func.sum(case((is_pending_review, 1), else_=0)),
            0,
        ).label("pending_review_count"),
        func.coalesce(
            func.sum(case((is_pending_review, Transaction.amount_inr), else_=0.0)),
            0.0,
        ).label("pending_review_volume_inr"),
        # Resolved metrics
        func.coalesce(
            func.sum(case((is_resolved, 1), else_=0)),
            0,
        ).label("resolved_count"),
        func.coalesce(
            func.sum(case((is_resolved, Transaction.amount_inr), else_=0.0)),
            0.0,
        ).label("resolved_volume_inr"),
        # Expected recovery
        func.coalesce(
            func.sum(func.coalesce(RecoveryDecisionRow.selected_expected_net_recovery_inr, 0.0)),
            0.0,
        ).label("expected_recovery_inr"),
    ).select_from(Transaction).outerjoin(
        AuditEntry,
        AuditEntry.transaction_id == Transaction.id,
    ).outerjoin(
        RecoveryDecisionRow,
        RecoveryDecisionRow.transaction_id == Transaction.id,
    ).outerjoin(
        RecoveryOutcomeRow,
        RecoveryOutcomeRow.transaction_id == Transaction.id,
    )

    if is_session:
        query = query.where(Transaction.data_split == "live_mode")

    (
        attempted_volume_inr,
        failed_volume_inr,
        recovered_volume_inr,
        transaction_count,
        pending_review_count,
        pending_review_volume_inr,
        resolved_count,
        resolved_volume_inr,
        expected_recovery_inr,
    ) = db.execute(query).one()

    recovery_rate_pct = (
        round((float(recovered_volume_inr) / float(resolved_volume_inr)) * 100, 1)
        if float(resolved_volume_inr) > 0
        else None
    )

    timeline_query = (
        select(
            RecoveryOutcomeRow.outcome_timestamp,
            RecoveryOutcomeRow.actual_recovered_inr,
        )
        .join(Transaction, RecoveryOutcomeRow.transaction_id == Transaction.id)
        .where(
            RecoveryOutcomeRow.observed_success.is_(True),
            RecoveryOutcomeRow.actual_recovered_inr.is_not(None),
        )
    )

    if is_session:
        timeline_query = timeline_query.where(Transaction.data_split == "live_mode")
        start_time_query = (
            select(func.min(AuditEntry.created_at))
            .join(Transaction, AuditEntry.transaction_id == Transaction.id)
            .where(Transaction.data_split == "live_mode")
        )
    else:
        start_time_query = select(func.min(AuditEntry.created_at))

    timeline_started_at = db.scalar(start_time_query)
    recovery_rows = db.execute(
        timeline_query.order_by(RecoveryOutcomeRow.outcome_timestamp.asc())
    ).all()

    cumulative_recovered = 0.0
    recovery_timeline = []
    if timeline_started_at is not None:
        recovery_timeline.append(
            {
                "timestamp": timeline_started_at.isoformat(),
                "cumulative_recovered_inr": cumulative_recovered,
            }
        )
    for outcome_timestamp, actual_recovered_inr in recovery_rows:
        cumulative_recovered += float(actual_recovered_inr)
        recovery_timeline.append(
            {
                "timestamp": outcome_timestamp.isoformat(),
                "cumulative_recovered_inr": cumulative_recovered,
            }
        )

    return {
        "scope": "session" if is_session else "all",
        "attempted_volume_inr": float(attempted_volume_inr),
        "failed_volume_inr": float(failed_volume_inr),
        "recovered_volume_inr": float(recovered_volume_inr),
        "transaction_count": int(transaction_count),
        "recovery_timeline": recovery_timeline,
        "pending_review_count": int(pending_review_count),
        "pending_review_volume_inr": float(pending_review_volume_inr),
        "resolved_count": int(resolved_count),
        "resolved_volume_inr": float(resolved_volume_inr),
        "recovery_rate_pct": recovery_rate_pct,
        "expected_recovery_inr": float(expected_recovery_inr),
    }


@router.get("/recent")
def get_recent_transactions(limit: int = 50, scope: str = "session", db: Session = Depends(get_db)):
    """Feeds the dashboard's live decision feed. Joins transaction,
    audit_entry, and (outer) recovery_decision so the frontend gets
    decline reason + decision + reasoning + economic ranking in one
    call rather than needing multiple round trips.

    Filters by scope ('session' -> live_mode, 'all' -> all history).
    """
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
    )
    if scope.lower() == "session":
        stmt = stmt.where(Transaction.data_split == "live_mode")

    stmt = stmt.order_by(AuditEntry.created_at.desc()).limit(limit)
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
