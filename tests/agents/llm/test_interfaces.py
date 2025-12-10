"""Tests para interfaces del LLM Agent."""

import pytest
from datetime import datetime
from src.agents.llm.interfaces import (
    AutonomyLevel,
    MarketView,
    PortfolioPosition,
    PortfolioSummary,
    SymbolData,
    RegimeInfo,
    RiskLimits,
    AgentContext,
    AgentDecision,
)
from src.strategies.interfaces import Signal


class TestAutonomyLevel:
    def test_enum_values(self):
        assert AutonomyLevel.CONSERVATIVE.value == "conservative"
        assert AutonomyLevel.MODERATE.value == "moderate"
        assert AutonomyLevel.EXPERIMENTAL.value == "experimental"


class TestPortfolioPosition:
    def test_market_value(self):
        pos = PortfolioPosition(
            symbol="AAPL",
            quantity=10,
            avg_entry_price=150.0,
            current_price=160.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=6.67,
            holding_days=5
        )
        assert pos.market_value == 1600.0
    
    def test_immutability(self):
        pos = PortfolioPosition(
            symbol="AAPL",
            quantity=10,
            avg_entry_price=150.0,
            current_price=160.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=6.67,
            holding_days=5
        )
        with pytest.raises(AttributeError):
            pos.quantity = 20


class TestRiskLimits:
    def test_can_trade_true(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=2,
            current_daily_pnl_pct=-1.0
        )
        assert limits.can_trade is True
        assert limits.remaining_trades == 3
    
    def test_can_trade_false_max_trades(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=5,  # Alcanzó máximo
            current_daily_pnl_pct=0
        )
        assert limits.can_trade is False
        assert limits.remaining_trades == 0
    
    def test_can_trade_false_max_loss(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=1,
            current_daily_pnl_pct=-4.0  # Excede pérdida máxima
        )
        assert limits.can_trade is False


class TestAgentContext:
    @pytest.fixture
    def sample_context(self):
        return AgentContext(
            context_id="ctx_test123",
            timestamp=datetime.utcnow(),
            regime=RegimeInfo(
                regime="BULL",
                confidence=0.75,
                probabilities={"BULL": 0.75, "BEAR": 0.1, "SIDEWAYS": 0.1, "VOLATILE": 0.05},
                model_id="hmm_v1"
            ),
            market=None, # Mocked below or ignored for basic test
            portfolio=PortfolioSummary(
                total_value=25000,
                cash_available=20000,
                invested_value=5000,
                positions=(),
                daily_pnl=50,
                daily_pnl_pct=0.2,
                total_pnl=500,
                total_pnl_pct=2.0
            ),
            watchlist=(),
            risk_limits=RiskLimits(
                max_position_pct=5.0,
                max_portfolio_risk_pct=2.0,
                max_daily_trades=5,
                max_daily_loss_pct=3.0,
                current_daily_trades=1,
                current_daily_pnl_pct=0.2
            ),
            autonomy_level=AutonomyLevel.MODERATE
        )
    
    def test_to_dict_serializable(self, sample_context):
        # We need to provide a mock market context for to_dict to work fully if we were testing to_prompt_text
        # But for to_dict, it just accesses attributes.
        # Wait, the implementation of to_dict accesses self.market attributes?
        # Let's check interfaces.py.
        # AgentContext.to_dict accesses self.market? No, it doesn't seem to include market in to_dict in the snippet I wrote?
        # Let's check the snippet I wrote for interfaces.py
        # It includes: regime, portfolio, risk_limits, watchlist_count, autonomy_level.
        # It does NOT include market in to_dict.
        
        d = sample_context.to_dict()
        import json
        json_str = json.dumps(d)  # No debe lanzar excepción
        assert "context_id" in d


class TestAgentDecision:
    def test_confidence_validation(self):
        with pytest.raises(ValueError):
            AgentDecision(
                decision_id="dec_test",
                timestamp=datetime.utcnow(),
                # context_id removed
                market_view=MarketView.BULLISH,
                confidence=1.5,  # Inválido
                reasoning="Test",
                signals=[], # was actions
                # key_factors removed
                model_used="test",
                # autonomy_level removed
                tokens_used=100,
                execution_time_ms=150 # was latency_ms
            )
    
    def test_has_actions(self):
        decision = AgentDecision(
            decision_id="dec_test",
            timestamp=datetime.utcnow(),
            market_view=MarketView.NEUTRAL,
            confidence=0.8,
            reasoning="No opportunities",
            signals=[],
            model_used="test",
            tokens_used=100,
            execution_time_ms=150
        )
        assert not decision.signals
