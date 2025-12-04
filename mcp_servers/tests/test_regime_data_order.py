"""
Tests for regime.py data ordering bug fix.

Verifies that technical indicators are calculated on chronologically
ordered data, not DESC ordered data.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project paths
mcp_servers_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_servers_root))

from technical.tools.regime import get_regime_tool


@pytest.mark.asyncio
async def test_regime_data_ordering_with_mock():
    """
    Test that regime calculations use chronologically ordered data.
    
    This test creates mock data in DESC order (as returned by the query)
    and verifies that the tool correctly reorders it before calculations.
    """
    # Create test data: ascending close prices
    dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
    test_data = pd.DataFrame({
        'time': dates,
        'close': np.linspace(100, 150, 250)  # Linearly increasing prices
    })
    
    # Reverse to DESC order (simulating DB query result)
    test_data_desc = test_data.iloc[::-1].reset_index(drop=True)
    
    # Mock engine and connection
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    
    # Mock pd.read_sql to return DESC data
    with patch('pandas.read_sql') as mock_read_sql:
        # First call: OHLCV data (DESC order)
        # Second call: indicators data (empty for this test)
        mock_read_sql.side_effect = [
            test_data_desc.copy(),  # OHLCV query
            pd.DataFrame({'indicator': [], 'value': []})  # Indicators query (empty)
        ]
        
        result = await get_regime_tool({'symbol': 'TEST'}, mock_engine)
        
        assert 'metrics' in result
        assert 'sma_200' in result['metrics']
        
        sma_200 = result['metrics']['sma_200']
        
        # For linear data from 100 to 150 over 250 points:
        # Last 200 values should give SMA around 130
        print(f"SMA200 calculated: {sma_200}")
        assert sma_200 > 125, "SMA200 seems too low, might be using wrong data order"
        assert sma_200 < 150, "SMA200 seems too high"


@pytest.mark.asyncio
async def test_regime_insufficient_data_validation():
    """Test that regime tool validates minimum data requirements."""
    
    # Create insufficient data (only 150 rows, need 200+)
    dates = pd.date_range(end=datetime.now(), periods=150, freq='D')
    insufficient_data = pd.DataFrame({
        'time': dates,
        'close': np.random.rand(150) * 100 + 100
    })
    
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    
    with patch('pandas.read_sql') as mock_read_sql:
        mock_read_sql.return_value = insufficient_data
        
        # Should raise ValueError about insufficient data
        with pytest.raises(ValueError, match="Insufficient data.*need 200"):
            await get_regime_tool({'symbol': 'TEST'}, mock_engine)


@pytest.mark.asyncio
async def test_regime_current_price_is_latest():
    """Verify that current_price reflects the most recent data point."""
    
    # Create data where most recent price is clearly identifiable
    dates = pd.date_range(end=datetime.now(), periods=250, freq='D')
    test_data = pd.DataFrame({
        'time': dates,
        'close': [100.0] * 249 + [999.99]  # Last price is 999.99
    })
    
    # Return in DESC order
    test_data_desc = test_data.iloc[::-1].reset_index(drop=True)
    
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    
    with patch('pandas.read_sql') as mock_read_sql:
        mock_read_sql.side_effect = [
            test_data_desc.copy(),
            pd.DataFrame({'indicator': [], 'value': []})
        ]
        
        result = await get_regime_tool({'symbol': 'TEST'}, mock_engine)
        
        # After reordering, current_price should be 999.99
        assert result['metrics']['current_price'] == 999.99, \
            "Current price should be the most recent value after reordering"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
