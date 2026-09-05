from pydantic import BaseModel, Field
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from datetime import datetime
import asyncio

from app.db.session import get_db, SessionLocal
from app.models.transaction import Transaction
from app.models.audit_entry import AuditEntry
from app.models.recovery_decision import RecoveryDecisionRow
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.agent.gate import route
from app.agent.reasoning import get_triage_decision
from app.agent.economics.historical_evidence import query_historical_evidence
from app.agent.economics.scoring import score_recovery_options
from app.agent.executor import execute
from app.core.logging import get_logger
from app.schemas.triage import TriageAction, TriagePath
from app.schemas.recovery import RecoveryContext
from app.services.customer_history import get_customer_history
from app.agent.rules.decline_taxonomy import FAST_PATH_TABLE, ROUTED_TO_REASONING_PATH
from app.api.webhooks import _live_spend_tracker, _outcome_name

router = APIRouter(prefix="/demo", tags=["demo"])
logger = get_logger(__name__)

class DemoSimulateRequest(BaseModel):
    amount_inr: float
    decline_reason: str
    decline_reason_raw: Optional[str] = None
    customer_id: Optional[str] = None
    customer_history: Optional[dict] = None

class LiveModeStartRequest(BaseModel):
    """Controls playback pace only; it never changes the decision pipeline."""

    interval_seconds: float = Field(default=5.0, gt=0)

_live_mode_task: Optional[asyncio.Task] = None
_live_mode_state = {
    "is_running": False,
    "current_step": 0,
    "transactions_fired": 0,
    "sequence_length": 0,
    "current_preset": None,
}

# This is deliberately an ordered script, not a sampler.  Keep the entries as
# preset names instead of duplicating payloads so manual simulation and live
# playback always execute the same Tier 11 scenarios.
LIVE_MODE_SEQUENCE = (
    "Nighttime bank timeout",
    "High-value clean customer",
    "Stolen card",
    "Unmapped bank error",
    "Repeat offender",
    "Low-value nuisance",
    "Spend cap in action",
    "Genuinely novel bank code",
    "Account closed",
    "Compliance block",
)

def _simulate_transaction(payload: DemoSimulateRequest, source: str, db: Session):
    """Run the one and only demo simulation pipeline for every demo source."""
    decline_reason = payload.decline_reason.lower()
    allowed_reasons = set(FAST_PATH_TABLE.keys()) | set(ROUTED_TO_REASONING_PATH.keys()) | {"unmapped"}
    if decline_reason not in allowed_reasons and decline_reason != "unmapped":
        raise HTTPException(status_code=400, detail=f"Invalid decline_reason: {decline_reason}")
    
    customer_id = payload.customer_id or f"demo_cust_{uuid.uuid4().hex[:8]}"
    
    if payload.customer_history is not None:
        cust_history = payload.customer_history
    else:
        cust_history = get_customer_history(db, customer_id)
        
    payment_id = f"pay_demo_{uuid.uuid4().hex[:10]}"
    transaction = Transaction(
        id=str(uuid.uuid4()),
        razorpay_payment_id=payment_id,
        amount_inr=payload.amount_inr,
        decline_reason_raw=payload.decline_reason_raw or (decline_reason.replace("_", " ").title() if decline_reason != "unmapped" else "Unmapped Error"),
        decline_reason=decline_reason,
        customer_id=customer_id,
        customer_history=cust_history,
        failed_at=datetime.utcnow(),
        is_synthetic=True,
        data_split=source
    )
    db.add(transaction)
    db.commit()
    
    gate = route(transaction)
    if gate.path == TriagePath.DETERMINISTIC: 
        candidate, text, confidence = gate.fast_path_action, gate.fast_path_reasoning, None
    else:
        try:
            llm = get_triage_decision(transaction)
            candidate, text, confidence = llm.action, llm.reasoning_text, llm.confidence
        except Exception as exc:
            logger.exception("LLM decision failed for %s", transaction.id)
            candidate, text, confidence = None, f"LLM unavailable ({type(exc).__name__}); economics fallback.", None
            
    context = RecoveryContext(
        amount_inr=transaction.amount_inr, 
        decline_reason=transaction.decline_reason,
        customer_prior_success_rate=transaction.customer_history.get("prior_success_rate", transaction.customer_history.get("success_rate")),
        customer_account_age_days=transaction.customer_history.get("account_age_days"), 
        recent_retry_count=transaction.customer_history.get("recent_retry_count"), 
        failure_hour=transaction.failed_at.hour,
        llm_insights=llm.insights if 'llm' in locals() else None
    )
    
    evidence = query_historical_evidence(db=db, decline_reason=transaction.decline_reason, customer_history=transaction.customer_history)
    economics = score_recovery_options(transaction_id=transaction.id, permitted_actions=list(TriageAction), context=context, historical_evidence=evidence)
    selected_action = economics.selected_action
    
    if candidate is None and gate.path == TriagePath.REASONING:
        selected_action = TriageAction.HOLD_FOR_REVIEW
        text += " [Held: no safe automatic decision after LLM failure.]"
    elif candidate != economics.selected_action:
        text = f"Path suggested {candidate.value if candidate else 'None'}; economics selected {economics.selected_action.value}. {text}"
        
    result = execute(
        transaction, 
        gate.path, 
        selected_action, 
        text, 
        confidence, 
        _live_spend_tracker, 
        economics.options, 
        economics.selected_expected_net_recovery_inr, 
        economics.value_advantage_vs_next_best_inr, 
        db=db
    )
    
    option = next((o for o in economics.options if o.action == result.action), None)
    
    db.add(AuditEntry(transaction_id=transaction.id, path_taken=result.decision_path.value, action=result.action.value, reasoning_text=result.reasoning_text, confidence=result.confidence, was_gated=result.was_gated, amount_inr=transaction.amount_inr, outcome=_outcome_name(result.status)))
    db.add(RecoveryDecisionRow(transaction_id=transaction.id, options_json=[o.model_dump() for o in result.options], selected_action=result.action.value, selected_expected_net_recovery_inr=result.selected_expected_net_recovery_inr, value_advantage_vs_next_best_inr=result.value_advantage_vs_next_best_inr, confidence=result.confidence, reasoning_text=result.reasoning_text, decision_path=result.decision_path.value, was_gated=result.was_gated))
    db.add(RecoveryOutcomeRow(transaction_id=transaction.id, action=result.action.value, execution_status=result.status.value, actual_recovered_inr=None, observed_success=None, variance_inr=None, outcome_timestamp=result.completed_at or result.attempted_at, provider=result.provider, provider_reference=result.provider_reference, mode=result.mode.value, amount_attempted=result.amount_attempted, action_cost_inr=result.action_cost_inr, risk_penalty_inr=option.risk_penalty_inr if option else 0.0, net_recovered_inr=None, error_code=result.error_code, error_message=result.error_message, outcome_source="executor"))
    db.commit()
    
    return {
        "status": "processed", 
        "transaction_id": transaction.id, 
        "execution_status": result.status.value, 
        "provider_reference": result.provider_reference,
        "is_demo_simulated": True
    }


