#!/usr/bin/env python
# scripts/verify_fase_b1.py
"""
Verification script for Phase B1: ETF Momentum Strategy.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_check(name: str, passed: bool, detail: str = "") -> None:
    status = "OK" if passed else "FAIL"
    if detail:
        print(f"  [{status}] {name}: {detail}")
    else:
        print(f"  [{status}] {name}")


def verify_interfaces() -> bool:
    """Verify interfaces and dataclasses."""
    print_header("VERIFYING INTERFACES")
    
    all_passed = True
    
    try:
        from src.strategies.interfaces import (
            Signal, SignalDirection, MarketRegime,
            PositionInfo, MarketContext, TradingStrategy
        )
        print_check("Imports", True)
    except Exception as e:
        print_check("Imports", False, str(e))
        return False
    
    # Test Signal
    try:
        sig = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.8,
            entry_price=100.0,
            stop_loss=90.0,
            take_profit=120.0
        )
        assert sig.risk_reward_ratio() == 2.0
        print_check("Signal dataclass", True)
    except Exception as e:
        print_check("Signal dataclass", False, str(e))
        all_passed = False

    # Test TradingStrategy ABC
    try:
        class TestStrategy(TradingStrategy):
            @property
            def strategy_id(self): return "test"
            @property
            def strategy_name(self): return "Test"
            @property
            def strategy_description(self): return "Test Desc"
            @property
            def required_regime(self): return [MarketRegime.BULL]
            def generate_signals(self, ctx): return []
            def should_close(self, pos, ctx): return None
            
        strat = TestStrategy()
        assert strat.strategy_id == "test"
        print_check("TradingStrategy ABC", True)
    except Exception as e:
        print_check("TradingStrategy ABC", False, str(e))
        all_passed = False
        
    return all_passed


def verify_registry() -> bool:
    """Verify StrategyRegistry."""
    print_header("VERIFYING REGISTRY")
    
    all_passed = True
    
    try:
        from src.strategies.registry import StrategyRegistry
        from src.strategies.interfaces import TradingStrategy, MarketRegime
        
        # Reset registry
        StrategyRegistry.reset()
        
        # Define test strategy
        class MockStrategy(TradingStrategy):
            @property
            def strategy_id(self): return "mock_strat"
            @property
            def strategy_name(self): return "Mock"
            @property
            def strategy_description(self): return "Mock"
            @property
            def required_regime(self): return [MarketRegime.BULL]
            def generate_signals(self, ctx): return []
            def should_close(self, pos, ctx): return None
            
        # Register
        StrategyRegistry.register("mock_strat", MockStrategy)
        print_check("Register strategy", True)
        
        # Get instance
        instance = StrategyRegistry.get("mock_strat")
        assert instance is not None
        assert instance.strategy_id == "mock_strat"
        print_check("Get instance", True)
        
        # Singleton check
        instance2 = StrategyRegistry.get("mock_strat")
        assert instance is instance2
        print_check("Singleton instance", True)
        
    except Exception as e:
        print_check("Registry logic", False, str(e))
        all_passed = False
        
    return all_passed


def verify_config() -> bool:
    """Verify StrategyConfig."""
    print_header("VERIFYING CONFIG")
    
    all_passed = True
    
    try:
        from src.strategies.config import get_strategy_config
        
        config = get_strategy_config()
        assert config.config  # Should load default or file
        
        # Check structure
        assert "strategies" in config.config
        assert "global" in config.config
        
        print_check("Config loading", True)
        
        # Check specific value
        etf_conf = config.get_strategy_config("etf_momentum")
        assert etf_conf.get("enabled") is True
        print_check("ETF Momentum config", True)
        
    except Exception as e:
        print_check("Config logic", False, str(e))
        all_passed = False
        
    return all_passed


def verify_etf_momentum() -> bool:
    """Verify ETF Momentum Strategy components."""
    print_header("VERIFYING ETF MOMENTUM")
    
    all_passed = True
    
    try:
        from src.strategies.swing.momentum_calculator import MomentumCalculator
        from src.strategies.swing.etf_momentum import ETFMomentumStrategy
        from src.strategies.swing.base_swing import BaseSwingStrategy
        from src.strategies.registry import StrategyRegistry
        
        # Check inheritance
        assert issubclass(ETFMomentumStrategy, BaseSwingStrategy)
        print_check("Inheritance", True)
        
        # Check Calculator
        calc = MomentumCalculator()
        prices = [100.0] * 252
        score = calc.calculate("TEST", prices)
        assert score.score == 50.0  # Flat prices = neutral score
        print_check("Momentum Calculator", True)
        
        # Check Strategy Instantiation
        strat = ETFMomentumStrategy()
        assert strat.strategy_id == "etf_momentum"
        print_check("Strategy Instantiation", True)
        
        # Check Registry Auto-registration
        # Note: Importing the module should trigger registration via decorator
        reg_strat = StrategyRegistry.get("etf_momentum")
        assert reg_strat is not None
        assert isinstance(reg_strat, ETFMomentumStrategy)
        print_check("Auto-registration", True)
        
    except Exception as e:
        print_check("ETF Momentum logic", False, str(e))
        all_passed = False
        
    return all_passed


def verify_runner() -> bool:
    """Verify StrategyRunner."""
    print_header("VERIFYING RUNNER")
    
    all_passed = True
    
    try:
        import asyncio
        import logging
        
        # Configure logging to see runner output
        logging.basicConfig(level=logging.DEBUG)
        
        from src.strategies.runner import StrategyRunner
        from src.strategies.registry import StrategyRegistry
        from src.strategies.swing.etf_momentum import ETFMomentumStrategy
        
        # Mock MCP Client
        class MockMCP:
            async def call(self, server, tool, params=None):
                if tool == "get_regime":
                    return {"regime": "BULL", "confidence": 0.8, "probabilities": {}}
                if tool == "get_ohlcv":
                    # Return bullish prices
                    return {"close": [100.0 * (1 + 0.001*i) for i in range(300)], "volume": []}
                if tool == "get_indicators":
                    return {
                        "rsi_14": 50, 
                        "sma_50": 90, 
                        "sma_200": 80, 
                        "atr_14": 2.0,
                        "volatility_20d": 0.1
                    }
                return {}
        
        # Setup
        StrategyRegistry.reset()
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        # Force config reload to populate Registry
        from src.strategies.config import get_strategy_config
        config = get_strategy_config()
        config.load()  # Reloads from file and updates Registry
        
        runner = StrategyRunner(mcp_client=MockMCP())
        
        # Run cycle
        signals = asyncio.run(runner.run_cycle())
        
        # Should generate signals because regime is BULL and prices are bullish
        assert len(signals) > 0
        print_check("Run Cycle (Signals Generated)", True)
        
        metrics = runner.get_metrics()
        assert metrics["cycles_completed"] == 1
        print_check("Runner Metrics", True)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print_check("Runner logic", False, str(e))
        all_passed = False
        
    return all_passed


def main():
    print("STARTING PHASE B1 VERIFICATION")
    
    checks = [
        verify_interfaces(),
        verify_registry(),
        verify_config(),
        verify_etf_momentum(),
        verify_runner(),
    ]
    
    if all(checks):
        print("\n" + "="*60)
        print("  ALL CHECKS PASSED - PHASE B1 (PARTIAL)")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("  SOME CHECKS FAILED")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
