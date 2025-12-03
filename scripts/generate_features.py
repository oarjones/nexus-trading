"""
Generate Historical Features Script

Generates ML features for all symbols in the registry using the Feature Store module.
Creates Parquet files partitioned by symbol and month, updates metadata in PostgreSQL,
and caches current day features in Redis.

Usage:
    python scripts/generate_features.py
    python scripts/generate_features.py --symbol AAPL
    python scripts/generate_features.py --start 2024-01-01
"""

import sys
import os
import logging
import argparse
from datetime import date, timedelta
from pathlib import Path
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data.symbols import SymbolRegistry
from src.data.feature_store import FeatureStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate ML features for trading symbols')
    
    parser.add_argument(
        '--symbol',
        type=str,
        help='Generate features for specific symbol only'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD), default: 2019-01-01'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD), default: today'
    )
    
    return parser.parse_args()


def validate_features(features_df, symbol):
    """
    Validate generated features.
    
    Args:
        features_df: DataFrame with features
        symbol: Symbol ticker
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'symbol': symbol,
        'total_rows': len(features_df),
        'total_features': len([c for c in features_df.columns if c not in ['time', 'symbol']]),
        'nan_percentage': {},
        'issues': []
    }
    
    # Check NaN percentages
    for col in features_df.columns:
        if col not in ['time', 'symbol']:
            nan_pct = features_df[col].isna().sum() / len(features_df) * 100
            results['nan_percentage'][col] = nan_pct
            
            if nan_pct > 5.0:
                results['issues'].append(f"Feature '{col}' has {nan_pct:.1f}% NaN values (>5% threshold)")
    
    # Check date range
    if 'time' in features_df.columns:
        min_date = features_df['time'].min()
        max_date = features_df['time'].max()
        results['date_range'] = f"{min_date.date()} to {max_date.date()}"
    
    return results


def main():
    """Generate features for all symbols."""
    args = parse_args()
    
    print('=' * 70)
    print('HISTORICAL FEATURES GENERATION')
    print('=' * 70)
    
    # Load environment
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    base_path = 'data/features'
    
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)
    
    # Parse dates
    start_date = date.fromisoformat(args.start) if args.start else date(2019, 1, 1)
    end_date = date.fromisoformat(args.end) if args.end else date.today()
    
    print(f"\nDate range: {start_date} to {end_date}")
    print(f"Feature path: {base_path}")
    print()
    
    # Initialize components
    print("[1/3] Initializing Feature Store...")
    feature_store = FeatureStore(base_path, db_url, redis_url)
    
    print("[2/3] Loading symbols...")
    registry = SymbolRegistry('config/symbols.yaml')
    
    # Filter symbols if specified
    if args.symbol:
        symbols = [s for s in registry.get_all() if s.ticker == args.symbol]
        if not symbols:
            print(f"ERROR: Symbol '{args.symbol}' not found in registry")
            sys.exit(1)
    else:
        symbols = registry.get_all()
    
    print(f"  → Processing {len(symbols)} symbols")
    print()
    
    # Statistics
    stats = {
        'total': len(symbols),
        'successful': 0,
        'failed': 0,
        'total_features_generated': 0,
        'total_rows': 0
    }
    
    errors = []
    validation_results = []
    
    print("[3/3] Generating features...")
    print('-' * 70)
    
    # Process each symbol
    for symbol in tqdm(symbols, desc="Symbols"):
        try:
            logger.info(f"Processing {symbol.ticker}...")
            
            # Generate features
            features_df = feature_store.generate_features(
                symbol.ticker,
                start_date,
                end_date
            )
            
            if features_df.empty:
                logger.warning(f"No features generated for {symbol.ticker}")
                stats['failed'] += 1
                errors.append((symbol.ticker, "No features generated"))
                continue
            
            # Validate features
            validation = validate_features(features_df, symbol.ticker)
            validation_results.append(validation)
            
            # Save to Parquet
            feature_store.save(symbol.ticker, features_df)
            
            # Update statistics
            stats['successful'] += 1
            stats['total_features_generated'] += validation['total_features']
            stats['total_rows'] += len(features_df)
            
            logger.info(
                f"  ✓ {symbol.ticker}: {len(features_df)} rows, "
                f"{validation['total_features']} features"
            )
            
        except Exception as e:
            logger.error(f"Error processing {symbol.ticker}: {e}")
            stats['failed'] += 1
            errors.append((symbol.ticker, str(e)))
    
    # Print summary
    print()
    print('=' * 70)
    print('GENERATION SUMMARY')
    print('=' * 70)
    print(f"Symbols processed:      {stats['successful']}/{stats['total']}")
    print(f"Total feature rows:     {stats['total_rows']:,}")
    print(f"Unique features:        {stats['total_features_generated'] // stats['successful'] if stats['successful'] > 0 else 0}")
    print(f"Failed:                 {stats['failed']}")
    print()
    
    # Validation summary
    if validation_results:
        print("VALIDATION RESULTS")
        print('-' * 70)
        
        total_issues = sum(len(v['issues']) for v in validation_results)
        
        if total_issues == 0:
            print("✓ All features passed validation (<5% NaN)")
        else:
            print(f"⚠ Found {total_issues} validation issues:")
            print()
            for result in validation_results:
                if result['issues']:
                    print(f"  {result['symbol']}:")
                    for issue in result['issues']:
                        print(f"    - {issue}")
            print()
        
        # NaN statistics
        all_nan_pcts = []
        for result in validation_results:
            all_nan_pcts.extend(result['nan_percentage'].values())
        
        if all_nan_pcts:
            avg_nan = sum(all_nan_pcts) / len(all_nan_pcts)
            max_nan = max(all_nan_pcts)
            print(f"Average NaN %:          {avg_nan:.2f}%")
            print(f"Max NaN %:              {max_nan:.2f}%")
            print()
    
    # Errors
    if errors:
        print(f"ERRORS ({len(errors)} symbols)")
        print('-' * 70)
        for symbol, error in errors[:10]:  # Show max 10
            print(f"  {symbol}: {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        print()
    
    print('=' * 70)
    print("✓ Feature generation complete!")
    print('=' * 70)
    
    # Exit code
    sys.exit(0 if stats['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
