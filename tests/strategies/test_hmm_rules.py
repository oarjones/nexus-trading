import pytest
import asyncio
from unittest.mock import MagicMock
from datetime import datetime, timezone

from src.strategies.swing.hmm_rules_strategy import HMMRulesStrategy
from src.strategies.interfaces import MarketContext, MarketRegime, PositionInfo, Signal, SignalDirection

@pytest.fixture
def hmm_strategy():
    config = {
        "required_regime": ["BULL", "SIDEWAYS"],
        "rules": {
            "bull": {
                "rsi_entry_threshold": 60,
                "position_size_pct": 0.05
            },
            "sideways": {
                "rsi_buy_threshold": 30,
                "rsi_sell_threshold": 70,
                "position_size_pct": 0.03
            }
        }
    }
    return HMMRulesStrategy(config)

@pytest.fixture
def mock_context_bull():
    return MarketContext(
        regime=MarketRegime.BULL,
        regime_confidence=0.85,
        regime_probabilities={"BULL": 0.85, "BEAR": 0.05, "SIDEWAYS": 0.1},
        market_data={
            "SPY": {
                "price": 400.0,
                "indicators": {"RSI": 50.0} # Below 60, should buy
            },
            "QQQ": {
                "price": 300.0,
                "indicators": {"RSI": 70.0} # Above 60, ignore
            }
        },
        capital_available=25000.0,
        positions=[]
    )

@pytest.fixture
def mock_context_sideways():
    return MarketContext(
        regime=MarketRegime.SIDEWAYS,
        regime_confidence=0.75,
        regime_probabilities={"SIDEWAYS": 0.75},
        market_data={
            "IWM": {
                "price": 180.0,
                "indicators": {"RSI": 25.0} # Below 30, should buy
            },
            "GLD": {
                "price": 170.0,
                "indicators": {"RSI": 45.0} # Middle, ignore
            }
        },
        capital_available=25000.0,
        positions=[]
    )

@pytest.mark.asyncio
async def test_generate_signals_bull(hmm_strategy, mock_context_bull):
    signals = await hmm_strategy.generate_signals(mock_context_bull)
    
    assert len(signals) == 1
    sig = signals[0]
    assert sig.symbol == "SPY"
    assert sig.direction == SignalDirection.LONG
    assert sig.reasoning.startswith("BULL Regime dip")
    
    # Check sizing and SL
    assert sig.size_suggestion == 0.05
    # Default SL 3% -> 400 * 0.97 = 388
    assert sig.stop_loss == 388.0

@pytest.mark.asyncio
async def test_generate_signals_sideways(hmm_strategy, mock_context_sideways):
    signals = await hmm_strategy.generate_signals(mock_context_sideways)
    
    assert len(signals) == 1
    sig = signals[0]
    assert sig.symbol == "IWM"
    assert sig.direction == SignalDirection.LONG
    assert sig.reasoning.startswith("SIDEWAYS Mean Rev")
    assert sig.size_suggestion == 0.03

@pytest.mark.asyncio
async def test_should_close_sideways(hmm_strategy):
    context = MagicMock(spec=MarketContext)
    context.regime = MarketRegime.SIDEWAYS
    context.market_data = {
        "SPY": {"indicators": {"RSI": 75.0}} # Overbought > 70
    }
    
    position = PositionInfo(
        position_id="p1",
        symbol="SPY",
        direction=SignalDirection.LONG,
        entry_price=100, current_price=110, size=10, 
        unrealized_pnl=100, unrealized_pnl_pct=0.1,
        opened_at=datetime.now(timezone.utc)
    )
    
    signal = await hmm_strategy.should_close(position, context)
    
    assert signal is not None
    assert signal.direction == SignalDirection.CLOSE
    assert "Overbought" in signal.reasoning

@pytest.mark.asyncio
async def test_should_close_bear_switch(hmm_strategy):
    # Test emergency close when regime switches to BEAR
    context = MagicMock(spec=MarketContext)
    context.regime = MarketRegime.BEAR
    
    position = PositionInfo(
        position_id="p1",
        symbol="SPY",
        direction=SignalDirection.LONG,
        entry_price=100, current_price=90, size=10, 
        unrealized_pnl=-100, unrealized_pnl_pct=-0.1,
        opened_at=datetime.now(timezone.utc)
    )
    
    signal = await hmm_strategy.should_close(position, context)
    
    assert signal is not None
    assert signal.direction == SignalDirection.CLOSE
    assert "Regime shifted to BEAR" in signal.reasoning
