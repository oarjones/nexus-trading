"""Tests para interfaces y dataclasses de estrategias."""

import pytest
from datetime import datetime, timedelta
from src.strategies.interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    PositionInfo,
    MarketContext,
    TradingStrategy,
)


class TestSignal:
    """Tests para Signal dataclass."""
    
    def test_signal_creation_valid(self):
        """Crear señal válida."""
        signal = Signal(
            strategy_id="test_strategy",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.75,
            entry_price=450.0,
            stop_loss=445.0,
            take_profit=465.0,
            regime_at_signal=MarketRegime.BULL,
            regime_confidence=0.80,
        )
        
        assert signal.strategy_id == "test_strategy"
        assert signal.symbol == "SPY"
        assert signal.direction == SignalDirection.LONG
        assert signal.confidence == 0.75
        assert signal.signal_id  # UUID generado
    
    def test_signal_requires_entry_for_long(self):
        """Señales LONG requieren entry_price."""
        with pytest.raises(ValueError, match="requieren entry_price"):
            Signal(
                strategy_id="test",
                symbol="SPY",
                direction=SignalDirection.LONG,
                confidence=0.70,
                entry_price=None,  # ← Error: requerido
                stop_loss=445.0,
            )
    
    def test_signal_requires_stop_loss(self):
        """Señales LONG/SHORT requieren stop_loss."""
        with pytest.raises(ValueError, match="requieren stop_loss"):
            Signal(
                strategy_id="test",
                symbol="SPY",
                direction=SignalDirection.LONG,
                confidence=0.70,
                entry_price=450.0,
                stop_loss=None,  # ← Error: requerido
            )
    
    def test_confidence_validation(self):
        """Confianza debe estar entre 0 y 1."""
        with pytest.raises(ValueError, match="confidence debe estar entre"):
            Signal(
                strategy_id="test",
                symbol="SPY",
                direction=SignalDirection.HOLD,
                confidence=1.5,  # ← Error: > 1.0
            )
    
    def test_risk_reward_ratio(self):
        """Calcular ratio riesgo/beneficio."""
        signal = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.70,
            entry_price=100.0,
            stop_loss=95.0,    # Riesgo: 5
            take_profit=115.0,  # Beneficio: 15
        )
        
        assert signal.risk_reward_ratio() == 3.0  # 15 / 5 = 3
    
    def test_signal_expiration(self):
        """Verificar expiración de señal."""
        # Señal que expira en el pasado
        signal = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.HOLD,
            confidence=0.50,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert signal.is_expired() is True
        
        # Señal que expira en el futuro
        signal2 = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.HOLD,
            confidence=0.50,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert signal2.is_expired() is False
    
    def test_signal_serialization(self):
        """Serializar y deserializar señal."""
        original = Signal(
            strategy_id="test_strategy",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.75,
            entry_price=450.0,
            stop_loss=445.0,
            take_profit=465.0,
            regime_at_signal=MarketRegime.BULL,
            regime_confidence=0.80,
            indicators={"rsi": 35, "macd": 0.5},
        )
        
        data = original.to_dict()
        restored = Signal.from_dict(data)
        
        assert restored.signal_id == original.signal_id
        assert restored.direction == original.direction
        assert restored.regime_at_signal == original.regime_at_signal
        assert restored.indicators == original.indicators
