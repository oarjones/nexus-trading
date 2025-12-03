"""
Integration tests for Risk Server.

Tests all 3 tools: check_limits, calculate_size, get_exposure
"""

import pytest
import sys
from pathlib import Path

# Add mcp-servers to path
mcp_servers_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_servers_root))

from risk.tools import check_limits_tool, calculate_size_tool, get_exposure_tool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_limits_tool_allowed():
    """Test check_limits tool with allowed trade."""
    result = await check_limits_tool({
        'symbol': 'AAPL',
        'size': 10000,
        'portfolio_value': 100000,
        'current_positions': [
            {'symbol': 'MSFT', 'size': 15000, 'sector': 'Technology'}
        ],
        'sector': 'Technology'
    })
    
    assert 'allowed' in result
    assert 'violations' in result
    assert 'warnings' in result
    assert isinstance(result['allowed'], bool)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_limits_tool_position_violation():
    """Test check_limits tool with position size violation."""
    result = await check_limits_tool({
        'symbol': 'AAPL',
        'size': 25000,  # 25% of portfolio (exceeds 20% limit)
        'portfolio_value': 100000,
        'current_positions': [],
        'sector': 'Technology'
    })
    
    assert result['allowed'] is False
    assert len(result['violations']) > 0
    assert any('position size' in v.lower() for v in result['violations'])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_limits_tool_sector_violation():
    """Test check_limits tool with sector concentration violation."""
    result = await check_limits_tool({
        'symbol': 'AAPL',
        'size': 15000,
        'portfolio_value': 100000,
        'current_positions': [
            {'symbol': 'MSFT', 'size': 20000, 'sector': 'Technology'},
            {'symbol': 'GOOGL', 'size': 10000, 'sector': 'Technology'}
        ],
        'sector': 'Technology'
    })
    
    assert result['allowed'] is False
    assert any('sector' in v.lower() for v in result['violations'])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calculate_size_tool():
    """Test calculate_size tool with valid Kelly parameters."""
    result = await calculate_size_tool({
        'portfolio_value': 100000,
        'win_rate': 0.55,
        'avg_win': 0.02,
        'avg_loss': 0.01,
        'kelly_fraction': 0.25
    })
    
    assert 'suggested_size' in result
    assert 'size_pct' in result
    assert 'kelly_pct' in result
    assert result['suggested_size'] > 0
    assert 0 <= result['size_pct'] <= 0.05  # Should be reasonable


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calculate_size_tool_no_edge():
    """Test calculate_size tool with no edge (negative Kelly)."""
    result = await calculate_size_tool({
        'portfolio_value': 100000,
        'win_rate': 0.40,  # Low win rate
        'avg_win': 0.01,
        'avg_loss': 0.02,
        'kelly_fraction': 0.25
    })
    
    assert result['kelly_pct'] == 0  # No position when no edge
    assert result['suggested_size'] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_exposure_tool(sample_positions):
    """Test get_exposure tool."""
    result = await get_exposure_tool({
        'portfolio_value': 100000,
        'positions': sample_positions
    })
    
    assert result['total_value'] == 100000
    assert result['total_invested'] == 45000
    assert result['cash_pct'] == 0.55
    assert result['positions_count'] == 3
    assert 'exposure_by_sector' in result
    assert 'exposure_by_market' in result
    assert 'concentration_metrics' in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_exposure_tool_concentration(sample_positions):
    """Test get_exposure HHI calculation."""
    result = await get_exposure_tool({
        'portfolio_value': 100000,
        'positions': sample_positions
    })
    
    metrics = result['concentration_metrics']
    
    assert 'hhi' in metrics
    assert 'effective_positions' in metrics
    assert 0 < metrics['hhi'] <= 1
    assert metrics['effective_positions'] > 0
