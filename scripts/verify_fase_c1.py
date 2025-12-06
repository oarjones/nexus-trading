#!/usr/bin/env python
# scripts/verify_fase_c1.py
"""
Verification script for Phase C1: Metrics System.
"""

import sys
import asyncio
import json
import uuid
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics.schemas import (
    TradeOpenEvent,
    TradeCloseEvent,
    TradeDirection,
    TradeStatus,
    TradeEventType
)
from src.metrics.calculators import (
    calculate_sharpe_ratio,
    calculate_win_rate,
    calculate_max_drawdown
)
from src.metrics.collector import MetricsCollector
# Aggregator requires DB connection, we'll mock or skip deep integration test if DB not ready
from src.metrics.aggregator import MetricsAggregator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_c1")


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


async def verify_schemas():
    """Verify Pydantic schemas."""
    print_header("VERIFYING SCHEMAS")
    
    try:
        # Test TradeOpenEvent
        event = TradeOpenEvent(
            strategy_id="test_strat",
            symbol="SPY",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            size_shares=10,
            size_value_eur=1000.0
        )
        assert event.event_type == TradeEventType.TRADE_OPEN
        assert event.trade_id is not None
        
        print_check("TradeOpenEvent Schema", True)
        return True
    except Exception as e:
        print_check("TradeOpenEvent Schema", False, str(e))
        return False


async def verify_calculators():
    """Verify Calculators."""
    print_header("VERIFYING CALCULATORS")
    
    try:
        # Win Rate
        pnl = [100, -50, 100, -50]
        wr = calculate_win_rate(pnl)
        assert wr == 0.5
        print_check("Win Rate Calculator", True)
        
        # Sharpe
        returns = [0.01, 0.02, -0.01, 0.015]
        sharpe = calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, float)
        print_check("Sharpe Calculator", True)
        
        # Max Drawdown
        equity = [100, 110, 105, 115, 90, 100]
        # Peak 115, Drop to 90. DD = (115-90)/115 = 25/115 = 0.217
        dd = calculate_max_drawdown(equity)
        assert 0.21 < dd < 0.22
        print_check("Max Drawdown Calculator", True)
        
        return True
    except Exception as e:
        print_check("Calculators", False, str(e))
        return False


async def verify_collector_mock():
    """Verify Collector (Mocked Redis/DB)."""
    print_header("VERIFYING COLLECTOR (MOCK)")
    
    # This is a partial verification since we might not have Redis/DB running in this env
    # We'll just instantiate and check basic structure
    try:
        collector = MetricsCollector()
        assert collector.channel == "trades"
        print_check("Collector Instantiation", True)
        return True
    except Exception as e:
        print_check("Collector Instantiation", False, str(e))
        return False


async def main_async():
    print("STARTING PHASE C1 VERIFICATION")
    
    checks = [
        await verify_schemas(),
        await verify_calculators(),
        await verify_collector_mock(),
    ]
    
    if all(checks):
        print("\n" + "="*60)
        print("  ALL CHECKS PASSED - PHASE C1")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("  SOME CHECKS FAILED")
        print("="*60)
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
