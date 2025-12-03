"""
Quick verification script for Phase 1 corrections.
Tests that all modules import correctly and database pool works.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test all imports."""
    print("Testing imports...")
    
    try:
        from src.database import DatabasePool
        print("✓ DatabasePool imported")
        
        from src.data.ingestion import OHLCVIngester
        print("✓ OHLCVIngester imported")
        
        from src.data.indicators import IndicatorEngine
        print("✓ IndicatorEngine imported")
        
        from src.data.feature_store import FeatureStore
        print("✓ FeatureStore imported")
        
        from src.data.scheduler import DataScheduler
        print("✓ DataScheduler imported")
        
        print("\n✅ All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_pool():
    """Test database pool singleton."""
    print("\nTesting DatabasePool singleton...")
    
    try:
        from src.database import DatabasePool
        
        # Create two instances
        pool1 = DatabasePool("postgresql://test:test@localhost/test")
        pool2 = DatabasePool()
        
        # Should be same instance
        assert pool1 is pool2, "Singleton pattern broken"
        print("✓ Singleton pattern works")
        
        # Get engine
        engine = pool1.get_engine()
        print(f"✓ Engine created: {engine}")
        
        print("\n✅ DatabasePool tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ DatabasePool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = True
    
    success &= test_imports()
    success &= test_database_pool()
    
    if success:
        print("\n" + "="*50)
        print("✅ ALL VERIFICATION TESTS PASSED!")
        print("="*50)
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ SOME TESTS FAILED")
        print("="*50)
        sys.exit(1)
