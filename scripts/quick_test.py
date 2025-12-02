"""
Quick test of core modules without database dependencies

Tests that can run immediately without infrastructure setup.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("PHASE 1 - QUICK MODULE TESTS")
print("=" * 60)

# Test 1: Symbol Registry
print("\n[1/5] Testing Symbol Registry...")
try:
    from src.data.symbols import SymbolRegistry
    
    registry = SymbolRegistry('config/symbols.yaml')
    symbols = registry.get_all()
    
    print(f"✅ Symbol Registry: {len(symbols)} symbols loaded")
    print(f"   - EU stocks: {len(registry.get_by_market('EU'))}")
    print(f"   - US stocks: {len(registry.get_by_market('US'))}")
    print(f"   - Forex: {len(registry.get_by_market('FOREX'))}")
    print(f"   - Crypto: {len(registry.get_by_market('CRYPTO'))}")
except Exception as e:
    print(f"❌ Symbol Registry failed: {e}")
    sys.exit(1)

# Test 2: Yahoo Provider (basic instantiation)
print("\n[2/5] Testing Yahoo Provider...")
try:
    from src.data.providers.yahoo import YahooProvider
    
    provider = YahooProvider(rate_limit=0.5)
    print(f"✅ Yahoo Provider: {provider}")
except Exception as e:
    print(f"❌ Yahoo Provider failed: {e}")
    sys.exit(1)

# Test 3: IBKR Provider (basic instantiation)
print("\n[3/5] Testing IBKR Provider...")
try:
    from src.data.providers.ibkr import IBKRProvider
    
    provider = IBKRProvider(host='127.0.0.1', port=7497, client_id=1)
    print(f"✅ IBKR Provider: {provider}")
except Exception as e:
    print(f"❌ IBKR Provider failed: {e}")
    sys.exit(1)

# Test 4: Indicator Engine (instantiation)
print("\n[4/5] Testing Indicators Engine...")
try:
    from src.data.indicators import IndicatorEngine
    import pandas as pd
    import numpy as np
    
    # Create sample OHLCV data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    sample_data = pd.DataFrame({
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 120, 100),
        'low': np.random.uniform(90, 100, 100),
        'close': np.random.uniform(95, 115, 100),
        'volume': np.random.uniform(1000000, 5000000, 100),
    }, index=dates)
    
    # Test indicator calculation (without DB)
    engine = IndicatorEngine('postgresql://dummy')  # Won't connect, just testing
    print(f"✅ Indicator Engine: {engine}")
    print(f"   - {len(engine.INDICATORS_CONFIG)} indicators configured")
except Exception as e:
    print(f"❌ Indicator Engine failed: {e}")
    sys.exit(1)

# Test 5: Feature Store (instantiation)
print("\n[5/5] Testing Feature Store...")
try:
    from src.data.feature_store import FeatureStore
    
    # Test instantiation (won't connect to DBs)
    print(f"✅ Feature Store: Module loaded successfully")
except Exception as e:
    print(f"❌ Feature Store failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL QUICK TESTS PASSED!")
print("=" * 60)
print("\nNext steps:")
print("1. Configure .env file with database credentials")
print("2. Ensure Docker services are running (docker-compose ps)")
print("3. Run: python scripts/verify_data_pipeline.py")
print("4. (Optional) Load historical data: python scripts/load_historical.py")
