"""
OHLCV Data Ingestion Service

Handles ingestion of OHLCV data into TimescaleDB with validation,
bulk insert/upsert capabilities, and quality checks.

Example:
    >>> ingester = OHLCVIngester(database_url)
    >>> result = ingester.ingest(ohlcv_dataframe)
    >>> print(f"Inserted: {result['inserted']}, Updated: {result['updated']}")
"""

from datetime import timezone
import logging
from typing import Dict, Tuple
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.database import DatabasePool

logger = logging.getLogger(__name__)


class OHLCVIngester:
    """
    Ingests OHLCV market data into TimescaleDB hypertable.
    
    Features:
    - Bulk insert/upsert for efficiency
    - Pre-insert data validation
    - Duplicate handling via ON CONFLICT
    - Statistics reporting (inserted/updated/rejected)
    - Detailed error logging
    
    Attributes:
        db_url: SQLAlchemy database URL
        table_name: Target table name (default: 'market_data.ohlcv')
    """
    
    def __init__(self, db_url: str, table_name: str = 'market_data.ohlcv'):
        """
        Initialize OHLCV ingester.
        
        Args:
            db_url: PostgreSQL/TimescaleDB connection string
            table_name: Target table (default: 'market_data.ohlcv')
        """
        self.db_url = db_url
        self.table_name = table_name
        self.engine = DatabasePool(db_url).get_engine()  # Use shared pool
        
        logger.info(f"OHLCV Ingester initialized for table: {table_name} (using connection pool)")
    
    def _validate_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
        """
        Validate OHLCV DataFrame before ingestion.
        
        Checks:
        - Required columns present
        - Correct data types
        - Price > 0
        - Volume >= 0
        - No future timestamps
        - OHLC relationships (high >= low, etc.)
        
        Args:
            df: DataFrame to validate
            
        Returns:
            Tuple of (validated_df, issues_list)
            - validated_df: Clean records ready for insert
            - issues_list: List of validation issue dicts
        """
        issues = []
        
        # Check required columns
        required_cols = ['symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Create a copy for validation
        valid_df = df.copy()
        
        # Check for empty DataFrame
        if valid_df.empty:
            logger.warning("Empty DataFrame provided for ingestion")
            return valid_df, issues
        
        initial_count = len(valid_df)
        
        # Validation 1: Positive prices
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            invalid_prices = valid_df[col] <= 0
            if invalid_prices.any():
                invalid_count = invalid_prices.sum()
                issues.append({
                    'type': 'invalid_price',
                    'column': col,
                    'count': invalid_count,
                    'message': f"{invalid_count} records with {col} <= 0"
                })
                valid_df = valid_df[~invalid_prices]
        
        # Validation 2: Non-negative volume
        invalid_volume = valid_df['volume'] < 0
        if invalid_volume.any():
            invalid_count = invalid_volume.sum()
            issues.append({
                'type': 'invalid_volume',
                'count': invalid_count,
                'message': f"{invalid_count} records with volume < 0"
            })
            valid_df = valid_df[~invalid_volume]
        
        # Validation 3: No future timestamps
        if 'time' in valid_df.columns or valid_df.index.name == 'time':
            time_col = valid_df.index if valid_df.index.name == 'time' else valid_df['time']
            future_times = time_col > pd.Timestamp.now()
            if future_times.any():
                invalid_count = future_times.sum()
                issues.append({
                    'type': 'future_timestamp',
                    'count': invalid_count,
                    'message': f"{invalid_count} records with future timestamps"
                })
                valid_df = valid_df[~future_times]
        
        # Validation 4: OHLC relationships
        # High should be >= Low
        invalid_high_low = valid_df['high'] < valid_df['low']
        if invalid_high_low.any():
            invalid_count = invalid_high_low.sum()
            issues.append({
                'type': 'invalid_ohlc',
                'count': invalid_count,
                'message': f"{invalid_count} records with high < low"
            })
            valid_df = valid_df[~invalid_high_low]
        
        # High should be >= Open and Close
        invalid_high_open = valid_df['high'] < valid_df['open']
        if invalid_high_open.any():
            invalid_count = invalid_high_open.sum()
            issues.append({
                'type': 'invalid_ohlc',
                'count': invalid_count,
                'message': f"{invalid_count} records with high < open"
            })
            valid_df = valid_df[~invalid_high_open]
        
        invalid_high_close = valid_df['high'] < valid_df['close']
        if invalid_high_close.any():
            invalid_count = invalid_high_close.sum()
            issues.append({
                'type': 'invalid_ohlc',
                'count': invalid_count,
                'message': f"{invalid_count} records with high < close"
            })
            valid_df = valid_df[~invalid_high_close]
        
        # Low should be <= Open and Close
        invalid_low_open = valid_df['low'] > valid_df['open']
        if invalid_low_open.any():
            invalid_count = invalid_low_open.sum()
            issues.append({
                'type': 'invalid_ohlc',
                'count': invalid_count,
                'message': f"{invalid_count} records with low > open"
            })
            valid_df = valid_df[~invalid_low_open]
        
        invalid_low_close = valid_df['low'] > valid_df['close']
        if invalid_low_close.any():
            invalid_count = invalid_low_close.sum()
            issues.append({
                'type': 'invalid_ohlc',
                'count': invalid_count,
                'message': f"{invalid_count} records with low > close"
            })
            valid_df = valid_df[~invalid_low_close]
        
        # Log validation results
        rejected_count = initial_count - len(valid_df)
        if rejected_count > 0:
            logger.warning(f"Validation rejected {rejected_count}/{initial_count} records")
            for issue in issues:
                logger.warning(f"  - {issue['message']}")
        
        return valid_df, issues
    
    def ingest(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Ingest OHLCV data into TimescaleDB.
        
        Performs bulk upsert using ON CONFLICT DO UPDATE.
        Validates data before insertion and reports statistics.
        
        Args:
            df: DataFrame with OHLCV data
               Required columns: symbol, timeframe, open, high, low, close, volume
               Index or column: time (timestamp)
               Optional column: source
               
        Returns:
            Dictionary with statistics:
            - 'inserted': Number of new records
            - 'updated': Number of updated records
            - 'rejected': Number of rejected records
            - 'issues': List of validation issues
            
        Raises:
            ValueError: If DataFrame is invalid
            SQLAlchemyError: If database operation fails
        """
        if df.empty:
            logger.info("Empty DataFrame, nothing to ingest")
            return {'inserted': 0, 'updated': 0, 'rejected': 0, 'issues': []}
        
        # Validate data
        valid_df, issues = self._validate_dataframe(df)
        rejected_count = len(df) - len(valid_df)
        
        if valid_df.empty:
            logger.warning("All records rejected during validation")
            return {
                'inserted': 0,
                'updated': 0,
                'rejected': rejected_count,
                'issues': issues
            }
        
        # Ensure 'time' is a column, not index
        if valid_df.index.name == 'time':
            valid_df = valid_df.reset_index()
        
        # Add source column if not present
        if 'source' not in valid_df.columns:
            valid_df['source'] = 'unknown'
        
        # Select only required columns in correct order
        columns_order = ['time', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume', 'source']
        valid_df = valid_df[columns_order]
        
        try:
            # Count existing records before upsert
            with self.engine.connect() as conn:
                # Create temporary table with data
                temp_table = f"temp_{int(datetime.now(timezone.utc).timestamp())}"
                valid_df.to_sql(temp_table, conn, if_exists='replace', index=False, method='multi')
                
                # Perform upsert
                upsert_query = text(f"""
                    WITH upsert AS (
                        INSERT INTO {self.table_name} 
                        (time, symbol, timeframe, open, high, low, close, volume, source)
                        SELECT time, symbol, timeframe, open, high, low, close, volume, source
                        FROM {temp_table}
                        ON CONFLICT (time, symbol, timeframe) 
                        DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            source = EXCLUDED.source
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
            
            logger.info(
                f"Ingestion complete: {inserted_count} inserted, "
                f"{updated_count} updated, {rejected_count} rejected"
            )
            
            return {
                'inserted': inserted_count,
                'updated': updated_count,
                'rejected': rejected_count,
                'issues': issues
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during ingestion: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during ingestion: {e}")
            raise
    
    def get_row_count(self, symbol: str = None, timeframe: str = None) -> int:
        """
        Get count of rows in OHLCV table, optionally filtered.
        
        Args:
            symbol: Optional symbol filter
            timeframe: Optional timeframe filter
            
        Returns:
            Number of rows
        """
        try:
            query = f"SELECT COUNT(*) FROM {self.table_name} WHERE 1=1"
            params = {}
            
            if symbol:
                query += " AND symbol = :symbol"
                params['symbol'] = symbol
            
            if timeframe:
                query += " AND timeframe = :timeframe"
                params['timeframe'] = timeframe
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                count = result.scalar()
                return count
                
        except SQLAlchemyError as e:
            logger.error(f"Error counting rows: {e}")
            return 0
    
    def __repr__(self) -> str:
        """String representation of ingester."""
        return f"OHLCVIngester(table='{self.table_name}')"
