"""
Tests for message schemas.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
import sys

print(">>> sys.path[0:5] =", sys.path[0:5])

# Imports work now thanks to pytest.ini pythonpath configuration
from agents.schemas import (
    TradingSignal,
    RiskRequest,
    RiskResponse,
    Decision,
    Alert,
    AgentStatus,
    Direction,
)


class TestTradingSignal:
    """Tests for TradingSignal model."""
    
    def test_valid_signal(self):
        """Test creating a valid trading signal."""
        signal = TradingSignal(
            from_agent="technical_analyst",
            symbol="SAN.MC",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=4.50,
            stop_loss=4.30,
            take_profit=5.00,
            timeframe="1d",
            reasoning="RSI oversold + MACD bullish",
            indicators={"RSI": 28, "MACD": 0.05}
        )
        
        assert signal.symbol == "SAN.MC"
        assert signal.direction == Direction.LONG
        assert signal.confidence == 0.75
        assert signal.message_id  # Auto-generated UUID
        assert isinstance(signal.timestamp, datetime)
    
    def test_confidence_validation(self):
        """Test that confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TradingSignal(
                from_agent="test",
                symbol="TEST",
                direction=Direction.LONG,
                confidence=1.5,  # Invalid
                entry_price=100,
                stop_loss=95,
                take_profit=110,
                timeframe="1d",
                reasoning="test",
                indicators={}
            )
    
    def test_negative_price_rejected(self):
        """Test that negative prices are rejected."""
        with pytest.raises(ValidationError):
            TradingSignal(
                from_agent="test",
                symbol="TEST",
                direction=Direction.LONG,
                confidence=0.75,
                entry_price=-100,  # Invalid
                stop_loss=95,
                take_profit=110,
                timeframe="1d",
                reasoning="test",
                indicators={}
            )
    
    def test_default_ttl(self):
        """Test that default TTL is 300 seconds."""
        signal = TradingSignal(
            from_agent="test",
            symbol="TEST",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=100,
            stop_loss=95,
            take_profit=110,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        assert signal.ttl_seconds == 300


class TestRiskRequest:
    """Tests for RiskRequest model."""
    
    def test_valid_request(self):
        """Test creating a valid risk request."""
        signal = TradingSignal(
            from_agent="technical_analyst",
            symbol="SAN.MC",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=4.50,
            stop_loss=4.30,
            take_profit=5.00,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        request = RiskRequest(
            signal=signal,
            capital=100000,
            current_positions=[]
        )
        
        assert request.signal == signal
        assert request.capital == 100000
        assert request.request_id  # Auto-generated
        assert request.message_id  # Auto-generated
    
    def test_negative_capital_rejected(self):
        """Test that negative capital is rejected."""
        signal = TradingSignal(
            from_agent="test",
            symbol="TEST",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=100,
            stop_loss=95,
            take_profit=110,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        with pytest.raises(ValidationError):
            RiskRequest(
                signal=signal,
                capital=-1000,  # Invalid
                current_positions=[]
            )


class TestRiskResponse:
    """Tests for RiskResponse model."""
    
    def test_approved_response(self):
        """Test creating an approved risk response."""
        response = RiskResponse(
            request_id="test-request-id",
            approved=True,
            original_size=100,
            adjusted_size=80,
            adjustments=[{"reason": "high_correlation", "factor": 0.8}],
            warnings=["Approaching sector limit"]
        )
        
        assert response.approved is True
        assert response.adjusted_size == 80
        assert response.rejection_reason is None
    
    def test_rejected_response(self):
        """Test creating a rejected risk response."""
        response = RiskResponse(
            request_id="test-request-id",
            approved=False,
            original_size=0,
            adjusted_size=0,
            adjustments=[],
            warnings=[],
            rejection_reason="Max drawdown exceeded"
        )
        
        assert response.approved is False
        assert response.rejection_reason == "Max drawdown exceeded"


class TestDecision:
    """Tests for Decision model."""
    
    def test_execute_decision(self):
        """Test creating an execute decision."""
        signal = TradingSignal(
            from_agent="technical_analyst",
            symbol="SAN.MC",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=4.50,
            stop_loss=4.30,
            take_profit=5.00,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        decision = Decision(
            signal=signal,
            score=0.75,
            action="execute",
            size=100,
            adjustments=[],
            warnings=[],
            reasoning="Score 0.75 exceeds threshold 0.65"
        )
        
        assert decision.action == "execute"
        assert decision.size == 100
    
    def test_invalid_action_rejected(self):
        """Test that invalid actions are rejected."""
        signal = TradingSignal(
            from_agent="test",
            symbol="TEST",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=100,
            stop_loss=95,
            take_profit=110,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        with pytest.raises(ValidationError):
            Decision(
                signal=signal,
                score=0.75,
                action="invalid_action",  # Invalid
                size=100,
                adjustments=[],
                warnings=[],
                reasoning="test"
            )


class TestAlert:
    """Tests for Alert model."""
    
    def test_critical_alert(self):
        """Test creating a critical alert."""
        alert = Alert(
            from_agent="risk_manager",
            severity="critical",
            message="KILL SWITCH: Drawdown exceeded 15%",
            context={"drawdown": 0.16}
        )
        
        assert alert.severity == "critical"
        assert "context" in alert.model_dump()
    
    def test_invalid_severity_rejected(self):
        """Test that invalid severity is rejected."""
        with pytest.raises(ValidationError):
            Alert(
                from_agent="test",
                severity="urgent",  # Invalid
                message="test"
            )


class TestAgentStatus:
    """Tests for AgentStatus model."""
    
    def test_healthy_status(self):
        """Test creating a healthy status."""
        status = AgentStatus(
            agent_name="technical_analyst",
            status="healthy",
            last_activity=datetime.utcnow(),
            metrics={"signals_generated": 5}
        )
        
        assert status.status == "healthy"
        assert status.last_activity is not None
    
    def test_invalid_status_rejected(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValidationError):
            AgentStatus(
                agent_name="test",
                status="broken",  # Invalid
            )
