"""
Positions retrieval tool.

Get current portfolio positions from IBKR.
"""

import logging
from typing import Dict, Any, List
from .connection import IBKRConnection

logger = logging.getLogger(__name__)


async def get_positions_tool(args: Dict[str, Any], ibkr_conn: IBKRConnection) -> Dict[str, Any]:
    """
    Get current portfolio positions.
    
    Retrieves all open positions from IBKR account.
    
    Args:
        args: Tool arguments (none required)
        ibkr_conn: IBKR connection instance
        
    Returns:
        Dictionary with positions list
        
    Example:
        >>> await get_positions_tool({}, ibkr_conn)
        {
            "positions_count": 3,
            "total_value": 55000.00,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 100,
                    "avg_cost": 170.50,
                    "market_price": 175.43,
                    "market_value": 17543.00,
                    "unrealized_pnl": 493.00,
                    "unrealized_pnl_pct": 2.89
                },
                ...
            ]
        }
    """
    try:
        # Ensure connected
        ib = await ibkr_conn.ensure_connected()
        
        # Get positions
        positions = await ib.positionsAsync()
        
        positions_list = []
        total_value = 0.0
        
        for position in positions:
            contract = position.contract
            
            # Get market price (use market value / quantity)
            market_value = position.marketValue
            quantity = position.position
            market_price = market_value / quantity if quantity != 0 else 0
            
            unrealized_pnl = position.unrealizedPNL
            unrealized_pnl_pct = (unrealized_pnl / (position.avgCost * abs(quantity))) * 100 if position.avgCost and quantity else 0
            
            positions_list.append({
                'symbol': contract.symbol,
                'quantity': int(quantity),
                'avg_cost': round(position.avgCost, 2),
                'market_price': round(market_price, 2),
                'market_value': round(market_value, 2),
                'unrealized_pnl': round(unrealized_pnl, 2),
                'unrealized_pnl_pct': round(unrealized_pnl_pct, 2),
                'currency': contract.currency,
                'exchange': contract.exchange
            })
            
            total_value += market_value
        
        logger.info(f"Retrieved {len(positions_list)} positions, total value: ${total_value:,.2f}")
        
        return {
            'positions_count': len(positions_list),
            'total_value': round(total_value, 2),
            'positions': positions_list
        }
    
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise
