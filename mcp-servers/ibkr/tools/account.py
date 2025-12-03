"""
Account information tool.

Retrieves IBKR account information and balances.
"""

import logging
from typing import Dict, Any
from .connection import IBKRConnection

logger = logging.getLogger(__name__)


async def get_account_tool(args: Dict[str, Any], ibkr_conn: IBKRConnection) -> Dict[str, Any]:
    """
    Get IBKR account information.
    
    Retrieves account summary including:
    - Net liquidation value
    - Cash balance
    - Buying power
    - Account type (paper/live)
    
    Args:
        args: Tool arguments (none required)
        ibkr_conn: IBKR connection instance
        
    Returns:
        Dictionary with account information
        
    Example:
        >>> await get_account_tool({}, ibkr_conn)
        {
            "account_id": "DU1234567",
            "account_type": "paper",
            "net_liquidation": 100000.00,
            "cash_balance": 45000.00,
            "buying_power": 180000.00,
            "currency": "USD"
        }
    """
    try:
        # Ensure connected
        ib = await ibkr_conn.ensure_connected()
        
        # Get account summary
        account_values = ib.accountSummary()
        
        # Extract key values
        account_info = {}
        
        for item in account_values:
            if item.tag == 'NetLiquidation':
                account_info['net_liquidation'] = float(item.value)
            elif item.tag == 'TotalCashValue':
                account_info['cash_balance'] = float(item.value)
            elif item.tag == 'BuyingPower':
                account_info['buying_power'] = float(item.value)
            elif item.tag == 'AccountType':
                account_info['account_type'] = item.value
        
        # Get account ID
        accounts = ib.managedAccounts()
        account_id = accounts[0] if accounts else 'Unknown'
        
        # Detect if paper trading (DU prefix = paper)
        is_paper = account_id.startswith('DU')
        
        logger.info(f"Retrieved account info for {account_id} ({'PAPER' if is_paper else 'LIVE'})")
        
        return {
            'account_id': account_id,
            'account_type': 'paper' if is_paper else 'live',
            'net_liquidation': round(account_info.get('net_liquidation', 0), 2),
            'cash_balance': round(account_info.get('cash_balance', 0), 2),
            'buying_power': round(account_info.get('buying_power', 0), 2),
            'currency': 'USD'  # Could be extended to support multi-currency
        }
    
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        raise
