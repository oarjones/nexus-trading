"""
Feature Store

Generates, stores, and retrieves ML features for trading strategies.
Uses Parquet for efficient columnar storage, PostgreSQL for metadata,
and Redis for caching current day features.

Example:
    >>> store = FeatureStore(base_path='data/features', db_url=db, redis_url=redis)
    >>> features_df = store.generate_features('AAPL', date(2024, 1, 1), date.today())
    >>> store.save('AAPL', features_df)
    >>> loaded = store.load('AAPL', date(2024, 11, 1), date(2024, 12, 1))
"""

from datetime import timezone
import logging
import json
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Optional
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.database import DatabasePool
import redis

logger = logging.getLogger(__name__)


class FeatureStore:
    """
    Feature store for ML-ready trading features.
    
    Architecture:
    - Storage: Parquet files partitioned by symbol and month
    - Metadata: PostgreSQL features.catalog table
    - Cache: Redis for current day features
    
    Features generated (30+):
    - Momentum: returns, RSI, MACD
    - Volatility: ATR, BB width, volatility
    - Volume: volume ratios, OBV
    - Trend: SMA ratios, ADX, trend strength
    - Derived: slopes, momentum indicators
    
    Attributes:
        base_path: Root directory for Parquet files
        db_url: PostgreSQL connection string
        redis_client: Redis client for caching
    """
    
    def __init__(self, base_path: str, db_url: str, redis_url: str):
        """
        Initialize feature store.
        
        Args:
            base_path: Directory for Parquet files (e.g., 'data/features')
            db_url: PostgreSQL connection string
            redis_url: Redis connection string
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.db_url = db_url
        # self.engine = create_engine(db_url)
        self.engine = DatabasePool(db_url).get_engine()  # Use shared pool
        
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        logger.info(f"Feature Store initialized at {self.base_path}")
    
    def _get_symbol_path(self, symbol: str) -> Path:
        """Get directory path for symbol."""
        return self.base_path / f"symbol={symbol}"
    
    def _get_month_path(self, symbol: str, year: int, month: int) -> Path:
        """Get file path for symbol and month."""
        symbol_dir = self._get_symbol_path(symbol)
        return symbol_dir / f"{year:04d}-{month:02d}" / "features.parquet"
    
    def generate_features(
        self,
        symbol: str,
        start: date,
        end: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Generate features from OHLCV and indicators data.
        
        Loads data from TimescaleDB and calculates 30+ features.
        
        Args:
            symbol: Symbol ticker
            start: Start date
            end: End date
            timeframe: Timeframe (default: '1d')
            
        Returns:
            DataFrame with features (columns: time, symbol, feature columns)
            
        Raises:
            ValueError: If insufficient data
        """
        # Load OHLCV data
        ohlcv_query = text("""
            SELECT time, open, high, low, close, volume
            FROM market_data.ohlcv
            WHERE symbol = :symbol 
              AND timeframe = :timeframe
              AND time >= :start 
              AND time <= :end
            ORDER BY time
        """)
        
        with self.engine.connect() as conn:
            ohlcv_df = pd.read_sql(
                ohlcv_query,
                conn,
                params={'symbol': symbol, 'timeframe': timeframe, 'start': start, 'end': end}
            )
        
        if ohlcv_df.empty:
            raise ValueError(f"No OHLCV data found for {symbol} between {start} and {end}")
        
        ohlcv_df.set_index('time', inplace=True)
        
        # Load indicators
        indicators_query = text("""
            SELECT time, indicator, value
            FROM market_data.indicators
            WHERE symbol = :symbol 
              AND timeframe = :timeframe
              AND time >= :start 
              AND time <= :end
            ORDER BY time, indicator
        """)
        
        with self.engine.connect() as conn:
            indicators_df = pd.read_sql(
                indicators_query,
                conn,
                params={'symbol': symbol, 'timeframe': timeframe, 'start': start, 'end': end}
            )
        
        # Pivot indicators to wide format
        if not indicators_df.empty:
            indicators_wide = indicators_df.pivot(index='time', columns='indicator', values='value')
            # Merge with OHLCV
            data = ohlcv_df.join(indicators_wide, how='left')
        else:
            data = ohlcv_df
        
        # Generate features
        features = pd.DataFrame(index=data.index)
        features['symbol'] = symbol
        
        # === Momentum Features ===
        # Returns
        features['returns_1d'] = data['close'].pct_change(1)
        features['returns_5d'] = data['close'].pct_change(5)
        features['returns_20d'] = data['close'].pct_change(20)
        
        # RSI-based (if available)
        if 'rsi_14' in data.columns:
            features['rsi_14'] = data['rsi_14']
            features['rsi_slope'] = data['rsi_14'].diff(5)  # 5-day slope
        
        # MACD-based (if available)
        if 'macd_hist' in data.columns:
            features['macd_hist'] = data['macd_hist']
            features['macd_slope'] = data['macd_hist'].diff(3)
        
        # Momentum indicator
        # Use percentage returns (comparable across assets)
        features['momentum_5d'] = data['close'].pct_change(5)
        features['momentum_20d'] = data['close'].pct_change(20)
        
        # === Volatility Features ===
        # Rolling volatility (annualized - industry standard)
        daily_returns = data['close'].pct_change()
        features['volatility_20d'] = daily_returns.rolling(20).std() * np.sqrt(252)
        features['volatility_60d'] = daily_returns.rolling(60).std() * np.sqrt(252)
        
        # ATR-based (if available)
        if 'atr_14' in data.columns:
            features['atr_14'] = data['atr_14']
            features['atr_ratio'] = data['atr_14'] / data['close']  # ATR as % of price
        
        # Bollinger Bands features (if available)
        if 'bb_width' in data.columns:
            features['bb_width'] = data['bb_width']
        if 'bb_position' in data.columns:
            features['bb_position'] = data['bb_position']
        
        # High-Low range
        features['hl_ratio'] = (data['high'] - data['low']) / data['close']
        
        # === Volume Features ===
        # Volume ratios (protected against division by zero)
        vol_ma_20 = data['volume'].rolling(20).mean()
        vol_ma_60 = data['volume'].rolling(60).mean()
        
        features['volume_ratio_20d'] = np.where(
            vol_ma_20 > 0,
            data['volume'] / vol_ma_20,
            1.0  # Neutral if no average volume
        )
        
        features['volume_ratio_60d'] = np.where(
            vol_ma_60 > 0,
            data['volume'] / vol_ma_60,
            1.0
        )
        
        # OBV (On-Balance Volume) - normalized for cross-asset comparison
        obv = (np.sign(data['close'].diff()) * data['volume']).cumsum()
        obv_ma = obv.rolling(20).mean()
        
        features['obv_slope'] = np.where(
            obv_ma != 0,
            obv.diff(10) / obv_ma,  # Normalized slope
            0
        )
        
        # === Trend Features ===
        # SMA ratios (if available)
        if 'sma_20' in data.columns:
            features['sma_ratio_20'] = data['close'] / data['sma_20']
        if 'sma_50' in data.columns:
            features['sma_ratio_50'] = data['close'] / data['sma_50']
        if 'sma_200' in data.columns:
            features['sma_ratio_200'] = data['close'] / data['sma_200']
        
        # ADX-based (if available)
        if 'adx_14' in data.columns:
            features['adx_14'] = data['adx_14']
            features['trend_strength'] = data['adx_14'] / 100  # Normalize to 0-1
        
        # Price distance from highs/lows
        features['dist_from_52w_high'] = data['close'] / data['close'].rolling(252).max() - 1
        features['dist_from_52w_low'] = data['close'] / data['close'].rolling(252).min() - 1
        
        # === Derived Features ===
        # Moving average crossovers
        if 'sma_20' in data.columns and 'sma_50' in data.columns:
            features['sma_20_50_cross'] = (data['sma_20'] / data['sma_50']) - 1
        
        # Price acceleration
        features['price_accel'] = features['returns_1d'].diff(1)
        
        # Apply transformations
        features = self._apply_transforms(features)
        
        # Reset index to have time as column
        features = features.reset_index()
        
        logger.info(f"Generated {len(features.columns)-2} features for {symbol}, {len(features)} rows")
        
        return features
    
    def _apply_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply transformations to features.
        
        - Z-score normalization (rolling 60-day window)
        - Winsorization (1-99 percentile)
        
        Args:
            df: DataFrame with raw features
            
        Returns:
            Transformed DataFrame
        """
        # Skip symbol column
        feature_cols = [col for col in df.columns if col != 'symbol']
        
        transformed = df.copy()
        
        for col in feature_cols:
            if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
                # Winsorization (clip to 1st-99th percentile)
                p01 = df[col].quantile(0.01)
                p99 = df[col].quantile(0.99)
                transformed[col] = df[col].clip(lower=p01, upper=p99)
                
                # Rolling z-score (60-day window)
                rolling_mean = transformed[col].rolling(60, min_periods=20).mean()
                rolling_std = transformed[col].rolling(60, min_periods=20).std()
                
                # Add suffix to indicate z-scored
                transformed[f'{col}_zscore'] = (transformed[col] - rolling_mean) / rolling_std
        
        return transformed
    
    def save(self, symbol: str, features_df: pd.DataFrame):
        """
        Save features to Parquet files, partitioned by month.
        
        Updates metadata in PostgreSQL and caches current day in Redis.
        
        Args:
            symbol: Symbol ticker
            features_df: DataFrame with features (must have 'time' column)
            
        Raises:
            ValueError: If DataFrame is invalid
        """
        if features_df.empty:
            logger.warning(f"Empty features DataFrame for {symbol}, nothing to save")
            return
        
        if 'time' not in features_df.columns:
            raise ValueError("Features DataFrame must have 'time' column")
        
        # Ensure time is datetime
        features_df['time'] = pd.to_datetime(features_df['time'])
        
        # Partition by month
        features_df['year'] = features_df['time'].dt.year
        features_df['month'] = features_df['time'].dt.month
        
        partitions = features_df.groupby(['year', 'month'])
        
        for (year, month), partition_df in partitions:
            # Drop partitioning columns
            partition_df = partition_df.drop(columns=['year', 'month'])
            
            # Get file path
            file_path = self._get_month_path(symbol, year, month)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to Parquet
            table = pa.Table.from_pandas(partition_df)
            pq.write_table(table, file_path)
            
            logger.info(f"Saved {len(partition_df)} feature rows to {file_path}")
        
        # Update metadata in PostgreSQL
        self._update_metadata(symbol, features_df)
        
        # Cache current day features in Redis
        self._cache_today_features(symbol, features_df)
    
    def _update_metadata(self, symbol: str, features_df: pd.DataFrame):
        """Update feature metadata in PostgreSQL."""
        try:
            # Get feature names (exclude time and symbol)
            feature_cols = [col for col in features_df.columns if col not in ['time', 'symbol']]
            
            with self.engine.connect() as conn:
                for feature_name in feature_cols:
                    update_query = text("""
                        INSERT INTO features.catalog (feature_name, symbol, last_updated)
                        VALUES (:feature_name, :symbol, :updated)
                        ON CONFLICT (feature_name, symbol) 
                        DO UPDATE SET last_updated = EXCLUDED.last_updated
                    """)
                    
                    conn.execute(
                        update_query,
                        {
                            'feature_name': feature_name,
                            'symbol': symbol,
                            'updated': datetime.now(timezone.utc)
                        }
                    )
                
                conn.commit()
            
            logger.debug(f"Updated metadata for {len(feature_cols)} features")
            
        except SQLAlchemyError as e:
            logger.warning(f"Failed to update metadata: {e}")
    
    def _cache_today_features(self, symbol: str, features_df: pd.DataFrame):
        """Cache today's features in Redis."""
        try:
            today = date.today()
            today_features = features_df[features_df['time'].dt.date == today]
            
            if not today_features.empty:
                cache_key = f"features:{symbol}:{today.isoformat()}"
                cache_value = today_features.to_json(orient='records')
                
                # Cache with 24-hour TTL
                self.redis_client.setex(cache_key, 86400, cache_value)
                
                logger.debug(f"Cached {len(today_features)} today's features for {symbol}")
        
        except Exception as e:
            logger.warning(f"Failed to cache features: {e}")
    
    def load(
        self,
        symbol: str,
        start: date,
        end: date
    ) -> pd.DataFrame:
        """
        Load features from Parquet files.
        
        Checks Redis cache for current day, loads from Parquet for historical.
        
        Args:
            symbol: Symbol ticker
            start: Start date
            end: End date
            
        Returns:
            DataFrame with features
        """
        # Check Redis cache for today
        today = date.today()
        all_dfs = []
        
        if end >= today:
            cache_key = f"features:{symbol}:{today.isoformat()}"
            cached = self.redis_client.get(cache_key)
            
            if cached:
                today_df = pd.read_json(cached, orient='records')
                today_df['time'] = pd.to_datetime(today_df['time'])
                all_dfs.append(today_df)
                logger.debug(f"Loaded {len(today_df)} cached features for {symbol}")
                
                # Adjust end date to avoid duplicate
                end = today - pd.Timedelta(days=1)
        
        # Load from Parquet files
        symbol_dir = self._get_symbol_path(symbol)
        
        if not symbol_dir.exists():
            logger.warning(f"No feature data found for {symbol}")
            return pd.DataFrame()
        
        # Find relevant month directories
        start_ym = (start.year, start.month)
        end_ym = (end.year, end.month)
        
        for month_dir in sorted(symbol_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            
            try:
                # Parse year-month from directory name
                year, month = map(int, month_dir.name.split('-'))
                
                if (year, month) >= start_ym and (year, month) <= end_ym:
                    parquet_file = month_dir / "features.parquet"
                    
                    if parquet_file.exists():
                        df = pd.read_parquet(parquet_file)
                        df['time'] = pd.to_datetime(df['time'])
                        
                        # Filter by date range
                        df = df[(df['time'].dt.date >= start) & (df['time'].dt.date <= end)]
                        
                        if not df.empty:
                            all_dfs.append(df)
                            logger.debug(f"Loaded {len(df)} features from {parquet_file}")
            
            except (ValueError, OSError) as e:
                logger.warning(f"Error loading from {month_dir}: {e}")
                continue
        
        if not all_dfs:
            logger.warning(f"No features found for {symbol} between {start} and {end}")
            return pd.DataFrame()
        
        # Combine all DataFrames
        result = pd.concat(all_dfs, ignore_index=True)
        result = result.sort_values('time').reset_index(drop=True)
        
        logger.info(f"Loaded {len(result)} feature rows for {symbol}")
        
        return result
    
    def __repr__(self) -> str:
        """String representation of feature store."""
        return f"FeatureStore(base_path='{self.base_path}')"
