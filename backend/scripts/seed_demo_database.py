#!/usr/bin/env python
"""
Seeds the local database with 25-30 simulated transactions specifically
flagged as 'demo' data. These run through the real triage pipeline so
the database reflects true agent behavior.
"""

import sys
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.session import SessionLocal
from app.models.transaction import Transaction
from app.models.audit_entry import AuditEntry
from app.models.recovery_decision import RecoveryDecisionRow
from app.models.recovery_outcome import RecoveryOutcomeRow
from app.agent.gate import route
from app.agent.reasoning import get_triage_decision
from app.agent.economics.historical_evidence import query_historical_evidence
from app.agent.economics.scoring import score_recovery_options
from app.agent.executor import execute, ExecutionStatus
from app.schemas.triage import TriageAction, TriagePath
from app.schemas.recovery import RecoveryContext
from app.api.webhooks import _live_spend_tracker, _outcome_name

# Reuse existing distributions
from scripts.generate_synthetic_data import (
    DECLINE_REASONS_WEIGHTED,
    HISTORY_PATTERNS,
    _weighted_choice,
    _build_customer_history,
    generate_action_outcomes
)

def clear_demo_data(db):
    print("Clearing old demo data...")
    demo_txns = db.query(Transaction).filter(
        Transaction.is_synthetic == True,
        Transaction.data_split == "demo"
    ).all()
    
    txn_ids = [t.id for t in demo_txns]
    if txn_ids:
        db.query(RecoveryOutcomeRow).filter(RecoveryOutcomeRow.transaction_id.in_(txn_ids)).delete(synchronize_session=False)
        db.query(RecoveryDecisionRow).filter(RecoveryDecisionRow.transaction_id.in_(txn_ids)).delete(synchronize_session=False)
        db.query(AuditEntry).filter(AuditEntry.transaction_id.in_(txn_ids)).delete(synchronize_session=False)
        db.query(Transaction).filter(Transaction.id.in_(txn_ids)).delete(synchronize_session=False)
        db.commit()
    print(f"Cleared {len(txn_ids)} old demo transactions.")

def seed_demo_database(count=30, seed=101):
    rng = random.Random(seed)
    base_time = datetime.utcnow() - timedelta(days=2)
    
    with SessionLocal() as db:
        clear_demo_data(db)
        
        print(f"Generating {count} new demo transactions...")
        
        action_counts = {}
        
        for i in range(count):
            decline_reason = _weighted_choice(rng, DECLINE_REASONS_WEIGHTED)
            pattern = rng.choice(HISTORY_PATTERNS)
            history = _build_customer_history(rng, pattern)
            amount_inr = round(rng.uniform(199, 15000), 2)
            failure_time = base_time + timedelta(hours=rng.randint(0, 48))
            
            # Generate the simulated true outcomes for all possible actions
            outcomes = generate_action_outcomes(decline_reason, history, amount_inr, failure_time.hour, rng)
            
            txn_id = str(uuid.uuid4())
            customer_id = f"demo_cust_{rng.getrandbits(32):08x}"
            payment_id = f"pay_demo_{rng.getrandbits(40):010x}"
            
            transaction = Transaction(
                id=txn_id,
                razorpay_payment_id=payment_id,
                amount_inr=amount_inr,
                decline_reason_raw=decline_reason.replace("_", " ").title(),
                decline_reason=decline_reason,
                customer_id=customer_id,
                customer_history=history,
                failed_at=failure_time,
                is_synthetic=True,
                data_split="demo"
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
            
            outcome_row = RecoveryOutcomeRow(
                transaction_id=transaction.id, 
                action=result.action.value, 
                execution_status=result.status.value, 
                actual_recovered_inr=None, 
                observed_success=None, 
                variance_inr=None, 
                outcome_timestamp=result.completed_at or result.attempted_at, 
                provider=result.provider, 
                provider_reference=result.provider_reference, 
                mode=result.mode.value, 
                amount_attempted=result.amount_attempted, 
                action_cost_inr=result.action_cost_inr, 
                risk_penalty_inr=option.risk_penalty_inr if option else 0.0, 
                net_recovered_inr=None, 
                error_code=result.error_code, 
                error_message=result.error_message, 
                outcome_source="executor"
            )
            db.add(outcome_row)
            db.commit()
            
            # Optionally resolve the outcome based on the synthetic ground truth
            # 80% chance we resolve it (some stay pending/held for realism)
            if rng.random() < 0.8:
                action_str = result.action.value
                synthetic_outcome = outcomes.get(action_str)
                if synthetic_outcome:
                    recovered = synthetic_outcome["recovered"]
                    recovered_amount = synthetic_outcome["recovered_amount_inr"]
                    
                    outcome_row.execution_status = ExecutionStatus.SUCCEEDED.value if recovered else ExecutionStatus.FAILED.value
                    outcome_row.actual_recovered_inr = recovered_amount
                    outcome_row.observed_success = recovered
                    outcome_row.net_recovered_inr = synthetic_outcome["net_recovered_inr"]
                    outcome_row.outcome_source = "demo_seed_resolved"
                    
                    audit = db.query(AuditEntry).filter_by(transaction_id=transaction.id).first()
                    if audit:
                        audit.outcome = "recovered" if recovered else "not_recovered"
                        
                    db.commit()
            
            action_counts[result.action.value] = action_counts.get(result.action.value, 0) + 1
            
        print("\nSeed complete! Action Distribution:")
        for action, count_ in sorted(action_counts.items()):
            print(f"  {action}: {count_}")
            
if __name__ == "__main__":
    seed_demo_database()