@router.post("/simulate")
def simulate_transaction(payload: DemoSimulateRequest, db: Session = Depends(get_db)):
    """Manual, one-off demo simulation. Live playback uses the same helper."""
    return _simulate_transaction(payload, source="demo", db=db)

@router.get("/presets")
def get_presets():
    return [
        {
            "name": "Nighttime bank timeout",
            "description": "Demonstrates the reasoning path correctly identifying a transient bank timeout during off-hours, recommending a delayed batch retry.",
            "payload": {
                "amount_inr": 2500.0,
                "decline_reason": "bank_timeout",
                "customer_history": {
                    "prior_transaction_count": 2,
                    "prior_success_rate": 0.5,
                    "most_recent_decline_reason": "bank_timeout",
                    "account_age_days": 15
                }
            }
        },
        {
            "name": "High-value clean customer",
            "description": "Demonstrates high confidence in retrying an insufficient funds error because the customer's flawless history suggests a simple timing issue.",
            "payload": {
                "amount_inr": 25000.0,
                "decline_reason": "insufficient_funds",
                "customer_history": {
                    "prior_transaction_count": 10,
                    "prior_success_rate": 1.0,
                    "most_recent_decline_reason": None,
                    "account_age_days": 180
                }
            }
        },
        {
            "name": "Stolen card",
            "description": "Demonstrates the deterministic fast path immediately escalating a lost or stolen card to dunning, bypassing any dangerous automatic retry.",
            "payload": {
                "amount_inr": 1500.0,
                "decline_reason": "card_reported_lost_or_stolen",
                "customer_history": {
                    "prior_transaction_count": 0,
                    "prior_success_rate": None,
                    "most_recent_decline_reason": None,
                    "account_age_days": 1
                }
            }
        },
        {
            "name": "Unmapped bank error",
            "description": "Demonstrates the LLM reasoning path correctly parsing a raw, unstructured bank error code and mapping it to an appropriate recovery action.",
            "payload": {
                "amount_inr": 3000.0,
                "decline_reason": "unmapped",
                "customer_history": {
                    "prior_transaction_count": 3,
                    "prior_success_rate": 0.66,
                    "most_recent_decline_reason": "insufficient_funds",
                    "account_age_days": 45
                }
            }
        },
        {
            "name": "Repeat offender",
            "description": "Demonstrates historical_evidence correctly shifting the probability estimate downward for repeated identical failures, favoring Dunning over another wasted retry.",
            "payload": {
                "amount_inr": 2500.0,
                "decline_reason": "insufficient_funds",
                "customer_history": {
                    "prior_transaction_count": 5,
                    "prior_success_rate": 0.2,
                    "most_recent_decline_reason": "insufficient_funds",
                    "account_age_days": 30
                }
            }
        },
        {
            "name": "Low-value nuisance",
            "description": "Demonstrates that the fixed action cost of a retry makes holding or no-action the optimal choice for very small amounts, even if probability is nontrivial.",
            "payload": {
                "amount_inr": 150.0,
                "decline_reason": "insufficient_funds",
                "customer_history": {
                    "prior_transaction_count": 1,
                    "prior_success_rate": 0.5,
                    "most_recent_decline_reason": "insufficient_funds",
                    "account_age_days": 10
                }
            }
        },
        {
            "name": "Spend cap in action",
            "description": "Sized to hit the live-mode batch spend cap so it visibly gets gated to hold_for_review by the safety bound, not by lack of confidence.",
            "payload": {
                "amount_inr": 600000.0,
                "decline_reason": "bank_timeout",
                "customer_history": {
                    "prior_transaction_count": 10,
                    "prior_success_rate": 1.0,
                    "most_recent_decline_reason": None,
                    "account_age_days": 365
                }
            }
        },
        {
            "name": "Genuinely novel bank code",
            "description": "Uses a different raw error string for an 'unmapped' decline to prove the LLM reasoning isn't brittle to a single hardcoded 'Unmapped Error' phrase.",
            "payload": {
                "amount_inr": 3500.0,
                "decline_reason": "unmapped",
                "decline_reason_raw": "ERR_99_HOST_UNAVAILABLE_RETRY",
                "customer_history": {
                    "prior_transaction_count": 4,
                    "prior_success_rate": 1.0,
                    "most_recent_decline_reason": None,
                    "account_age_days": 120
                }
            }
        },
        {
            "name": "Account closed",
            "description": "Demonstrates the fast path explicitly recognizing a permanent terminal state, selecting NO_ACTION to prevent wasted fees.",
            "payload": {
                "amount_inr": 1000.0,
                "decline_reason": "account_closed",
                "customer_history": {
                    "prior_transaction_count": 5,
                    "prior_success_rate": 0.8,
                    "most_recent_decline_reason": "account_closed",
                    "account_age_days": 200
                }
            }
        },
        {
            "name": "Compliance block",
            "description": "Demonstrates the deterministic fast path correctly isolating a regulatory risk and holding it for mandatory human review.",
            "payload": {
                "amount_inr": 5000.0,
                "decline_reason": "compliance_block",
                "customer_history": {
                    "prior_transaction_count": 1,
                    "prior_success_rate": 1.0,
                    "most_recent_decline_reason": None,
                    "account_age_days": 5
                }
            }
        }
    ]

