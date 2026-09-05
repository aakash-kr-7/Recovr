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
    assert len(presets) == 4
    names = [p["name"] for p in presets]
    assert "Nighttime bank timeout" in names
    assert "High-value clean customer" in names
    assert "Stolen card" in names
    assert "Unmapped bank error" in names

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

