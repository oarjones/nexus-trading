#!/usr/bin/env python3
"""
Data Configuration Verification - Phase A1.2
Run: python scripts/verify_data_config.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.config import DataSourceConfig

def main():
    print("DATA CONFIGURATION VERIFICATION - PHASE A1.2")
    print("=" * 50)
    
    try:
        # 1. Load configuration
        print("Loading configuration...")
        config = DataSourceConfig("config/data_sources.yaml")
        
        # 2. Verify sources
        primary = config.get_primary_source()
        fallback = config.get_fallback_source()
        
        print(f"Primary source: {primary.name if primary else 'None'}")
        print(f"Fallback source: {fallback.name if fallback else 'None'}")
        
        if not primary or primary.name != 'ibkr':
            print("❌ Error: Primary source should be 'ibkr'")
            return 1
            
        if not fallback or fallback.name != 'yahoo':
            print("❌ Error: Fallback source should be 'yahoo'")
            return 1
            
        # 3. Verify specific configs
        ibkr_config = config.get_ibkr_config()
        print(f"IBKR Host: {ibkr_config.host}:{ibkr_config.port}")
        
        if ibkr_config.port != 7497:
            print("❌ Error: Incorrect IBKR port (should be 7497 for paper)")
            return 1
            
        # 4. Verify mapping
        symbol = "EURUSD"
        mapped = config.get_symbol_for_source(symbol, "ibkr")
        print(f"Mapping {symbol} -> IBKR: {mapped}")
        
        if mapped != "EUR.USD":
            print(f"❌ Error: Incorrect mapping for {symbol}")
            return 1
            
        print("\n✅ CONFIGURATION OK - Task A1.2 completed")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
