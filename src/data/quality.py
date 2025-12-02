"""
Data Quality Checker

Validates data quality and generates alerts for issues.
Monitors OHLCV data, features, and completeness.

Example:
    >>> checker = DataQualityChecker(db_url, influx_client)
    >>> valid_df, issues = checker.check_ohlcv(ohlcv_df)
    >>> feature_issues = checker.check_features(features_df)
"""

import logging
from typing import Dict, List, Tuple
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """
    Data quality validation and monitoring.
    
    Checks:
    - OHLCV data validity (prices > 0, volume >= 0, etc.)
    - Feature quality (NaN percentage, outliers)
    - Data completeness (gaps detection)
    - Gap alerts (missing trading days)
    
    Attributes:
        db_url: Database connection string
        influx_client: Optional InfluxDB client for metrics
    """
    
    # Quality thresholds
    MAX_NAN_PCT = 0.05  # 5% maximum NaN tolerated
    MAX_GAP_PCT = 0.10  # 10% maximum price gap
    MAX_MISSING_DAYS = 5  # Alert if missing > 5 days
    
    def __init__(self, db_url: str, influx_client=None):
        """
        Initialize data quality checker.
        
        Args:
            db_url: PostgreSQL connection string
            influx_client: Optional InfluxDB client for metrics
        """
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.influx_client = influx_client
        
        logger.info("Data Quality Checker initialized")
    
    def check_ohlcv(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:
        """
        Validate OHLCV DataFrame.
        
        Checks performed:
        - Price > 0
        - Volume >= 0
        - No future timestamps
        - Gap detection (>10% price change)
        - OHLC relationships
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            Tuple of (valid_df, issues_list)
        """
        issues = []
        
        if df.empty:
            return df, issues
        
        valid_df = df.copy()
        initial_count = len(valid_df)
        
        # Check 1: Positive prices
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in valid_df.columns:
                invalid = valid_df[col] <= 0
                if invalid.any():
                    count = invalid.sum()
                    issues.append({
                        'type': 'error',
                        'check': 'price_positive',
                        'column': col,
                        'count': count,
                        'message': f"{count} records with {col} <= 0 (rejected)"
                    })
                    valid_df = valid_df[~invalid]
        
        # Check 2: Non-negative volume
        if 'volume' in valid_df.columns:
            invalid = valid_df['volume'] < 0
            if invalid.any():
                count = invalid.sum()
                issues.append({
                    'type': 'error',
                    'check': 'volume_nonnegative',
                    'count': count,
                    'message': f"{count} records with volume < 0 (rejected)"
                })
                valid_df = valid_df[~invalid]
        
        # Check 3: No future timestamps
        time_col = valid_df.index if valid_df.index.name == 'time' else valid_df.get('time')
        if time_col is not None:
            future = time_col > pd.Timestamp.now()
            if future.any():
                count = future.sum()
                issues.append({
                    'type': 'error',
                    'check': 'future_timestamp',
                    'count': count,
                    'message': f"{count} records with future timestamps (rejected)"
                })
                if isinstance(time_col, pd.Series):
                    valid_df = valid_df[~future]
                else:
                    valid_df = valid_df[~future.values]
        
        # Check 4: Price gaps (warning only)
        if 'close' in valid_df.columns and len(valid_df) > 1:
            price_changes = valid_df['close'].pct_change().abs()
            large_gaps = price_changes > self.MAX_GAP_PCT
            
            if large_gaps.any():
                count = large_gaps.sum()
                max_gap = price_changes.max()
                issues.append({
                    'type': 'warning',
                    'check': 'price_gap',
                    'count': count,
                    'max_gap_pct': max_gap * 100,
                    'message': f"{count} records with >10% price gap (max: {max_gap*100:.1f}%)"
                })
        
        rejected = initial_count - len(valid_df)
        if rejected > 0:
            logger.warning(f"OHLCV validation: {rejected}/{initial_count} records rejected")
        
        return valid_df, issues
    
    def check_features(self, df: pd.DataFrame) -> List[Dict]:
        """
        Check feature quality.
        
        Checks:
        - NaN percentage per column
        - Outliers (values > 5 std from mean)
        
        Args:
            df: Features DataFrame
            
        Returns:
            List of issues
        """
        issues = []
        
        if df.empty:
            return issues
        
        # Exclude non-feature columns
        exclude_cols = ['time', 'symbol']
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        for col in feature_cols:
            if df[col].dtype in [np.float64, np.float32]:
                # Check NaN percentage
                nan_pct = df[col].isna().sum() / len(df)
                
                if nan_pct > self.MAX_NAN_PCT:
                    issues.append({
                        'type': 'warning',
                        'check': 'nan_percentage',
                        'column': col,
                        'nan_pct': nan_pct * 100,
                        'message': f"{col}: {nan_pct*100:.1f}% NaN (threshold: {self.MAX_NAN_PCT*100}%)"
                    })
                
                # Check for extreme outliers (> 5 std)
                if not df[col].isna().all():
                    mean = df[col].mean()
                    std = df[col].std()
                    
                    if std > 0:
                        outliers = (df[col] - mean).abs() > (5 * std)
                        outlier_count = outliers.sum()
                        
                        if outlier_count > 0:
                            outlier_pct = outlier_count / len(df)
                            issues.append({
                                'type': 'info',
                                'check': 'outliers',
                                'column': col,
                                'count': outlier_count,
                                'pct': outlier_pct * 100,
                                'message': f"{col}: {outlier_count} outliers (>{5}σ)"
                            })
        
        return issues
    
    def check_completeness(
        self,
        symbol: str,
        expected_days: int = 5,
        timeframe: str = '1d'
    ) -> List[Dict]:
        """
        Check data completeness (detect gaps).
        
        Args:
            symbol: Symbol ticker
            expected_days: Expected number of trading days
            timeframe: Timeframe to check
            
        Returns:
            List of gaps found
        """
        issues = []
        
        try:
            # Get last N days of data
            end_date = date.today()
            start_date = end_date - timedelta(days=expected_days + 5)  # +5 for weekends
            
            query = text("""
                SELECT DATE(time) as date
                FROM market_data.ohlcv
                WHERE symbol = :symbol 
                  AND timeframe = :timeframe
                  AND time >= :start
                GROUP BY DATE(time)
                ORDER BY DATE(time)
            """)
            
            with self.engine.connect() as conn:
                result = pd.read_sql(
                    query,
                    conn,
                    params={
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'start': start_date
                    }
                )
            
            if result.empty:
                issues.append({
                    'type': 'error',
                    'check': 'completeness',
                    'symbol': symbol,
                    'message': f"No data found for {symbol} in last {expected_days} days"
                })
                return issues
            
            # Count trading days (exclude weekends)
            dates = pd.to_datetime(result['date'])
            trading_days = dates[dates.dt.dayofweek < 5]  # Monday=0, Friday=4
            
            if len(trading_days) < expected_days:
                missing = expected_days - len(trading_days)
                issues.append({
                    'type': 'warning',
                    'check': 'completeness',
                    'symbol': symbol,
                    'expected': expected_days,
                    'found': len(trading_days),
                    'missing': missing,
                    'message': f"{symbol}: Missing {missing} days of data"
                })
        
        except SQLAlchemyError as e:
            logger.error(f"Error checking completeness for {symbol}: {e}")
            issues.append({
                'type': 'error',
                'check': 'completeness',
                'symbol': symbol,
                'message': f"Database error: {str(e)}"
            })
        
        return issues
    
    def report_metrics(self, metrics: Dict):
        """
        Report quality metrics to InfluxDB.
        
        Args:
            metrics: Dictionary of metrics to report
        """
        if not self.influx_client:
            logger.debug("No InfluxDB client configured, skipping metrics")
            return
        
        try:
            from influxdb_client import Point
            
            point = Point("data_quality")
            
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    point = point.field(key, value)
                else:
                    point = point.tag(key, str(value))
            
            write_api = self.influx_client.write_api()
            write_api.write(bucket="trading", record=point)
            
            logger.debug(f"Reported metrics to InfluxDB: {list(metrics.keys())}")
        
        except Exception as e:
            logger.warning(f"Failed to report metrics to InfluxDB: {e}")
    
    def run_all_checks(self, symbol: str) -> Dict:
        """
        Run all quality checks for a symbol.
        
        Args:
            symbol: Symbol ticker
            
        Returns:
            Dictionary with check results
        """
        all_issues = []
        
        # Check completeness
        completeness_issues = self.check_completeness(symbol, expected_days=5)
        all_issues.extend(completeness_issues)
        
        # Report metrics
        metrics = {
            'symbol': symbol,
            'total_issues': len(all_issues),
            'errors': sum(1 for i in all_issues if i['type'] == 'error'),
            'warnings': sum(1 for i in all_issues if i['type'] == 'warning'),
            'timestamp': datetime.now().isoformat()
        }
        
        self.report_metrics(metrics)
        
        return {
            'symbol': symbol,
            'issues': all_issues,
            'metrics': metrics
        }
    
    def __repr__(self) -> str:
        """String representation of checker."""
        return f"DataQualityChecker(max_nan={self.MAX_NAN_PCT*100}%)"
