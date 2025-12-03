"""
Technical Indicators Engine

Calculates technical indicators on OHLCV data and persists to TimescaleDB.
Uses pandas-ta for efficient vectorized calculations.

Example:
    >>> engine = IndicatorEngine(database_url)
    >>> indicators_df = engine.calculate_all(ohlcv_df)
    >>> result = engine.persist(indicators_df, 'AAPL')
"""

import logging
from typing import Dict, List, Optional
import pandas as pd
import pandas_ta as ta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.database import DatabasePool
from src.database import DatabasePool

logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    Calculates and persists technical indicators.
    
    Indicators implemented:
    - Moving Averages: SMA (20, 50, 200), EMA (12, 26)
    - Momentum: RSI(14), MACD (12, 26, 9)
    - Volatility: ATR(14), Bollinger Bands (20, 2)
    - Trend: ADX(14)
    
    Features:
    - Vectorized calculations using pandas-ta
    - Bulk persistence to TimescaleDB
    - Configurable indicator parameters
    - Missing data handling
    
    Attributes:
        db_url: Database connection string
        table_name: Target table for indicators
    """
    
    # Default indicator configuration
    INDICATORS_CONFIG = {
        'sma_20': {'func': 'sma', 'params': {'length': 20}},
        'sma_50': {'func': 'sma', 'params': {'length': 50}},
        'sma_200': {'func': 'sma', 'params': {'length': 200}},
        'ema_12': {'func': 'ema', 'params': {'length': 12}},
        'ema_26': {'func': 'ema', 'params': {'length': 26}},
        'rsi_14': {'func': 'rsi', 'params': {'length': 14}},
        'atr_14': {'func': 'atr', 'params': {'length': 14}},
        'adx_14': {'func': 'adx', 'params': {'length': 14}},
    }
    
    def __init__(self, db_url: str, table_name: str = 'market_data.indicators'):
        """
        Initialize indicator engine.
        
        Args:
            db_url: PostgreSQL/TimescaleDB connection string
            table_name: Target table for indicators
        """
        self.db_url = db_url
        self.table_name = table_name
        # self.engine = create_engine(db_url)
        self.engine = DatabasePool(db_url).get_engine()  # Use shared pool
        
        logger.info(f"Indicator Engine initialized for table: {table_name}")
    
    def calculate_all(self, df: pd.DataFrame, symbol: str = None, timeframe: str = '1d') -> pd.DataFrame:
        """
        Calculate all configured indicators for OHLCV data.
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            symbol: Symbol ticker (optional, for logging)
            timeframe: Timeframe string (default: '1d')
            
        Returns:
            DataFrame with calculated indicators in long format:
            Columns: time, symbol, timeframe, indicator, value
            
        Raises:
            ValueError: If DataFrame doesn't have required columns
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        if df.empty:
            logger.warning(f"Empty DataFrame provided for {symbol}")
            return pd.DataFrame()
        
        # Ensure we have enough data for longest lookback (200 for SMA_200)
        min_required = 200
        if len(df) < min_required:
            logger.warning(
                f"Insufficient data for {symbol}: {len(df)} rows (need {min_required}). "
                "Some indicators will have NaN values."
            )
        
        # Create a copy to avoid modifying original
        data = df.copy()
        
        # Calculate indicators
        indicators = {}
        
        try:
            # Simple Moving Averages
            indicators['sma_20'] = ta.sma(data['close'], length=20)
            indicators['sma_50'] = ta.sma(data['close'], length=50)
            indicators['sma_200'] = ta.sma(data['close'], length=200)
            
            # Exponential Moving Averages
            indicators['ema_12'] = ta.ema(data['close'], length=12)
            indicators['ema_26'] = ta.ema(data['close'], length=26)
            
            # RSI
            indicators['rsi_14'] = ta.rsi(data['close'], length=14)
            
            # MACD
            macd_result = ta.macd(data['close'], fast=12, slow=26, signal=9)
            if macd_result is not None:
                indicators['macd_line'] = macd_result[f'MACD_12_26_9']
                indicators['macd_signal'] = macd_result[f'MACDs_12_26_9']
                indicators['macd_hist'] = macd_result[f'MACDh_12_26_9']
            
            # ATR
            indicators['atr_14'] = ta.atr(data['high'], data['low'], data['close'], length=14)
            
            # Bollinger Bands
            bb_result = ta.bbands(data['close'], length=20, std=2)
            if bb_result is not None and not bb_result.empty:
                # Get actual column names (pandas_ta format may vary)
                bb_cols = bb_result.columns.tolist()
                bb_upper_col = [c for c in bb_cols if 'BBU' in c]
                bb_middle_col = [c for c in bb_cols if 'BBM' in c]
                bb_lower_col = [c for c in bb_cols if 'BBL' in c]
                
                if bb_upper_col and bb_middle_col and bb_lower_col:
                    indicators['bb_upper'] = bb_result[bb_upper_col[0]]
                    indicators['bb_middle'] = bb_result[bb_middle_col[0]]
                    indicators['bb_lower'] = bb_result[bb_lower_col[0]]
                    # Calculate BB width and position
                    indicators['bb_width'] = (bb_result[bb_upper_col[0]] - bb_result[bb_lower_col[0]]) / bb_result[bb_middle_col[0]]
                    # BB position: where price is within the bands (0 = lower, 0.5 = middle, 1 = upper)
                    bb_range = bb_result[bb_upper_col[0]] - bb_result[bb_lower_col[0]]
                    indicators['bb_position'] = (data['close'] - bb_result[bb_lower_col[0]]) / bb_range
            
            # ADX
            adx_result = ta.adx(data['high'], data['low'], data['close'], length=14)
            if adx_result is not None and not adx_result.empty:
                # Get actual column names
                adx_cols = adx_result.columns.tolist()
                adx_col = [c for c in adx_cols if 'ADX' in c and 'DM' not in c]
                dmp_col = [c for c in adx_cols if 'DMP' in c]
                dmn_col = [c for c in adx_cols if 'DMN' in c]
                
                if adx_col:
                    indicators['adx_14'] = adx_result[adx_col[0]]
                if dmp_col:
                    indicators['dmp_14'] = adx_result[dmp_col[0]]
                if dmn_col:
                    indicators['dmn_14'] = adx_result[dmn_col[0]]
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol}: {e}")
            raise
        
        # Convert to long format for database storage
        result_rows = []
        
        # Get time index
        if df.index.name == 'time':
            time_index = df.index
        elif 'time' in df.columns:
            time_index = df['time']
        else:
            # Use DataFrame index as time
            time_index = df.index
        
        for indicator_name, values in indicators.items():
            if values is None:
                continue
            
            for i, (timestamp, value) in enumerate(zip(time_index, values)):
                if pd.notna(value):  # Skip NaN values
                    result_rows.append({
                        'time': timestamp,
                        'symbol': symbol if symbol else 'unknown',
                        'timeframe': timeframe,
                        'indicator': indicator_name,
                        'value': float(value)
                    })
        
        result_df = pd.DataFrame(result_rows)
        
        if not result_df.empty:
            logger.info(
                f"Calculated {len(result_df)} indicator values for {symbol} "
                f"({len(indicators)} indicators × ~{len(df)} periods)"
            )
        
        return result_df
    
    def persist(self, indicators_df: pd.DataFrame) -> Dict[str, int]:
        """
        Persist indicators to TimescaleDB.
        
        Uses bulk upsert with ON CONFLICT.
        
        Args:
            indicators_df: DataFrame with columns: time, symbol, timeframe, indicator, value
            
        Returns:
            Dictionary with statistics: {'inserted': N, 'updated': M}
            
        Raises:
            ValueError: If DataFrame is invalid
            SQLAlchemyError: If database operation fails
        """
        if indicators_df.empty:
            logger.info("Empty indicators DataFrame, nothing to persist")
            return {'inserted': 0, 'updated': 0}
        
        # Validate required columns
        required_cols = ['time', 'symbol', 'timeframe', 'indicator', 'value']
        missing_cols = [col for col in required_cols if col not in indicators_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        try:
            with self.engine.connect() as conn:
                # Create temporary table
                temp_table = f"temp_indicators_{int(pd.Timestamp.now().timestamp())}"
                indicators_df.to_sql(temp_table, conn, if_exists='replace', index=False, method='multi')
                
                # Bulk upsert
                upsert_query = text(f"""
                    WITH upsert AS (
                        INSERT INTO {self.table_name} 
                        (time, symbol, timeframe, indicator, value)
                        SELECT time, symbol, timeframe, indicator, value
                        FROM {temp_table}
                        ON CONFLICT (time, symbol, timeframe, indicator) 
                        DO UPDATE SET value = EXCLUDED.value
                        RETURNING (xmax = 0) AS inserted
                    )
                    SELECT 
                        COUNT(*) FILTER (WHERE inserted) AS inserted_count,
                        COUNT(*) FILTER (WHERE NOT inserted) AS updated_count
                    FROM upsert
                """)
                
                result = conn.execute(upsert_query)
                row = result.fetchone()
                inserted_count = row[0] if row[0] is not None else 0
                updated_count = row[1] if row[1] is not None else 0
                
                # Drop temporary table
                conn.execute(text(f"DROP TABLE {temp_table}"))
                conn.commit()
            
            logger.info(f"Persisted indicators: {inserted_count} inserted, {updated_count} updated")
            
            return {
                'inserted': inserted_count,
                'updated': updated_count
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error persisting indicators: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error persisting indicators: {e}")
            raise
    
    def calculate_and_persist(
        self, 
        ohlcv_df: pd.DataFrame, 
        symbol: str, 
        timeframe: str = '1d'
    ) -> Dict[str, int]:
        """
        Convenience method to calculate and persist in one call.
        
        Args:
            ohlcv_df: DataFrame with OHLCV data
            symbol: Symbol ticker
            timeframe: Timeframe string
            
        Returns:
            Persistence statistics dictionary
        """
        indicators_df = self.calculate_all(ohlcv_df, symbol, timeframe)
        return self.persist(indicators_df)
    
    def get_indicator_count(self, symbol: str = None) -> int:
        """
        Get count of indicator records, optionally filtered by symbol.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            Number of indicator records
        """
        try:
            query = f"SELECT COUNT(*) FROM {self.table_name}"
            params = {}
            
            if symbol:
                query += " WHERE symbol = :symbol"
                params['symbol'] = symbol
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                count = result.scalar()
                return count
                
        except SQLAlchemyError as e:
            logger.error(f"Error counting indicators: {e}")
            return 0
    
    def __repr__(self) -> str:
        """String representation of engine."""
        return f"IndicatorEngine(table='{self.table_name}', indicators={len(self.INDICATORS_CONFIG)})"
