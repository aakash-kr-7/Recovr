import pytest
from unittest.mock import patch, MagicMock
from app.agent.providers.anthropic_provider import get_triage_decision_anthropic
from app.agent.providers.groq_provider import get_triage_decision_groq
from app.agent.reasoning import ReasoningResult
from app.schemas.triage import TriageAction
from app.models.transaction import Transaction
from datetime import datetime

@pytest.fixture
def dummy_transaction():
    return Transaction(
        id="test-txn-1",
        razorpay_payment_id="pay_123",
        amount_inr=100.0,
        decline_reason_raw="insufficient funds",
        decline_reason="insufficient_funds",
        customer_id="cust_1",
        customer_history={},
        failed_at=datetime.utcnow(),
        is_synthetic=True
    )

def test_anthropic_provider_contract(dummy_transaction):
    with patch("app.agent.providers.anthropic_provider.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = {
            "action": "retry_same_rail",
            "reasoning": "Standard retry for timing issue",
            "confidence": 0.95
        }
        
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response
        
        result = get_triage_decision_anthropic(dummy_transaction, "system_prompt", "user_message")
        
        assert isinstance(result, ReasoningResult)
        assert result.action == TriageAction.RETRY_SAME_RAIL
        assert result.reasoning_text == "Standard retry for timing issue"
        assert result.confidence == 0.95

def test_groq_provider_contract(dummy_transaction):
    with patch("app.agent.providers.groq_provider.Groq") as MockGroq:
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        
        mock_message = MagicMock()
        # Groq provider uses JSON mode and reads message.content rather
        # than native tool calls (see groq_provider.py).
        mock_message.content = '{"action": "retry_same_rail", "reasoning": "Standard retry for timing issue", "confidence": 0.95}'
        
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        mock_client.chat.completions.create.return_value = mock_response
        
        result = get_triage_decision_groq(dummy_transaction, "system_prompt", "user_message")
        
        assert isinstance(result, ReasoningResult)
        assert result.action == TriageAction.RETRY_SAME_RAIL
        assert result.reasoning_text == "Standard retry for timing issue"
        assert result.confidence == 0.95
