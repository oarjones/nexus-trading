"""
Tests for Strategy Registry.

Tests cover:
- Loading strategies from PostgreSQL
- State management in Redis
- Regime filtering
- Weight calculation
- State transitions
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from sqlalchemy.engine.result import Result
import sys

print(">>> sys.path[0:5] =", sys.path[0:5])

from trading.registry import StrategyRegistry, StrategyState, StrategyConfig



@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis_mock = Mock()
    redis_mock.exists = Mock(return_value=False)
    redis_mock.hset = Mock()
    redis_mock.hget = Mock(return_value=None)
    return redis_mock


@pytest.fixture
def sample_strategy_data():
    """Sample strategy data from database."""
    class Row:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    return [
        Row(
            id="swing_momentum_eu",
            name="Momentum Swing EU",
            enabled=True,
            markets=["BME", "XETRA"],
            regime_filter=["trending_bull"],
            timeframe="1d",
            params={"rsi_oversold": 35, "rsi_overbought": 65},
            risk_params={"max_positions": 5, "max_drawdown": 0.15},
            description="Test strategy"
        ),
        Row(
            id="mean_reversion_pairs",
            name="Pairs Mean Reversion",
            enabled=True,
            markets=["BME"],
            regime_filter=["range_bound"],
            timeframe="1h",
            params={"zscore_entry": 2.0},
            risk_params={"max_pairs": 2, "max_drawdown": 0.10},
            description=None
        )
    ]


@pytest.fixture
def registry(mock_db, mock_redis):
    """Create StrategyRegistry instance."""
    return StrategyRegistry(mock_db, mock_redis)


class TestStrategyRegistryInit:
    """Test StrategyRegistry initialization."""
    
    def test_initialization(self, registry, mock_db, mock_redis):
        """Test registry initializes correctly."""
        assert registry.db == mock_db
        assert registry.redis == mock_redis
        assert registry._strategies == {}


class TestLoadStrategies:
    """Test loading strategies from database."""
    
    def test_load_strategies_success(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test successful loading of strategies."""
        # Mock database query
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data)
        mock_db.execute = Mock(return_value=mock_result)
        
        count = registry.load_strategies()
        
        assert count == 2
        assert len(registry._strategies) == 2
        assert "swing_momentum_eu" in registry._strategies
        assert "mean_reversion_pairs" in registry._strategies
        
        # Verify state initialization in Redis
        assert mock_redis.hset.call_count == 2
    
    def test_load_strategies_initializes_state(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test that Redis state is initialized for new strategies."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data[:1])
        mock_db.execute = Mock(return_value=mock_result)
        mock_redis.exists = Mock(return_value=False)
        
        registry.load_strategies()
        
        # Check _initialize_state was called
        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == "strategy:swing_momentum_eu"
    
    def test_strategy_config_parsed_correctly(self, registry, mock_db, sample_strategy_data):
        """Test that StrategyConfig is parsed correctly from DB."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data[:1])
        mock_db.execute = Mock(return_value=mock_result)
        
        registry.load_strategies()
        
        config = registry.get_strategy("swing_momentum_eu")
        assert config.id == "swing_momentum_eu"
        assert config.name == "Momentum Swing EU"
        assert config.enabled is True
        assert "BME" in config.markets
        assert "trending_bull" in config.regime_filter
        assert config.params["rsi_oversold"] == 35


class TestStateManagement:
    """Test strategy state management."""
    
    def test_get_state_from_redis(self, registry, mock_redis):
        """Test getting state from Redis."""
        mock_redis.hget = Mock(return_value=b"active")
        
        state = registry.get_state("swing_momentum_eu")
        
        assert state == StrategyState.ACTIVE
        mock_redis.hget.assert_called_once_with(
            "strategy:swing_momentum_eu", "state"
        )
    
    def test_get_state_initializes_if_not_exists(self, registry, mock_redis):
        """Test state initialization if not in Redis."""
        mock_redis.hget = Mock(return_value=None)
        mock_redis.exists = Mock(return_value=False)
        
        state = registry.get_state("new_strategy")
        
        assert state == StrategyState.PAUSED
        mock_redis.hset.assert_called_once()
    
    def test_set_state_valid_transition(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test setting state with valid transition."""
        # Setup
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data[:1])
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        mock_redis.hget = Mock(return_value=b"paused")
        
        # Test
        registry.set_state("swing_momentum_eu", StrategyState.ACTIVE, "Manual activation")
        
        # Verify
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args
        assert call_args[1]["mapping"]["state"] == "active"
        assert "Manual activation" in call_args[1]["mapping"]["reason"]
    
    def test_set_state_invalid_transition_raises(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test that invalid state transition raises error."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data[:1])
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        mock_redis.hget = Mock(return_value=b"drawdown_disabled")
        
        # Drawdown disabled can only go to  active or paused, not regime_disabled
        with pytest.raises(ValueError, match="Invalid state transition"):
            registry.set_state("swing_momentum_eu", StrategyState.REGIME_DISABLED)
    
    def test_set_state_unknown_strategy_raises(self, registry):
        """Test setting state for unknown strategy raises error."""
        with pytest.raises(ValueError, match="not found in registry"):
            registry.set_state("unknown_strategy", StrategyState.ACTIVE)


class TestRegimeFiltering:
    """Test filtering strategies by regime."""
    
    def test_get_active_for_regime(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test getting active strategies for a regime."""
        # Setup
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data)
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        # Mock states: swing is active, pairs is paused
        def mock_hget(key, field):
            if "swing_momentum" in key:
                return b"active"
            return b"paused"
        
        mock_redis.hget = mock_hget
        
        # Test
        active = registry.get_active_for_regime("trending_bull")
        
        assert len(active) == 1
        assert active[0].id == "swing_momentum_eu"
    
    def test_get_active_for_regime_no_matches(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test regime with no active strategies."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data)
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        mock_redis.hget = Mock(return_value=b"active")
        
        # No strategy has "high_volatility" in regime_filter
        active = registry.get_active_for_regime("high_volatility")
        
        assert len(active) == 0
    
    def test_filters_by_state_and_regime(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test filtering requires both active state AND compatible regime."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data)
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        # All strategies active
        mock_redis.hget = Mock(return_value=b"active")
        
        # Only range_bound strategies
        active = registry.get_active_for_regime("range_bound")
        
        assert len(active) == 1
        assert active[0].id == "mean_reversion_pairs"


class TestWeightCalculation:
    """Test dynamic weight calculation."""
    
    def test_calculate_weights_basic(self, registry):
        """Test basic weight calculation."""
        strategy_ids = ["strategy_a", "strategy_b"]
        
        # Add strategies to registry
        registry._strategies = {
            "strategy_a": StrategyConfig(
                "strategy_a", "Strategy A", True, [], [], "1d",
                {}, {"max_drawdown": 0.15}, None
            ),
            "strategy_b": StrategyConfig(
                "strategy_b", "Strategy B", True, [], [], "1d",
                {}, {"max_drawdown": 0.15}, None
            ),
        }
        
        performance = {
            "strategy_a": {"sharpe_3m": 1.5, "drawdown": 0.05},
            "strategy_b": {"sharpe_3m": 1.0, "drawdown": 0.03},
        }
        
        weights = registry.calculate_weights(strategy_ids, performance)
        
        # Verify weights sum to 1.0
        assert abs(sum(weights.values()) - 1.0) < 0.001
        
        # Strategy A should have higher weight (higher Sharpe)
        assert weights["strategy_a"] > weights["strategy_b"]
    
    def test_calculate_weights_applies_constraints(self, registry):
        """Test that min/max weight constraints are applied."""
        strategy_ids = ["strategy_a", "strategy_b", "strategy_c"]
        
        registry._strategies = {
            sid: StrategyConfig(sid, sid, True, [], [], "1d", {}, {"max_drawdown": 0.15}, None)
            for sid in strategy_ids
        }
        
        # One strategy much better than others
        performance = {
            "strategy_a": {"sharpe_3m": 5.0, "drawdown": 0.01},
            "strategy_b": {"sharpe_3m": 0.3, "drawdown": 0.10},
            "strategy_c": {"sharpe_3m": 0.3, "drawdown": 0.10},
        }
        
        weights = registry.calculate_weights(strategy_ids, performance)
        
        # Max weight constraint (50%)
        assert weights["strategy_a"] <= 0.50
        
        # Min weight constraint (10%)
        assert all(w >= 0.10 for w in weights.values())
    
    def test_calculate_weights_no_performance_data(self, registry):
        """Test equal weights when no performance data."""
        strategy_ids = ["strategy_a", "strategy_b"]
        
        registry._strategies = {
            sid: StrategyConfig(sid, sid, True, [], [], "1d", {}, {"max_drawdown": 0.15}, None)
            for sid in strategy_ids
        }
        
        performance = {}  # No data
        
        weights = registry.calculate_weights(strategy_ids, performance)
        
        # Equal weights
        assert abs(weights["strategy_a"] - 0.5) < 0.001
        assert abs(weights["strategy_b"] - 0.5) < 0.001
    
    def test_calculate_weights_empty_list(self, registry):
        """Test with empty strategy list."""
        weights = registry.calculate_weights([], {})
        assert weights == {}


class TestUtilityMethods:
    """Test utility methods."""
    
    def test_get_strategy(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test getting strategy by ID."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data[:1])
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        config = registry.get_strategy("swing_momentum_eu")
        
        assert config is not None
        assert config.id == "swing_momentum_eu"
    
    def test_get_strategy_not_found(self, registry):
        """Test getting non-existent strategy."""
        config = registry.get_strategy("nonexistent")
        assert config is None
    
    def test_list_all_strategies(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test listing all strategies."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data)
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        all_strategies = registry.list_all_strategies()
        
        assert len(all_strategies) == 2
        assert all(isinstance(s, StrategyConfig) for s in all_strategies)
    
    def test_get_strategy_count(self, registry, mock_db, mock_redis, sample_strategy_data):
        """Test getting strategy count."""
        mock_result = Mock(spec=Result)
        mock_result.fetchall = Mock(return_value=sample_strategy_data)
        mock_db.execute = Mock(return_value=mock_result)
        registry.load_strategies()
        
        count = registry.get_strategy_count()
        assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
