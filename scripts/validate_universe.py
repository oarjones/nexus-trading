#!/usr/bin/env python
"""
Validate that all symbols in the master universe meet criteria.

Usage:
    python scripts/validate_universe.py
    python scripts/validate_universe.py --check-liquidity  # Checks with real data (requires yfinance)
"""

import sys
import yaml
import asyncio
import argparse
from pathlib import Path
from collections import Counter

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SYMBOLS_FILE = project_root / "config" / "symbols.yaml"

# Validation criteria
REQUIRED_FIELDS = ["ticker", "name", "market", "source", "asset_type", "sector"]
VALID_MARKETS = ["US", "EU", "GLOBAL"]
VALID_SOURCES = ["ibkr", "yahoo"]
VALID_ASSET_TYPES = ["etf", "stock", "reit", "commodity", "bond"]
VALID_LIQUIDITY_TIERS = [1, 2, 3]


def load_symbols():
    """Load symbols from YAML."""
    if not SYMBOLS_FILE.exists():
        print(f"ERROR: File not found: {SYMBOLS_FILE}")
        return []
        
    with open(SYMBOLS_FILE, 'r') as f:
        data = yaml.safe_load(f)
    return data.get("symbols", [])


def validate_structure(symbols):
    """Validate basic structure of each symbol."""
    errors = []
    warnings = []
    
    tickers = []
    
    for i, sym in enumerate(symbols):
        prefix = f"Symbol #{i+1}"
        
        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in sym:
                errors.append(f"{prefix}: Missing required field '{field}'")
        
        if "ticker" not in sym:
            continue
            
        ticker = sym["ticker"]
        prefix = f"[{ticker}]"
        tickers.append(ticker)
        
        # Validate values
        if sym.get("market") not in VALID_MARKETS:
            errors.append(f"{prefix}: Invalid market '{sym.get('market')}'")
            
        if sym.get("source") not in VALID_SOURCES:
            errors.append(f"{prefix}: Invalid source '{sym.get('source')}'")
            
        if sym.get("asset_type") not in VALID_ASSET_TYPES:
            warnings.append(f"{prefix}: Unusual asset_type '{sym.get('asset_type')}'")
            
        if sym.get("liquidity_tier") and sym["liquidity_tier"] not in VALID_LIQUIDITY_TIERS:
            warnings.append(f"{prefix}: Invalid liquidity_tier '{sym.get('liquidity_tier')}'")
            
        # Check defensive flag consistency (heuristic)
        if sym.get("sector") in ["bonds", "utilities", "gold"] and not sym.get("defensive", False):
            # Just a debug note, not even a warning as it's optional
            # warnings.append(f"{prefix}: Consider setting defensive: true for sector '{sym.get('sector')}'")
            pass
    
    # Check duplicates
    ticker_counts = Counter(tickers)
    for ticker, count in ticker_counts.items():
        if count > 1:
            errors.append(f"[{ticker}]: Duplicate ticker ({count} occurrences)")
    
    return errors, warnings


def print_summary(symbols):
    """Print universe summary."""
    print("\n" + "=" * 60)
    print("UNIVERSE SUMMARY")
    print("=" * 60)
    
    print(f"\nTotal symbols: {len(symbols)}")
    
    # By market
    markets = Counter(s.get("market", "UNKNOWN") for s in symbols)
    print("\nBy Market:")
    for market, count in sorted(markets.items()):
        print(f"  {market}: {count}")
    
    # By asset type
    types = Counter(s.get("asset_type", "UNKNOWN") for s in symbols)
    print("\nBy Asset Type:")
    for atype, count in sorted(types.items()):
        print(f"  {atype}: {count}")
    
    # By sector (top 15)
    sectors = Counter(s.get("sector", "UNKNOWN") for s in symbols)
    print("\nBy Sector (top 15):")
    for sector, count in sectors.most_common(15):
        print(f"  {sector}: {count}")
    
    # By liquidity tier
    tiers = Counter(s.get("liquidity_tier", "N/A") for s in symbols)
    print("\nBy Liquidity Tier:")
    for tier, count in sorted(tiers.items()):
        print(f"  Tier {tier}: {count}")


async def check_liquidity(symbols, sample_size=10):
    """
    Check real liquidity of a sample of symbols.
    Requires internet connection and yfinance.
    """
    print("\n" + "=" * 60)
    print("LIQUIDITY CHECK (sample)")
    print("=" * 60)
    
    try:
        import yfinance as yf
        import random
        
        sample = random.sample(symbols, min(sample_size, len(symbols)))
        print(f"\nChecking {len(sample)} random symbols...")
        
        low_liquidity = []
        for sym in sample:
            ticker = sym["ticker"]
            # Fix ticker for Yahoo if needed (e.g., .DE for German stocks if market is EU but source is IBKR)
            # This is a simple check, mappings might be needed for real robust check
            y_ticker = ticker
            
            try:
                stock = yf.Ticker(y_ticker)
                info = stock.info
                # Some tickers might fail or return partial info
                avg_volume = info.get("averageVolume", 0)
                price = info.get("currentPrice", info.get("regularMarketPrice", 0))
                
                # Try simple volume check if price is missing (common in some yfinance versions/endpoints)
                if not price and "previousClose" in info:
                    price = info["previousClose"]
                
                volume_usd = avg_volume * price if price else 0
                
                status = "✓" if volume_usd >= 500000 else "✗"
                print(f"  {status} {ticker}: ${volume_usd:,.0f}/day (Price: ${price})")
                
                if volume_usd < 500000 and volume_usd > 0:
                    low_liquidity.append(ticker)
                    
            except Exception as e:
                print(f"  ? {ticker}: Error - {str(e)[:50]}...")
        
        if low_liquidity:
            print(f"\n⚠️  Low liquidity symbols (<$500k): {low_liquidity}")
            
    except ImportError:
        print("yfinance not installed. Run: pip install yfinance")
    except Exception as e:
        print(f"Liquidity check failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Validate universe configuration")
    parser.add_argument("--check-liquidity", action="store_true", 
                       help="Check real liquidity data (requires yfinance)")
    args = parser.parse_args()
    
    print(f"Loading symbols from {SYMBOLS_FILE}")
    symbols = load_symbols()
    
    if not symbols:
        print("ERROR: No symbols found!")
        sys.exit(1)
    
    # Validate structure
    errors, warnings = validate_structure(symbols)
    
    if errors:
        print("\n❌ ERRORS:")
        for e in errors:
            print(f"  - {e}")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    
    # Summary
    print_summary(symbols)
    
    # Check liquidity if requested
    if args.check_liquidity:
        asyncio.run(check_liquidity(symbols))
    
    # Exit code
    if errors:
        print("\n❌ Validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ Validation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
