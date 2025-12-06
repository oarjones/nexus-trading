#!/usr/bin/env python
# scripts/verify_fase_c2.py
"""
Verification script for Phase C2: Intraday Strategies.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.intraday.mixins import MarketSession, IntraDayLimits, IntraDayMixin
from src.strategies.intraday.mean_reversion import MeanReversionIntraday
from src.strategies.intraday.volatility_breakout import VolatilityBreakout
from src.strategies.interfaces import MarketRegime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_c2")


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


def verify_session_logic():
    """Verify MarketSession logic."""
    print_header("VERIFYING SESSION LOGIC")
    
    try:
        session = MarketSession(
            market_id="TEST",
            timezone="UTC",
            open_time=time(9, 0),
            close_time=time(17, 0)
        )
        
        # Test Open
        open_dt = datetime(2023, 1, 4, 10, 0, tzinfo=ZoneInfo("UTC")) # Wed
        assert session.is_open(open_dt)
        print_check("Session Open Check", True)
        
        # Test Closed (Time)
        closed_dt = datetime(2023, 1, 4, 18, 0, tzinfo=ZoneInfo("UTC"))
        assert not session.is_open(closed_dt)
        print_check("Session Closed Check", True)
        
        # Test Time to Close
        dt = datetime(2023, 1, 4, 16, 30, tzinfo=ZoneInfo("UTC"))
        remaining = session.time_to_close(dt)
        assert remaining == timedelta(minutes=30)
        print_check("Time to Close Check", True)
        
        return True
    except Exception as e:
        print_check("Session Logic", False, str(e))
        return False


def verify_mean_reversion():
    """Verify Mean Reversion Strategy."""
    print_header("VERIFYING MEAN REVERSION")
    
    try:
        strategy = MeanReversionIntraday({
            "timeframe": "5min",
            "market": "US",
            "limits": {"max_trades_per_day": 5}
        })
        
        # Create Mock Data (Price below Lower Band)
        dates = pd.date_range(start="2023-01-01", periods=100, freq="5min")
        df = pd.DataFrame({
            "close": np.random.normal(100, 1, 100),
            "volume": np.random.normal(1000, 100, 100),
            "symbol": ["TEST"] * 100
        }, index=dates)
        
        # Force a drop
        df.iloc[-1, df.columns.get_loc("close")] = 90.0 
        
        # Generate Signals
        # Mock portfolio
        portfolio = {"total_value": 10000}
        
        # We need to bypass pre_checks that check time vs market hours
        # So we call _calculate_entry_signals directly
        signals = strategy._calculate_entry_signals(
            market_data=df,
            regime=MarketRegime.SIDEWAYS,
            portfolio=portfolio
        )
        
        # Should generate LONG signal (price 90 < lower band ~98)
        assert len(signals) > 0
        assert signals[0].direction.value == "LONG"
        
        print_check("Mean Reversion Signal Generation", True)
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print_check("Mean Reversion", False, str(e))
        return False


def verify_volatility_breakout():
    """Verify Volatility Breakout Strategy."""
    print_header("VERIFYING VOLATILITY BREAKOUT")
    
    try:
        strategy = VolatilityBreakout({
            "timeframe": "1min",
            "market": "US"
        })
        
        # Create Mock Data (Breakout Up)
        dates = pd.date_range(start="2023-01-01", periods=100, freq="1min")
        highs = np.random.normal(100, 1, 100)
        lows = highs - 1
        closes = highs - 0.5
        
        df = pd.DataFrame({
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.random.normal(1000, 100, 100),
            "symbol": ["TEST"] * 100
        }, index=dates)
        
        # Force breakout
        df.iloc[-1, df.columns.get_loc("close")] = 110.0
        df.iloc[-1, df.columns.get_loc("high")] = 110.5
        df.iloc[-1, df.columns.get_loc("volume")] = 5000 # High volume
        
        # Generate Signals
        signals = strategy._calculate_entry_signals(
            market_data=df,
            regime=MarketRegime.VOLATILE,
            portfolio={"total_value": 10000}
        )
        
        # Should generate LONG signal
        assert len(signals) > 0
        assert signals[0].direction.value == "LONG"
        
        print_check("Volatility Breakout Signal Generation", True)
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print_check("Volatility Breakout", False, str(e))
        return False


def main():
    print("STARTING PHASE C2 VERIFICATION")
    
    checks = [
        verify_session_logic(),
        verify_mean_reversion(),
        verify_volatility_breakout(),
    ]
    
    if all(checks):
        print("\n" + "="*60)
        print("  ALL CHECKS PASSED - PHASE C2")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("  SOME CHECKS FAILED")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
