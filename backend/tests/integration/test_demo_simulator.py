import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.session import Base
from app.main import app
from app.models.transaction import Transaction
from app.models.audit_entry import AuditEntry
from app.models.recovery_decision import RecoveryDecisionRow
from app.models.recovery_outcome import RecoveryOutcomeRow

client = TestClient(app)

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(autouse=True)
def setup_db(db_session):
    # The get_db dependency needs to be overridden for the TestClient to use db_session
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.clear()

def test_demo_presets_exist():
    response = client.get("/demo/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) == 10
    for p in presets:
        assert "description" in p
    names = [p["name"] for p in presets]
    assert "Nighttime bank timeout" in names
    assert "High-value clean customer" in names
    assert "Stolen card" in names
    assert "Unmapped bank error" in names
    assert "Repeat offender" in names
    assert "Low-value nuisance" in names
    assert "Spend cap in action" in names
    assert "Genuinely novel bank code" in names
    assert "Account closed" in names
    assert "Compliance block" in names

@patch("app.api.demo.get_triage_decision")
def test_demo_simulate_stolen_card(mock_get_triage_decision, db_session):
    """
    Proves the 'Stolen card' preset hits the deterministic fast path 
    and structural zero (no LLM call).
    """
    response = client.get("/demo/presets")
    presets = response.json()
    stolen_card_preset = next(p for p in presets if p["name"] == "Stolen card")
    
    payload = stolen_card_preset["payload"]
    
    sim_response = client.post("/demo/simulate", json=payload)
    assert sim_response.status_code == 200
    sim_data = sim_response.json()
    assert sim_data["is_demo_simulated"] is True
    
    txn_id = sim_data["transaction_id"]
    
    mock_get_triage_decision.assert_not_called()
    
    txn = db_session.query(Transaction).filter_by(id=txn_id).first()
    assert txn is not None
    assert txn.is_synthetic is True
    assert txn.data_split == "demo"
    
    audit = db_session.query(AuditEntry).filter_by(transaction_id=txn_id).first()
    assert audit is not None
    assert audit.path_taken == "deterministic"
    
    decision = db_session.query(RecoveryDecisionRow).filter_by(transaction_id=txn_id).first()
    assert decision is not None

def test_demo_simulate_all_presets(db_session):
    """
    Proves each of the four presets runs end-to-end and produces 
    a real AuditEntry + RecoveryDecision row.
    """
    with patch("app.api.demo.get_triage_decision") as mock_llm:
        from app.schemas.triage import TriageAction
        from app.agent.reasoning import ReasoningResult
        mock_llm.return_value = ReasoningResult(
            action=TriageAction.RETRY_SAME_RAIL,
            reasoning_text="Mocked LLM reasoning",
            confidence=0.9
        )
        
        response = client.get("/demo/presets")
        presets = response.json()
        
        for preset in presets:
            sim_response = client.post("/demo/simulate", json=preset["payload"])
            assert sim_response.status_code == 200
            sim_data = sim_response.json()
            
            txn_id = sim_data["transaction_id"]
            
            txn = db_session.query(Transaction).filter_by(id=txn_id).first()
            assert txn.is_synthetic is True
            assert txn.data_split == "demo"
            
            audit = db_session.query(AuditEntry).filter_by(transaction_id=txn_id).first()
            assert audit is not None
            
            decision = db_session.query(RecoveryDecisionRow).filter_by(transaction_id=txn_id).first()
            assert decision is not None

def test_repeat_offender_economic_shift(db_session):
    """
    Proves the 'Repeat offender' scenario's second/third occurrence actually produces 
    a measurably different economic outcome than the first, proving the historical 
    evidence loop is doing real work here.
    """
    with patch("app.api.demo.get_triage_decision") as mock_llm:
        from app.schemas.triage import TriageAction
        from app.agent.reasoning import ReasoningResult
        
        # We mock LLM to always suggest RETRY_SAME_RAIL with some reasoning.
        mock_llm.return_value = ReasoningResult(
            action=TriageAction.RETRY_SAME_RAIL,
            reasoning_text="LLM suggests retry",
            confidence=0.9
        )
        
        response = client.get("/demo/presets")
        presets = response.json()
        repeat_offender = next(p for p in presets if p["name"] == "Repeat offender")
        
        # Occurrence 1: Before any historical evidence is logged.
        resp1 = client.post("/demo/simulate", json=repeat_offender["payload"])
        assert resp1.status_code == 200
        txn1_id = resp1.json()["transaction_id"]
        
        dec1 = db_session.query(RecoveryDecisionRow).filter_by(transaction_id=txn1_id).first()
        expected_recovery_1 = dec1.selected_expected_net_recovery_inr
        
        # Seed 5 failed outcomes for this customer to cross MIN_SAMPLE_SIZE
        import uuid
        from datetime import datetime
        from app.models.transaction import Transaction
        
        for _ in range(5):
            fake_txn_id = str(uuid.uuid4())
            fake_txn = Transaction(
                id=fake_txn_id,
                razorpay_payment_id=f"fake_pay_{fake_txn_id}",
                amount_inr=repeat_offender["payload"]["amount_inr"],
                decline_reason=repeat_offender["payload"]["decline_reason"],
                decline_reason_raw="Insufficient Funds",
                customer_id="demo_cust",
                customer_history=repeat_offender["payload"]["customer_history"],
                failed_at=datetime.utcnow(),
                is_synthetic=True,
                data_split="demo"
            )
            db_session.add(fake_txn)
            
            fake_out = RecoveryOutcomeRow(
                transaction_id=fake_txn_id,
                action="retry_same_rail",
                execution_status="completed",
                observed_success=False,
                amount_attempted=repeat_offender["payload"]["amount_inr"],
                action_cost_inr=0.0,
                risk_penalty_inr=0.0,
                outcome_source="executor",
                outcome_timestamp=datetime.utcnow()
            )
            db_session.add(fake_out)
        db_session.commit()
        
        # Occurrence 2: After 5 failures, historical evidence should shift probability to 0.0
        resp2 = client.post("/demo/simulate", json=repeat_offender["payload"])
        assert resp2.status_code == 200
        txn2_id = resp2.json()["transaction_id"]
        
        dec2 = db_session.query(RecoveryDecisionRow).filter_by(transaction_id=txn2_id).first()
        expected_recovery_2 = dec2.selected_expected_net_recovery_inr
        
        # Prove the expected recovery shifted downwards
        assert expected_recovery_2 < expected_recovery_1
        
        # In fact, with 0% historical success on retry_same_rail, it shouldn't pick retry_same_rail anymore
        assert dec2.selected_action != dec1.selected_action

