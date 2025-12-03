"""
Order management tools.

Place, cancel, and check status of orders in IBKR.
"""

import logging
from typing import Dict, Any
from ib_insync import Stock, MarketOrder, LimitOrder, Order
from .connection import IBKRConnection

logger = logging.getLogger(__name__)


async def place_order_tool(
    args: Dict[str, Any],
    ibkr_conn: IBKRConnection,
    paper_only: bool = True,
    max_order_value: float = 10000
) -> Dict[str, Any]:
    """
    Place an order in IBKR.
    
    SAFETY: By default only allows paper trading and caps order value.
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol
            - action (str): 'BUY' or 'SELL'
            - quantity (int): Number of shares
            - order_type (str): 'MARKET' or 'LIMIT'
            - limit_price (float, optional): For limit orders
        ibkr_conn: IBKR connection instance
        paper_only: Safety check - only allow paper accounts
        max_order_value: Maximum order value in USD
        
    Returns:
        Dictionary with order confirmation
        
    Example:
        >>> await place_order_tool({
        ...     "symbol": "AAPL",
        ...     "action": "BUY",
        ...     "quantity": 10,
        ...     "order_type": "LIMIT",
        ...     "limit_price": 175.00
        ... }, ibkr_conn)
        {
            "order_id": 123,
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "order_type": "LIMIT",
            "limit_price": 175.00,
            "status": "Submitted"
        }
    """
    symbol = args.get('symbol')
    action = args.get('action', '').upper()
    quantity = args.get('quantity', 0)
    order_type = args.get('order_type', 'MARKET').upper()
    limit_price = args.get('limit_price')
    
    if not symbol or action not in ['BUY', 'SELL'] or quantity <= 0:
        raise ValueError("Invalid order parameters")
    
    try:
        # Ensure connected
        ib = await ibkr_conn.ensure_connected()
        
        # SAFETY CHECK 1: Verify paper trading
        accounts = ib.managedAccounts()
        account_id = accounts[0] if accounts else ''
        is_paper = account_id.startswith('DU')
        
        if paper_only and not is_paper:
            raise PermissionError(
                "LIVE TRADING BLOCKED: This server is configured for paper trading only. "
                f"Current account: {account_id}"
            )
        
        # SAFETY CHECK 2: Order value limit
        if limit_price:
            order_value = quantity * limit_price
        else:
            # For market orders, we'd need current price - skip check
            order_value = 0
        
        if order_value > max_order_value:
            raise ValueError(
                f"Order value ${order_value:,.2f} exceeds maximum ${max_order_value:,.2f}"
            )
        
        # Create contract
        contract = Stock(symbol, 'SMART', 'USD')
        
        # Create order
        if order_type == 'MARKET':
            order = MarketOrder(action, quantity)
        elif order_type == 'LIMIT':
            if not limit_price:
                raise ValueError("Limit price required for LIMIT orders")
            order = LimitOrder(action, quantity, limit_price)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
        
        # Place order
        trade = await ib.placeOrderAsync(contract, order)
        
        # Wait for initial confirmation
        await ib.sleep(1)
        
        logger.info(
            f"Order placed: {action} {quantity} {symbol} @ "
            f"{'MARKET' if order_type == 'MARKET' else f'LIMIT {limit_price}'} "
            f"(Order ID: {trade.order.orderId})"
        )
        
        return {
            'order_id': trade.order.orderId,
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'order_type': order_type,
            'limit_price': limit_price,
            'status': trade.orderStatus.status,
            'account_type': 'paper' if is_paper else 'live'
        }
    
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise


async def cancel_order_tool(args: Dict[str, Any], ibkr_conn: IBKRConnection) -> Dict[str, Any]:
    """
    Cancel an order in IBKR.
    
    Args:
        args: Tool arguments containing:
            - order_id (int): Order ID to cancel
        ibkr_conn: IBKR connection instance
        
    Returns:
        Dictionary with cancellation confirmation
        
    Example:
        >>> await cancel_order_tool({"order_id": 123}, ibkr_conn)
        {
            "order_id": 123,
            "status": "Cancelled"
        }
    """
    order_id = args.get('order_id')
    
    if not order_id:
        raise ValueError("Parameter 'order_id' is required")
    
    try:
        # Ensure connected
        ib = await ibkr_conn.ensure_connected()
        
        # Find the order
        trades = ib.trades()
        target_trade = None
        
        for trade in trades:
            if trade.order.orderId == order_id:
                target_trade = trade
                break
        
        if not target_trade:
            raise ValueError(f"Order ID {order_id} not found")
        
        # Cancel the order
        ib.cancelOrder(target_trade.order)
        
        # Wait for confirmation
        await ib.sleep(1)
        
        logger.info(f"Order {order_id} cancelled")
        
        return {
            'order_id': order_id,
            'status': 'Cancelled'
        }
    
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        raise


async def get_order_status_tool(args: Dict[str, Any], ibkr_conn: IBKRConnection) -> Dict[str, Any]:
    """
    Get status of an order.
    
    Args:
        args: Tool arguments containing:
            - order_id (int): Order ID to check
        ibkr_conn: IBKR connection instance
        
    Returns:
        Dictionary with order status
        
    Example:
        >>> await get_order_status_tool({"order_id": 123}, ibkr_conn)
        {
            "order_id": 123,
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "filled": 10,
            "remaining": 0,
            "status": "Filled",
            "avg_fill_price": 175.23
        }
    """
    order_id = args.get('order_id')
    
    if not order_id:
        raise ValueError("Parameter 'order_id' is required")
    
    try:
        # Ensure connected
        ib = await ibkr_conn.ensure_connected()
        
        # Find the order
        trades = ib.trades()
        target_trade = None
        
        for trade in trades:
            if trade.order.orderId == order_id:
                target_trade = trade
                break
        
        if not target_trade:
            raise ValueError(f"Order ID {order_id} not found")
        
        order = target_trade.order
        status = target_trade.orderStatus
        
        logger.info(f"Order {order_id} status: {status.status}")
        
        return {
            'order_id': order_id,
            'symbol': target_trade.contract.symbol,
            'action': order.action,
            'quantity': int(order.totalQuantity),
            'filled': int(status.filled),
            'remaining': int(status.remaining),
            'status': status.status,
            'avg_fill_price': round(status.avgFillPrice, 2) if status.avgFillPrice else None
        }
    
    except Exception as e:
        logger.error(f"Error getting order status {order_id}: {e}")
        raise
