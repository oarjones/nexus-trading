"""
Historical Data Loader - Slow Version

One-time script to populate database with 5 years of historical data.
Uses conservative rate limiting to avoid Yahoo Finance 429 errors.

Usage:
    python scripts/load_historical_slow.py
"""

import os
import sys
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.symbols import SymbolRegistry
from src.data.providers.yahoo import YahooProvider
from src.data.ingestion import OHLCVIngester
from src.data.indicators import IndicatorEngine
from src.data.feature_store import FeatureStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Load historical data for all symbols with conservative rate limiting."""
    print("=" * 60)
    print("HISTORICAL DATA LOADER - SLOW VERSION (Anti-Rate-Limit)")
    print("=" * 60)
    
    # Load environment
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)
    
    # Initialize components
    print("\n[1/5] Initializing components...")
    registry = SymbolRegistry('config/symbols.yaml')
    yahoo = YahooProvider(rate_limit=2.0)  # SLOWER: 2 seconds between requests
    ingester = OHLCVIngester(db_url)
    indicator_engine = IndicatorEngine(db_url)
    feature_store = FeatureStore('data/features', db_url, redis_url)
    
    symbols = registry.get_all()
    print(f"✓ Loaded {len(symbols)} symbols from registry")
    
    # Date range: 5 years
    end_date = date.today()
    start_date = date(2019, 1, 1)
    print(f"✓ Date range: {start_date} to {end_date}")
    print(f"\nNOTE: Using 2-second delay between symbols to avoid rate limiting")
    print(f"Estimated time: ~{len(symbols) * 2 / 60:.1f} minutes for downloads")
    
    # Statistics
    stats = {
        'total_symbols': len(symbols),
        'successful': 0,
        'failed': 0,
        'total_ohlcv': 0,
        'total_indicators': 0,
        'total_features': 0
    }
    
    errors = []
    
    print(f"\n[2/5] Downloading OHLCV data (ONE symbol at a time)...")
    print("-" * 60)
    
    # Process each symbol - ONE AT A TIME with delays
    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"\n[{i}/{len(symbols)}] Processing {symbol.ticker}...")
            
            # Step 1: Download OHLCV
            print(f"  → Downloading from Yahoo Finance...")
            df = yahoo._get_historical_sync(
                symbol.ticker,
                start=start_date,
                end=end_date,
                interval='1d'
            )
            
            if df.empty:
                logger.warning(f"No data returned for {symbol.ticker}, skipping")
                stats['failed'] += 1
                errors.append((symbol.ticker, "No data returned"))
                continue
            
            print(f"  → Downloaded {len(df)} bars")
            
            # Step 2: Ingest to database
            print(f"  → Ingesting to database...")
            result = ingester.ingest(df)
            stats['total_ohlcv'] += result['inserted'] + result['updated']
            
            print(f"  → Ingested: {result['inserted']} new, {result['updated']} updated")
            
            stats['successful'] += 1
            
            # IMPORTANT: Wait 2 seconds before next symbol to avoid rate limiting
            if i < len(symbols):
                print(f"  → Waiting 2 seconds before next symbol...")
                time.sleep(2.0)
            
        except Exception as e:
            logger.error(f"Error processing {symbol.ticker}: {e}")
            stats['failed'] += 1
            errors.append((symbol.ticker, str(e)))
            # Still wait even on error
            time.sleep(2.0)
    
    print(f"\n✓ Downloaded {stats['total_ohlcv']:,} OHLCV records")
    
    # Step 3: Calculate indicators
    print(f"\n[3/5] Calculating technical indicators...")
    print("-" * 60)
    
    for i, symbol in enumerate(symbols, 1):
        # Skip if download failed
        if any(err[0] == symbol.ticker for err in errors):
            continue
        
        try:
            print(f"[{i}/{len(symbols)}] Indicators for {symbol.ticker}...")
            
            # Load OHLCV from database
            from sqlalchemy import text
            import pandas as pd
            
            query = text("""
                SELECT time, open, high, low, close, volume
                FROM market_data.ohlcv
                WHERE symbol = :symbol AND timeframe = '1d'
                ORDER BY time
            """)
            
            with indicator_engine.engine.connect() as conn:
                ohlcv_df = pd.read_sql(
                    query,
                    conn,
                    params={'symbol': symbol.ticker}
                )
            
            if ohlcv_df.empty:
                continue
            
            ohlcv_df.set_index('time', inplace=True)
            
            # Calculate and persist
            result = indicator_engine.calculate_and_persist(ohlcv_df, symbol.ticker)
            stats['total_indicators'] += result['inserted'] + result['updated']
            
            print(f"  → {result['inserted']} new, {result['updated']} updated")
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol.ticker}: {e}")
    
    print(f"✓ Calculated {stats['total_indicators']:,} indicator values")
    
    # Step 4: Generate features
    print(f"\n[4/5] Generating features...")
    print("-" * 60)
    
    for i, symbol in enumerate(symbols, 1):
        # Skip if download failed
        if any(err[0] == symbol.ticker for err in errors):
            continue
        
        try:
            print(f"[{i}/{len(symbols)}] Features for {symbol.ticker}...")
            
            # Generate features
            features_df = feature_store.generate_features(
                symbol.ticker,
                start_date,
                end_date
            )
            
            if not features_df.empty:
                feature_store.save(symbol.ticker, features_df)
                stats['total_features'] += len(features_df)
                print(f"  → {len(features_df)} feature rows generated")
            
        except Exception as e:
            logger.error(f"Error generating features for {symbol.ticker}: {e}")
    
    print(f"✓ Generated {stats['total_features']:,} feature rows")
    
    # Summary
    print(f"\n[5/5] Summary")
    print("=" * 60)
    print(f"Symbols processed:    {stats['successful']}/{stats['total_symbols']}")
    print(f"OHLCV records:        {stats['total_ohlcv']:,}")
    print(f"Indicator values:     {stats['total_indicators']:,}")
    print(f"Feature rows:         {stats['total_features']:,}")
    print(f"Errors:               {stats['failed']}")
    
    if errors:
        print(f"\nErrors occurred for {len(errors)} symbols:")
        for ticker, error in errors[:10]:  # Show max 10 errors
            print(f"  - {ticker}: {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    
    print("\n✓ Historical data load complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
