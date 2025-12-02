"""
Calculate indicators for all loaded OHLCV data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.indicators import IndicatorEngine
from sqlalchemy import text
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

print('=' * 60)
print('CALCULATING TECHNICAL INDICATORS')
print('=' * 60)

engine = IndicatorEngine(os.getenv('DATABASE_URL'))

# Get list of symbols with data
with engine.engine.connect() as conn:
    result = conn.execute(text('SELECT DISTINCT symbol FROM market_data.ohlcv ORDER BY symbol'))
    symbols = [row[0] for row in result]

print(f'\nFound {len(symbols)} symbols with OHLCV data')
print()

total_inserted = 0
total_updated = 0

for i, symbol in enumerate(symbols, 1):
    print(f'[{i}/{len(symbols)}] {symbol}...')
    
    # Load OHLCV
    query = text('''
        SELECT time, open, high, low, close, volume
        FROM market_data.ohlcv
        WHERE symbol = :symbol AND timeframe = '1d'
        ORDER BY time
    ''')
    
    with engine.engine.connect() as conn:
        df = pd.read_sql(query, conn, params={'symbol': symbol})
    
    if df.empty:
        print(f'  No data')
        continue
    
    df.set_index('time', inplace=True)
    
    # Calculate and persist
    result = engine.calculate_and_persist(df, symbol, '1d')
    total_inserted += result['inserted']
    total_updated += result['updated']
    print(f'  {result["inserted"]} inserted, {result["updated"]} updated')

print()
print('=' * 60)
print(f'TOTAL: {total_inserted} indicators calculated')
print('=' * 60)