def _live_mode_presets() -> list[dict]:
    """Resolve the explicit script against the canonical Tier 11 preset library."""
    by_name = {preset["name"]: preset for preset in get_presets()}
    missing = [name for name in LIVE_MODE_SEQUENCE if name not in by_name]
    if missing:
        raise RuntimeError(f"Live-mode presets missing from library: {missing}")
    return [by_name[name] for name in LIVE_MODE_SEQUENCE]


async def live_mode_loop(interval: float):
    presets = _live_mode_presets()
    try:
        while (_live_mode_state["is_running"]
               and _live_mode_state["current_step"] < len(presets)):
            preset = presets[_live_mode_state["current_step"]]
            payload = DemoSimulateRequest(**preset["payload"])

            db = SessionLocal()
            try:
                # No alternate execution path: this is the same helper used
                # by POST /demo/simulate, with a traceable source label.
                _simulate_transaction(payload, source="live_mode", db=db)
            except Exception:
                logger.exception("Live mode failed at preset %s", preset["name"])
            finally:
                db.close()

            _live_mode_state["current_step"] += 1
            _live_mode_state["transactions_fired"] += 1
            _live_mode_state["current_preset"] = preset["name"]

            # Do not delay after the final event: a completed playback is
            # immediately visible to polling clients.
            if _live_mode_state["current_step"] < len(presets):
                await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Live-mode playback cancelled after %s events", _live_mode_state["transactions_fired"])
        raise
    finally:
        _live_mode_state["is_running"] = False

@router.post("/live-mode/start")
async def start_live_mode(request: LiveModeStartRequest = LiveModeStartRequest()):
    global _live_mode_task
    if _live_mode_task and not _live_mode_task.done():
        return {"status": "already_running"}

    _live_mode_state["is_running"] = True
    _live_mode_state["current_step"] = 0
    _live_mode_state["transactions_fired"] = 0
    _live_mode_state["sequence_length"] = len(LIVE_MODE_SEQUENCE)
    _live_mode_state["current_preset"] = None
    _live_mode_task = asyncio.create_task(live_mode_loop(request.interval_seconds))
    return {"status": "started", "sequence_length": len(LIVE_MODE_SEQUENCE)}

@router.post("/live-mode/stop")
async def stop_live_mode():
    global _live_mode_task
    if _live_mode_task and not _live_mode_task.done():
        _live_mode_task.cancel()
        try:
            await _live_mode_task
        except asyncio.CancelledError:
            pass
    _live_mode_state["is_running"] = False
    return {"status": "stopped"}

@router.get("/live-mode/status")
def get_live_mode_status():
    return _live_mode_state
