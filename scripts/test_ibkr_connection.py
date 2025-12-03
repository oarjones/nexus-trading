"""
Test IBKR Gateway connection.

This script tests the connection to IB Gateway and verifies
paper trading account configuration.

Usage:
    python scripts/test_ibkr_connection.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ib_insync import IB


async def test_connection():
    """Test IBKR Gateway connection."""
    
    # IB Gateway Paper Trading Configuration
    HOST = '127.0.0.1'
    PORT = 4002  # IB Gateway paper trading port
    CLIENT_ID = 1
    
    print("=" * 60)
    print("IBKR GATEWAY CONNECTION TEST")
    print("=" * 60)
    print(f"Host: {HOST}")
    print(f"Port: {PORT}")
    print(f"Client ID: {CLIENT_ID}")
    print()
    
    ib = IB()
    
    try:
        print("Connecting to IB Gateway...")
        await ib.connectAsync(HOST, PORT, clientId=CLIENT_ID, timeout=10)
        print("✓ Connected successfully!")
        print()
        
        # Get account info
        accounts = ib.managedAccounts()
        account_id = accounts[0] if accounts else 'Unknown'
        
        print(f"Account ID: {account_id}")
        
        # Verify paper trading
        is_paper = account_id.startswith('DU')
        if is_paper:
            print("✓ Paper Trading Account (SAFE)")
        else:
            print("⚠️  WARNING: LIVE TRADING ACCOUNT DETECTED!")
        print()
        
        # Get account summary
        print("Account Summary:")
        account_values = ib.accountSummary()
        
        for item in account_values:
            if item.tag in ['NetLiquidation', 'TotalCashValue', 'BuyingPower']:
                print(f"  {item.tag}: {item.value} {item.currency}")
        
        print()
        print("=" * 60)
        print("✅ CONNECTION TEST PASSED!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Run IBKR server: cd mcp-servers/ibkr && python server.py")
        print("2. Run IBKR tests: pytest mcp-servers/tests/test_ibkr.py -v")
        
        ib.disconnect()
        return True
        
    except asyncio.TimeoutError:
        print("✗ Connection timeout")
        print()
        print("Troubleshooting:")
        print("1. Is IB Gateway running?")
        print("2. Is API enabled in Gateway settings?")
        print("3. Is port 4002 correct? (Check Gateway API settings)")
        return False
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Verify IB Gateway is running")
        print("2. Check API settings are enabled")
        print("3. Verify 'Read-Only API' is NOT checked")
        print("4. Check localhost (127.0.0.1) is in trusted IPs")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
