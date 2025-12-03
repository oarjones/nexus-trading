"""
Integration tests for Market Data Server.

Tests all 3 tools: get_quote, get_ohlcv, get_symbols
"""

import pytest
import sys
from pathlib import Path

# Add mcp-servers to path
mcp_servers_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_servers_root))

from market-data.tools import get_quote_tool, get_ohlcv_tool, get_symbols_tool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_quote_tool_cache(db_url, redis_url, monkeypatch):
    """Test get_quote tool with Redis cache hit."""
    # Mock Redis to return cached quote
    mock_redis = {}
    mock_redis['quote:AAPL'] = {
        'last': '175.43',
        'bid': '175.40',
        'ask': '175.45',
        'volume': '82488200',
        'timestamp': '2024-12-03T10:00:00'
    }
    
    # Mock redis.from_url
    class MockRedis:
        def hgetall(self, key):
            return mock_redis.get(key, {})
    
    def mock_from_url(*args, **kwargs):
        return MockRedis()
    
    import redis
    monkeypatch.setattr(redis, 'from_url', mock_from_url)
    
    # Test
    result = await get_quote_tool({'symbol': 'AAPL'}, db_url, redis_url)
    
    assert result['symbol'] == 'AAPL'
    assert result['last'] == 175.43
    assert result['source'] == 'cache'


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_ohlcv_tool(db_url, sample_ohlcv_data, mock_database_pool, monkeypatch):
    """Test get_ohlcv tool."""
    # Mock pandas read_sql to return sample data
    import pandas as pd
    
    def mock_read_sql(*args, **kwargs):
        return sample_ohlcv_data.copy()
    
    monkeypatch.setattr(pd, 'read_sql', mock_read_sql)
    
    # Test
    result = await get_ohlcv_tool({
        'symbol': 'AAPL',
        'timeframe': '1d',
        'start': '2024-01-01',
        'end': '2024-01-31'
    }, db_url)
    
    assert result['symbol'] == 'AAPL'
    assert result['timeframe'] == '1d'
    assert result['count'] == 100
    assert len(result['data']) == 100


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_symbols_tool():
    """Test get_symbols tool."""
    result = await get_symbols_tool({})
    
    assert 'count' in result
    assert 'symbols' in result
    assert result['count'] > 0
    assert isinstance(result['symbols'], list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_symbols_tool_with_filter():
    """Test get_symbols tool with market filter."""
    result = await get_symbols_tool({'market': 'US'})
    
    assert 'count' in result
    assert all(s['market'] == 'US' for s in result['symbols'])
