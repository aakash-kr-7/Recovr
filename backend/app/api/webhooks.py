"""Idempotent Razorpay webhook intake and recovery-outcome completion."""
import hashlib, hmac, uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.agent.executor import BatchSpendTracker, ExecutionStatus, execute
from app.agent.gate import route
from app.agent.reasoning import get_triage_decision
from app.agent.economics.scoring import score_recovery_options
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.audit_entry import AuditEntry
from app.models.recovery_decision import RecoveryDecisionRow
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.models.transaction import Transaction
from app.schemas.recovery import RecoveryContext
from app.schemas.triage import TriageAction, TriagePath
from app.schemas.webhook import RazorpayWebhookPayload
from app.services.customer_history import get_customer_history
from app.utils.money import paise_to_inr

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)
_live_spend_tracker = BatchSpendTracker(cap_inr=get_settings().batch_spend_cap_inr)

def _verify_signature(body, signature):
    expected = hmac.new(get_settings().razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def _outcome_name(status):
    return {ExecutionStatus.HELD: "held_for_review", ExecutionStatus.FAILED: "execution_failed", ExecutionStatus.PENDING: "pending"}.get(status, "pending")

def _complete_link_payment(db, payload):
    entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    outcome = db.scalar(select(RecoveryOutcomeRow).where(RecoveryOutcomeRow.provider_reference == entity.get("id")))
    if outcome is None: return {"status": "ignored", "reason": "unknown_collection_link"}
    if outcome.observed_success is not None: return {"status": "duplicate", "transaction_id": outcome.transaction_id}
    recovered = paise_to_inr(entity.get("amount_paid", entity.get("amount", 0)))
    outcome.execution_status, outcome.actual_recovered_inr, outcome.observed_success = ExecutionStatus.SUCCEEDED.value, recovered, recovered > 0
    outcome.net_recovered_inr, outcome.outcome_timestamp = recovered - outcome.action_cost_inr - outcome.risk_penalty_inr, datetime.utcnow()
    outcome.outcome_source = "razorpay.payment_link.paid"
    audit = db.scalar(select(AuditEntry).where(AuditEntry.transaction_id == outcome.transaction_id))
    if audit: audit.outcome = "recovered" if recovered >= outcome.amount_attempted else "partial_recovery"
    db.commit()
    return {"status": "outcome_completed", "transaction_id": outcome.transaction_id, "recovered_inr": recovered}

def _complete_link_failure(db, payload):
    entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    outcome = db.scalar(select(RecoveryOutcomeRow).where(RecoveryOutcomeRow.provider_reference == entity.get("id")))
    if outcome is None: return {"status": "ignored", "reason": "unknown_collection_link"}
    if outcome.observed_success is not None: return {"status": "duplicate", "transaction_id": outcome.transaction_id}
    outcome.execution_status, outcome.actual_recovered_inr, outcome.observed_success = ExecutionStatus.FAILED.value, 0.0, False
    outcome.net_recovered_inr, outcome.outcome_timestamp, outcome.outcome_source = -outcome.action_cost_inr - outcome.risk_penalty_inr, datetime.utcnow(), "razorpay.payment_link.expired"
    audit = db.scalar(select(AuditEntry).where(AuditEntry.transaction_id == outcome.transaction_id))
    if audit: audit.outcome = "not_recovered"
    db.commit()
    return {"status": "outcome_completed", "transaction_id": outcome.transaction_id, "recovered_inr": 0.0}

@router.post("/razorpay")
async def handle_razorpay_webhook(request: Request, x_razorpay_signature: str = Header(...), db: Session = Depends(get_db)):
    body = await request.body()
    if not _verify_signature(body, x_razorpay_signature): raise HTTPException(status_code=401, detail="Invalid webhook signature")
    payload = RazorpayWebhookPayload.model_validate_json(body)
    if payload.event == "payment_link.paid": return _complete_link_payment(db, payload.model_dump())
    if payload.event == "payment_link.expired": return _complete_link_failure(db, payload.model_dump())
    if payload.event != "payment.failed": return {"status": "ignored", "event": payload.event}
    entity, payment_id = payload.payload["payment"]["entity"], payload.payload["payment"]["entity"]["id"]
    existing = db.scalar(select(Transaction).where(Transaction.razorpay_payment_id == payment_id))
    if existing: return {"status": "duplicate", "transaction_id": existing.id}
    customer_id = entity.get("contact") or entity.get("email") or "unknown"
    transaction = Transaction(id=str(uuid.uuid4()), razorpay_payment_id=payment_id, amount_inr=paise_to_inr(entity["amount"]),
        decline_reason_raw=entity.get("error_description", "unknown"), decline_reason=_normalize_decline_reason(entity.get("error_code")),
        customer_id=customer_id, customer_history=get_customer_history(customer_id), failed_at=datetime.utcfromtimestamp(entity["created_at"]), is_synthetic=False, data_split="production")
    db.add(transaction)
    try: db.commit()
    except IntegrityError:
        db.rollback(); existing = db.scalar(select(Transaction).where(Transaction.razorpay_payment_id == payment_id))
        return {"status": "duplicate", "transaction_id": existing.id}
    gate = route(transaction)
    if gate.path == TriagePath.DETERMINISTIC: candidate, text, confidence = gate.fast_path_action, gate.fast_path_reasoning, None
    else:
        try:
            llm = get_triage_decision(transaction); candidate, text, confidence = llm.action, llm.reasoning_text, llm.confidence
        except Exception as exc:
            logger.exception("LLM decision failed for %s", transaction.id)
            candidate, text, confidence = None, f"LLM unavailable ({type(exc).__name__}); economics fallback.", None
    context = RecoveryContext(amount_inr=transaction.amount_inr, decline_reason=transaction.decline_reason,
        customer_prior_success_rate=transaction.customer_history.get("prior_success_rate", transaction.customer_history.get("success_rate")),
        customer_account_age_days=transaction.customer_history.get("account_age_days"), recent_retry_count=transaction.customer_history.get("recent_retry_count"), failure_hour=transaction.failed_at.hour,
        llm_insights=llm.insights if 'llm' in locals() else None)
    economics = score_recovery_options(transaction_id=transaction.id, permitted_actions=list(TriageAction), context=context)
    selected_action = economics.selected_action
    if candidate is None and gate.path == TriagePath.REASONING:
        # The economics result remains recorded in RecoveryDecisionRow, but
        # an unavailable/malformed LLM must never authorize a real action.
        selected_action = TriageAction.HOLD_FOR_REVIEW
        text += " [Held: no safe automatic decision after LLM failure.]"
    elif candidate != economics.selected_action:
        text = f"Path suggested {candidate.value}; economics selected {economics.selected_action.value}. {text}"
    result = execute(transaction, gate.path, selected_action, text, confidence, _live_spend_tracker, economics.options, economics.selected_expected_net_recovery_inr, economics.value_advantage_vs_next_best_inr, db=db)
    option = next((o for o in economics.options if o.action == result.action), None)
    db.add(AuditEntry(transaction_id=transaction.id, path_taken=result.decision_path.value, action=result.action.value, reasoning_text=result.reasoning_text, confidence=result.confidence, was_gated=result.was_gated, amount_inr=transaction.amount_inr, outcome=_outcome_name(result.status)))
    db.add(RecoveryDecisionRow(transaction_id=transaction.id, options_json=[o.model_dump() for o in result.options], selected_action=result.action.value, selected_expected_net_recovery_inr=result.selected_expected_net_recovery_inr, value_advantage_vs_next_best_inr=result.value_advantage_vs_next_best_inr, confidence=result.confidence, reasoning_text=result.reasoning_text, decision_path=result.decision_path.value, was_gated=result.was_gated))
    db.add(RecoveryOutcomeRow(transaction_id=transaction.id, action=result.action.value, execution_status=result.status.value, actual_recovered_inr=None, observed_success=None, variance_inr=None, outcome_timestamp=result.completed_at or result.attempted_at, provider=result.provider, provider_reference=result.provider_reference, mode=result.mode.value, amount_attempted=result.amount_attempted, action_cost_inr=result.action_cost_inr, risk_penalty_inr=option.risk_penalty_inr if option else 0.0, net_recovered_inr=None, error_code=result.error_code, error_message=result.error_message, outcome_source="executor"))
    db.commit()
    return {"status": "processed", "transaction_id": transaction.id, "execution_status": result.status.value, "provider_reference": result.provider_reference}

def _normalize_decline_reason(error_code): return error_code.lower() if error_code else "unknown"
