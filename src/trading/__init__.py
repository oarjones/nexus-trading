"""
Trading engine for Nexus Trading Bot.

This package contains:
- Strategy Registry for strategy management
- Trading strategies (swing momentum, mean reversion, etc.)
- Backtesting framework with realistic cost models
- Execution agent for broker integration
"""

__version__ = "0.1.0"

from .registry import StrategyRegistry, StrategyState, StrategyConfig

__all__ = [
    "StrategyRegistry",
    "StrategyState",
    "StrategyConfig",
]
