"""
MCP Servers Validation Test.
Simple test without complex path manipulation.
"""

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "mcp_servers"))

# Colors
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; B = '\033[94m'; X = '\033[0m'


async def test_risk():
    """Test risk server."""
    print(f"\n{B}═══ RISK SERVER ═══{X}\n")
    
    try:
        from risk.tools.limits import check_limits_tool
        from risk.tools.sizing import calculate_size_tool
        from risk.tools.exposure import get_exposure_tool
        
        # Limits
        result = await check_limits_tool({
            'symbol': 'AAPL', 'size': 15000, 'portfolio_value': 100000,
            'current_positions': [{'symbol': 'MSFT', 'size': 20000, 'sector': 'Tech'}],
            'sector': 'Tech'
        })
        print(f"{G}✓{X} Limits: {'OK' if result['allowed'] else 'REJECTED'}")
        
        # Sizing
        result = await calculate_size_tool({
            'portfolio_value': 100000, 'win_rate': 0.55,
            'avg_win': 0.025, 'avg_loss': 0.015
        })
        print(f"{G}✓{X} Size: ${result['suggested_size']:,.0f}")
        
        # Exposure
        result = await get_exposure_tool({
            'portfolio_value': 100000,
            'positions': [{'symbol': 'AAPL', 'size': 20000, 'sector': 'Tech', 
                          'market': 'US', 'currency': 'USD'}]
        })
        print(f"{G}✓{X} Exposure: HHI={result['concentration_metrics']['hhi']:.3f}")
        
        return True
    except Exception as e:
        print(f"{R}✗{X} {e}")
        return False


async def test_symbols():
    """Test symbols."""
    print(f"\n{B}═══ SYMBOLS SERVER ═══{X}\n")
    
    try:
        from market_data.tools.symbols import get_symbols_tool
        
        result = await get_symbols_tool({})
        print(f"{G}✓{X} Total: {result['count']}")
        
        result = await get_symbols_tool({'market': 'US'})
        print(f"{G}✓{X} US: {result['count']}")
        
        return True
    except Exception as e:
        print(f"{R}✗{X} {e}")
        return False


async def test_ibkr():
    """Test IBKR."""
    print(f"\n{B}═══ IBKR SERVER ═══{X}\n")
    
    try:
        from ibkr.tools.connection import IBKRConnection
        from ibkr.tools.account import get_account_tool
        
        conn = IBKRConnection(host='127.0.0.1', port=4002, client_id=1)
        await conn.connect()
        
        if conn.is_connected():
            result = await get_account_tool({}, conn)
            print(f"{G}✓{X} Account: {result['account_id']}")
            print(f"  Net: ${result['net_liquidation']:,.2f}")
            await conn.disconnect()
            return True
        else:
            print(f"{R}✗{X} Connection failed")
            return False
    except Exception as e:
        print(f"{Y}⚠{X} {e}")
        return False


async def main():

    print(f"{B}{'═'*50}{X}")
    print(f"{B}MCP SERVERS VALIDATION{X}")
    print(f"{B}{'═'*50}{X}")
    
    results = {
        'Risk': await test_risk(),
        'Symbols': await test_symbols(),
        'IBKR': await test_ibkr()
    }
    
    print(f"\n{B}{'═'*50}{X}")
    passed = sum(results.values())
    print(f"\nResults: {passed}/{len(results)}\n")
    
    for name, result in results.items():
        print(f"  {G + '✓' if result else R + '✗'}{X} {name}")
    
    if all(results.values()):
        print(f"\n{G}✅ ALL TESTS PASSED{X}")
        return 0
    else:
        print(f"\n{Y}⚠ SOME TESTS FAILED{X}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
