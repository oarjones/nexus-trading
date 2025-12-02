"""
Data Pipeline Verification Script - Simple Version

Validates all Phase 1 data pipeline components without Unicode characters.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.symbols import SymbolRegistry
from src.data.providers.yahoo import YahooProvider
from sqlalchemy import create_engine, text
import pandas as pd


def print_header(text):
    """Print formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def check_yahoo_connection():
    """Verify Yahoo Finance connection."""
    print("Checking Yahoo Finance connection...")
    
    try:
        provider = YahooProvider()
        
        # Try downloading 1 day of SPY
        end = date.today()
        start = end - timedelta(days=1)
        df = provider.get_historical('SPY', start, end)
        
        if not df.empty:
            print(f"[PASS] Yahoo Finance: Connection OK ({len(df)} records)")
            return True, "Connection OK"
        else:
            print(f"[WARN] Yahoo Finance: No data returned")
            return False, "No data returned"
    
    except Exception as e:
        print(f"[FAIL] Yahoo Finance: Error - {e}")
        return False, str(e)


def check_timescale_data(db_url):
    """Verify TimescaleDB OHLCV data."""
    print("Checking TimescaleDB OHLCV data...")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Count total records
            result = conn.execute(text("SELECT COUNT(*) FROM market_data.ohlcv"))
            total_count = result.scalar()
            
            # Count symbols
            result = conn.execute(
                text("SELECT COUNT(DISTINCT symbol) FROM market_data.ohlcv")
            )
            symbol_count = result.scalar()
            
            # Date range
            result = conn.execute(
                text("SELECT MIN(time), MAX(time) FROM market_data.ohlcv")
            )
            row = result.fetchone()
            min_date, max_date = row
            
            if total_count > 0:
                print(
                    f"[PASS] TimescaleDB OHLCV: {total_count:,} records, "
                    f"{symbol_count} symbols"
                )
                print(f"       Date range: {min_date.date()} to {max_date.date()}")
                return True, f"{total_count:,} records, {symbol_count} symbols"
            else:
                print(f"[WARN] TimescaleDB OHLCV: No data")
                return False, "No data"
    
    except Exception as e:
        print(f"[FAIL] TimescaleDB OHLCV: Error - {e}")
        return False, str(e)


def check_indicators(db_url):
    """Verify indicators calculation."""
    print("Checking technical indicators...")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Count records
            result = conn.execute(text("SELECT COUNT(*) FROM market_data.indicators"))
            total_count = result.scalar()
            
            # Count indicators
            result = conn.execute(
                text("SELECT COUNT(DISTINCT indicator) FROM market_data.indicators")
            )
            indicator_count = result.scalar()
            
            # Count symbols
            result = conn.execute(
                text("SELECT COUNT(DISTINCT symbol) FROM market_data.indicators")
            )
            symbol_count = result.scalar()
            
            if total_count > 0:
                print(
                    f"[PASS] Indicators: {total_count:,} values, "
                    f"{indicator_count} indicators, {symbol_count} symbols"
                )
                
                # Show indicator list
                result = conn.execute(
                    text("SELECT DISTINCT indicator FROM market_data.indicators ORDER BY indicator LIMIT 10")
                )
                indicators = [row[0] for row in result]
                print(f"       Indicators: {', '.join(indicators)}")
                
                return True, f"{total_count:,} values"
            else:
                print(f"[WARN] Indicators: No data")
                return False, "No data"
    
    except Exception as e:
        print(f"[FAIL] Indicators: Error - {e}")
        return False, str(e)


def check_feature_store():
    """Verify Feature Store."""
    print("Checking Feature Store...")
    
    try:
        feature_path = Path('data/features')
        
        if not feature_path.exists():
            print(f"[WARN] Feature Store: Directory not found")
            return False, "Directory not found"
        
        # Count symbol directories
        symbol_dirs = [d for d in feature_path.iterdir() if d.is_dir() and d.name.startswith('symbol=')]
        
        # Count parquet files
        parquet_count = 0
        total_size = 0
        
        for symbol_dir in symbol_dirs:
            for month_dir in symbol_dir.iterdir():
                if month_dir.is_dir():
                    parquet_file = month_dir / 'features.parquet'
                    if parquet_file.exists():
                        parquet_count += 1
                        total_size += parquet_file.stat().st_size
        
        if parquet_count > 0:
            size_mb = total_size / (1024 * 1024)
            print(
                f"[PASS] Feature Store: {len(symbol_dirs)} symbols, "
                f"{parquet_count} parquet files ({size_mb:.1f} MB)"
            )
            return True, f"{len(symbol_dirs)} symbols, {parquet_count} files"
        else:
            print(f"[WARN] Feature Store: No parquet files")
            return False, "No files"
    
    except Exception as e:
        print(f"[FAIL] Feature Store: Error - {e}")
        return False, str(e)


def check_scheduler_config():
    """Verify scheduler configuration."""
    print("Checking scheduler configuration...")
    
    try:
        config_path = Path('config/scheduler.yaml')
        
        if not config_path.exists():
            print(f"[WARN] Scheduler Config: File not found")
            return False, "File not found"
        
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        jobs = config.get('jobs', {})
        enabled_jobs = [name for name, conf in jobs.items() if conf.get('enabled', False)]
        
        print(f"[PASS] Scheduler Config: {len(enabled_jobs)}/{len(jobs)} jobs enabled")
        for job_name in enabled_jobs:
            job = jobs[job_name]
            print(f"       - {job_name}: {job['hour']:02d}:{job['minute']:02d} {job.get('timezone', 'UTC')}")
        
        return True, f"{len(enabled_jobs)} jobs configured"
    
    except Exception as e:
        print(f"[FAIL] Scheduler Config: Error - {e}")
        return False, str(e)


def main():
    """Run all verification checks."""
    print_header("DATA PIPELINE VERIFICATION - Phase 1")
    
    # Load environment
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)
    
    # Run checks
    checks = [
        ("Yahoo Finance", check_yahoo_connection, []),
        ("TimescaleDB OHLCV", check_timescale_data, [db_url]),
        ("Indicators", check_indicators, [db_url]),
        ("Feature Store", check_feature_store, []),
        ("Scheduler Config", check_scheduler_config, []),
    ]
    
    results = []
    
    for name, check_fn, args in checks:
        success, message = check_fn(*args)
        results.append((name, success, message))
    
    # Summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, message in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status:8} {name:25} {message}")
    
    print(f"\n{'=' * 60}")
    print(f"Result: {passed}/{total} checks passed")
    
    if passed == total:
        print("[SUCCESS] All checks passed! Phase 1 pipeline is ready.")
    else:
        print(f"[WARNING] {total - passed} check(s) failed. Review above for details.")
    
    print(f"{'=' * 60}\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
