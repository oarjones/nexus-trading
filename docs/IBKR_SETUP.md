# Interactive Brokers (IBKR) Configuration Guide

## Prerequisites

1. **IBKR Account**: You need an Interactive Brokers account (Paper Trading or Live)
2. **TWS or IB Gateway**: Download and install from IBKR website
   - Trader Workstation (TWS): Full GUI application
   - IB Gateway: Lightweight headless version (recommended for automated trading)

## Setup Instructions

### Step 1: Download IB Gateway or TWS

**Recommended: IB Gateway (Standalone)**
- Download from: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- Install the application
- IB Gateway is lighter and designed for API connectivity

**Alternative: TWS (Full Platform)**
- Download from: https://www.interactivebrokers.com/en/trading/tws.php
- More features but heavier

### Step 2: Configure API Access

1. **Launch IB Gateway or TWS**
2. **Enable API Access:**
   - In TWS: Go to `File` → `Global Configuration` → `API` → `Settings`
   - In IB Gateway: Click on `Configure` → `Settings` → `API`
   
3. **Configure API Settings:**
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API: **Unchecked** (you need write access for trading)
   - ✅ Download open orders on connection: Checked (recommended)
   - Socket port: `7497` for Paper Trading, `7496` for Live Trading
   - Trusted IP addresses: Add `127.0.0.1` (localhost)

4. **Save changes and restart IB Gateway/TWS**

### Step 3: Configure Environment Variables

Edit your `.env` file (NOT `.env.example`) and add:

```env
# === Interactive Brokers (IBKR) ===
# Requires TWS or IB Gateway running
IBKR_HOST=127.0.0.1
IBKR_PORT=7497          # 7497 = Paper Trading, 7496 = Live Trading
IBKR_CLIENT_ID=1        # Unique ID (1-32, avoid conflicts if running multiple apps)
```

**Important Port Selection:**
- **7497 = Paper Trading** (Recommended for testing and development)
- **7496 = Live Trading** (Use ONLY when ready for real money!)

### Step 4: Test Connection

Run this Python script to verify connectivity:

```python
import asyncio
import os
from dotenv import load_dotenv
from src.data.providers.ibkr import IBKRProvider

load_dotenv()

async def test_connection():
    # Get credentials from environment
    host = os.getenv('IBKR_HOST', '127.0.0.1')
    port = int(os.getenv('IBKR_PORT', 7497))
    client_id = int(os.getenv('IBKR_CLIENT_ID', 1))
    
    print(f"Connecting to IBKR at {host}:{port}...")
    
    provider = IBKRProvider(host, port, client_id)
    
    try:
        await provider.connect()
        print("✅ Connected successfully!")
        
        # Get account summary
        summary = await provider.get_account_summary()
        print(f"Account value: ${summary.get('NetLiquidation', 'N/A')}")
        
        # Test getting a quote
        quote = await provider.get_quote('AAPL')
        if quote:
            print(f"AAPL Quote: Bid={quote['bid']}, Ask={quote['ask']}, Last={quote['last']}")
        
        # Test historical data
        df = await provider.get_historical('AAPL', '5 D', '1 day')
        print(f"Historical data: {len(df)} bars")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    
    finally:
        provider.disconnect()

# Run test
asyncio.run(test_connection())
```

## Troubleshooting

### Error: "Connection refused"
- ✅ Ensure IB Gateway or TWS is running
- ✅ Check that the port matches (7497 for paper, 7496 for live)
- ✅ Verify API is enabled in settings

### Error: "already in use"
- 🔄 Change `IBKR_CLIENT_ID` to a different number (1-32)
- 🔄 Close other applications connected to IBKR

### Error: "No security definition"
- 📝 Symbol might not be available or misspelled
- 📝 Try qualifying with exchange: `Stock('AAPL', 'SMART', 'USD')`

### "FA configuration required" warning
- ℹ️ Can be ignored for individual accounts
- ℹ️ Only relevant for Financial Advisor accounts

## Usage Examples

### Async Usage (Recommended)

```python
import asyncio
from src.data.providers.ibkr import IBKRProvider

async def main():
    provider = IBKRProvider(host='127.0.0.1', port=7497, client_id=1)
    
    async with provider:  # Automatically connects and disconnects
        # Get quote
        quote = await provider.get_quote('AAPL')
        print(quote)
        
        # Get historical data
        df = await provider.get_historical('MSFT', '1 Y', '1 day')
        print(df.head())

asyncio.run(main())
```

### Synchronous Usage

```python
from src.data.providers.ibkr import connect_ibkr

# Connect
provider = connect_ibkr(host='127.0.0.1', port=7497, client_id=1)

# Use provider...
# (Note: async methods need to be run in event loop)

# Disconnect
provider.disconnect()
```

## Integration with Data Pipeline

The IBKR connector is already integrated with the data pipeline scheduler. To enable it:

1. Update `config/symbols.yaml` to mark symbols with `source: ibkr`
2. The scheduler will automatically use IBKR for those symbols
3. Yahoo Finance remains the default for most symbols

## Security Notes

- 🔒 Never commit your actual credentials to git
- 🔒 Use `.env` for sensitive data (already in `.gitignore`)
- 🔒 Start with Paper Trading account (`port: 7497`)
- 🔒 Test thoroughly before switching to Live Trading

## Paper vs Live Trading

| Feature | Paper Trading (7497) | Live Trading (7496) |
|---------|---------------------|---------------------|
| Real money | ❌ No | ✅ Yes |
| Realistic quotes | ✅ Yes | ✅ Yes |
| Order execution | Simulated | Real |
| Risk | None | Real financial risk |
| **Recommended for** | Development & Testing | Production only |

---

**Next Steps:**
1. Install IB Gateway or TWS
2. Enable API in settings
3. Configure `.env` with your credentials
4. Run the test script above
5. Once connected, you're ready to use IBKR in the pipeline!
