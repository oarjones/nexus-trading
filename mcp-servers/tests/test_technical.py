"""
Integration tests for Technical Server.

Tests all 3 tools: calculate_indicators, get_regime, find_sr_levels
"""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add mcp-servers to path
mcp_servers_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_servers_root))

from technical.tools import calculate_indicators_tool, get_regime_tool, find_sr_levels_tool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calculate_indicators_tool(db_url, sample_ohlcv_data, monkeypatch):
    """Test calculate_indicators tool."""
    # Mock database to return sample data
    def mock_read_sql(*args, **kwargs):
        return sample_ohlcv_data.copy()
    
    monkeypatch.setattr(pd, 'read_sql', mock_read_sql)
    
    # Mock IndicatorEngine
    class MockIndicatorEngine:
        def __init__(self, *args):
            pass
        
        def calculate_all(self, df, symbol, timeframe):
            # Return mock indicators DataFrame
            return pd.DataFrame({
                'indicator': ['sma_20', 'rsi_14', 'macd_line', 'adx_14'],
                'value': [175.43, 58.32, 1.23, 28.5]
            })
    
    import src.data.indicators
    monkeypatch.setattr(src.data.indicators, 'IndicatorEngine', MockIndicatorEngine)
    
    # Test
    result = await calculate_indicators_tool({
        'symbol': 'AAPL',
        'period': 60
    }, db_url)
    
    assert result['symbol'] == 'AAPL'
    assert 'indicators' in result
    assert len(result['indicators']) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_regime_tool(db_url, sample_ohlcv_data, monkeypatch):
    """Test get_regime tool."""
    # Mock database queries
    def mock_read_sql(query, conn, **kwargs):
        # Return OHLCV
        if 'ohlcv' in str(query):
            return sample_ohlcv_data.copy()
        # Return indicators
        else:
            return pd.DataFrame({
                'indicator': ['adx_14', 'sma_200'],
                'value': [32.5, 100.0]
            })
    
    monkeypatch.setattr(pd, 'read_sql', mock_read_sql)
    
    # Test
    result = await get_regime_tool({'symbol': 'AAPL'}, db_url)
    
    assert result['symbol'] == 'AAPL'
    assert 'regime' in result
    assert 'confidence' in result
    assert 'metrics' in result
    assert result['regime'] in ['trending_bullish', 'trending_bearish', 'ranging', 'volatile_ranging']


@pytest.mark.integration
@pytest.mark.asyncio
async def test_find_sr_levels_tool(db_url, monkeypatch):
    """Test find_sr_levels tool."""
    # Create sample data with clear S/R levels
    dates = pd.date_range(end=pd.Timestamp.now(), periods=60, freq='D')
    
    # Create price pattern with resistance at 180 and support at 170
    closes = [175] * 60
    highs = [180] * 10 + [178] * 50  # Resistance at 180
    lows = [170] * 10 + [172] * 50   # Support at 170
    
    sample_data = pd.DataFrame({
        'time': dates,
        'high': highs,
        'low': lows,
        'close': closes
    })
    
    def mock_read_sql(*args, **kwargs):
        return sample_data
    
    monkeypatch.setattr(pd, 'read_sql', mock_read_sql)
    
    # Test
    result = await find_sr_levels_tool({
        'symbol': 'AAPL',
        'period': 60
    }, db_url)
    
    assert result['symbol'] == 'AAPL'
    assert 'support_levels' in result
    assert 'resistance_levels' in result
    assert isinstance(result['support_levels'], list)
    assert isinstance(result['resistance_levels'], list)
