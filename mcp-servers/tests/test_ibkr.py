"""
Integration tests for IBKR Server.

Tests all 5 tools: get_account, get_positions, place_order, cancel_order, get_order_status

Note: Most tests are mocked. Tests requiring real IBKR connection are marked with @pytest.mark.ibkr
"""

import pytest
import sys
from pathlib import Path

# Add mcp-servers to path
mcp_servers_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_servers_root))

from ibkr.tools import (
    get_account_tool,
    get_positions_tool,
    place_order_tool,
    cancel_order_tool,
    get_order_status_tool
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_account_tool(mock_ibkr_connection):
    """Test get_account tool with mocked connection."""
    # Mock account summary
    mock_ibkr_connection.ib.accountSummary.return_value = [
        type('obj', (), {'tag': 'NetLiquidation', 'value': '100000.00'}),
        type('obj', (), {'tag': 'TotalCashValue', 'value': '45000.00'}),
        type('obj', (), {'tag': 'BuyingPower', 'value': '180000.00'}),
    ]
    
    result = await get_account_tool({}, mock_ibkr_connection)
    
    assert result['account_id'] == 'DU1234567'
    assert result['account_type'] == 'paper'
    assert result['net_liquidation'] == 100000.00
    assert result['cash_balance'] == 45000.00


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_positions_tool(mock_ibkr_connection):
    """Test get_positions tool with mocked connection."""
    # Mock positions
    mock_position = type('obj', (), {
        'contract': type('obj', (), {
            'symbol': 'AAPL',
            'currency': 'USD',
            'exchange': 'SMART'
        }),
        'position': 100,
        'avgCost': 170.50,
        'marketValue': 17543.00,
        'unrealizedPNL': 493.00
    })
    
    mock_ibkr_connection.ib.positions.return_value = [mock_position]
    
    result = await get_positions_tool({}, mock_ibkr_connection)
    
    assert result['positions_count'] == 1
    assert result['positions'][0]['symbol'] == 'AAPL'
    assert result['positions'][0]['quantity'] == 100


@pytest.mark.integration
@pytest.mark.asyncio
async def test_place_order_tool_paper_safety(mock_ibkr_connection):
    """Test place_order tool enforces paper trading safety."""
    # Change to live account (should be blocked)
    mock_ibkr_connection.ib.managedAccounts.return_value = ['U1234567']  # Live account
    
    with pytest.raises(PermissionError, match="LIVE TRADING BLOCKED"):
        await place_order_tool({
            'symbol': 'AAPL',
            'action': 'BUY',
            'quantity': 10,
            'order_type': 'MARKET'
        }, mock_ibkr_connection, paper_only=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_place_order_tool_limit_check(mock_ibkr_connection):
    """Test place_order tool enforces order value limit."""
    with pytest.raises(ValueError, match="exceeds maximum"):
        await place_order_tool({
            'symbol': 'AAPL',
            'action': 'BUY',
            'quantity': 100,
            'order_type': 'LIMIT',
            'limit_price': 200.00  # 100 * 200 = $20,000 > $10,000 limit
        }, mock_ibkr_connection, paper_only=True, max_order_value=10000)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_place_order_tool_success(mock_ibkr_connection):
    """Test place_order tool with valid order."""
    # Mock order placement
    mock_trade = type('obj', (), {
        'order': type('obj', (), {'orderId': 123}),
        'orderStatus': type('obj', (), {'status': 'Submitted'})
    })
    
    mock_ibkr_connection.ib.placeOrder.return_value = mock_trade
    mock_ibkr_connection.ib.sleep = lambda x: None
    
    result = await place_order_tool({
        'symbol': 'AAPL',
        'action': 'BUY',
        'quantity': 10,
        'order_type': 'LIMIT',
        'limit_price': 175.00
    }, mock_ibkr_connection, paper_only=True, max_order_value=10000)
    
    assert result['order_id'] == 123
    assert result['status'] == 'Submitted'
    assert result['account_type'] == 'paper'


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cancel_order_tool(mock_ibkr_connection):
    """Test cancel_order tool."""
    # Mock trades
    mock_trade = type('obj', (), {
        'order': type('obj', (), {'orderId': 123})
    })
    
    mock_ibkr_connection.ib.trades.return_value = [mock_trade]
    mock_ibkr_connection.ib.cancelOrder = lambda x: None
    mock_ibkr_connection.ib.sleep = lambda x: None
    
    result = await cancel_order_tool({'order_id': 123}, mock_ibkr_connection)
    
    assert result['order_id'] == 123
    assert result['status'] == 'Cancelled'


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_order_status_tool(mock_ibkr_connection):
    """Test get_order_status tool."""
    # Mock trades
    mock_trade = type('obj', (), {
        'order': type('obj', (), {
            'orderId': 123,
            'action': 'BUY',
            'totalQuantity': 10
        }),
        'contract': type('obj', (), {'symbol': 'AAPL'}),
        'orderStatus': type('obj', (), {
            'status': 'Filled',
            'filled': 10,
            'remaining': 0,
            'avgFillPrice': 175.23
        })
    })
    
    mock_ibkr_connection.ib.trades.return_value = [mock_trade]
    
    result = await get_order_status_tool({'order_id': 123}, mock_ibkr_connection)
    
    assert result['order_id'] == 123
    assert result['status'] == 'Filled'
    assert result['filled'] == 10


# Optional: Real IBKR connection tests (skip if TWS not running)
@pytest.mark.ibkr
@pytest.mark.asyncio
async def test_real_ibkr_connection():
    """Test real IBKR connection (requires TWS/Gateway running)."""
    from ibkr.tools.connection import IBKRConnection
    
    conn = IBKRConnection()
    
    try:
        ib = await conn.connect()
        assert ib.isConnected()
        
        # Get account
        result = await get_account_tool({}, conn)
        assert 'account_id' in result
        
    finally:
        await conn.disconnect()
