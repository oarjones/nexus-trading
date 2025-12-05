#!/usr/bin/env python3
"""
Provider Factory Verification - Phase A1.3
Run: python scripts/verify_provider_factory.py
"""

import sys
import os
import asyncio
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.providers.provider_factory import ProviderFactory

async def main():
    print("PROVIDER FACTORY VERIFICATION - PHASE A1.3")
    print("=" * 50)
    
    try:
        # 1. Initialize Factory
        print("Initializing Factory...")
        factory = ProviderFactory("config/data_sources.yaml")
        
        # 2. Verify loaded providers
        print(f"Loaded providers: {list(factory._providers.keys())}")
        
        if 'ibkr' not in factory._providers:
            print("❌ Error: IBKR provider not loaded")
            return 1
            
        if 'yahoo' not in factory._providers:
            print("❌ Error: Yahoo provider not loaded")
            return 1
            
        # 3. Test Fallback (Forcing IBKR failure or using Yahoo directly)
        # Since TWS is not running, IBKR will fail and should fallback to Yahoo
        print("\nTesting historical data fetch (should fallback to Yahoo)...")
        
        symbol = "AAPL"
        df = await factory.get_historical(symbol, duration="1 M", bar_size="1 day")
        
        if df.empty:
            print("❌ Error: No data returned")
            return 1
            
        source = df['source'].iloc[0]
        print(f"Data source: {source}")
        print(f"Records: {len(df)}")
        print(f"Last price: {df['close'].iloc[-1]}")
        
        if source != 'yahoo':
            print("⚠️ Note: Expected 'yahoo' if TWS is not running")
        else:
            print("✅ Fallback to Yahoo worked correctly")
            
        # 4. Test Quote
        print("\nTesting quote fetch...")
        quote = await factory.get_quote(symbol)
        
        if quote:
            print(f"Quote: {quote}")
            print("✅ Quote fetched correctly")
        else:
            print("❌ Error: No quote returned")
            return 1
            
        print("\n✅ PROVIDER FACTORY OK - Task A1.3 completed")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(main()))
