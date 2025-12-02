"""
Data Pipeline Scheduler

Automates daily data pipeline execution using APScheduler.
Schedules jobs for OHLCV updates, indicator calculations, and feature generation.

Example:
    >>> scheduler = DataScheduler('config/scheduler.yaml', db_url, redis_url)
    >>> scheduler.setup_jobs()
    >>> scheduler.start()
    >>> # Scheduler runs in background
"""

import logging
import os
from datetime import date, timedelta
from pathlib import Path
import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.data.symbols import SymbolRegistry
from src.data.providers.yahoo import YahooProvider
from src.data.ingestion import OHLCVIngester
from src.data.indicators import IndicatorEngine
from src.data.feature_store import FeatureStore

logger = logging.getLogger(__name__)


class DataScheduler:
    """
    Scheduler for automated data pipeline execution.
    
    Jobs:
    1. OHLCV Update (18:30 CET) - Download latest market data
    2. Indicators (18:35 CET) - Calculate technical indicators
    3. Features (18:45 CET) - Generate ML features
    
    Uses APScheduler for cron-based job scheduling.
    
    Attributes:
        config: Job configuration from YAML
        scheduler: APScheduler instance
        db_url: Database connection string
        redis_url: Redis connection string
    """
    
    def __init__(self, config_path: str, db_url: str, redis_url: str):
        """
        Initialize data scheduler.
        
        Args:
            config_path: Path to scheduler.yaml configuration
            db_url: PostgreSQL connection string
            redis_url: Redis connection string
        """
        self.config_path = Path(config_path)
        self.db_url = db_url
        self.redis_url = redis_url
        
        # Load configuration
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
            self.config = config.get('jobs', {})
        
        # Initialize scheduler
        self.scheduler = BackgroundScheduler(
            timezone='Europe/Madrid',
            job_defaults={
                'coalesce': True,  # Combine missed runs
                'max_instances': 1  # Don't run job concurrently
            }
        )
        
        # Initialize components
        self.symbol_registry = SymbolRegistry('config/symbols.yaml')
        self.yahoo_provider = YahooProvider(rate_limit=0.5)
        self.ohlcv_ingester = OHLCVIngester(db_url)
        self.indicator_engine = IndicatorEngine(db_url)
        self.feature_store = FeatureStore('data/features', db_url, redis_url)
        
        logger.info(f"Data Scheduler initialized with config: {config_path}")
    
    def setup_jobs(self):
        """
        Configure all scheduled jobs from configuration.
        """
        # Job 1: OHLCV Update
        if self.config.get('ohlcv_update', {}).get('enabled', False):
            job_config = self.config['ohlcv_update']
            trigger = CronTrigger(
                hour=job_config['hour'],
                minute=job_config['minute'],
                timezone=job_config.get('timezone', 'Europe/Madrid')
            )
            
            self.scheduler.add_job(
                self.job_update_ohlcv,
                trigger=trigger,
                id='ohlcv_daily',
                name='Daily OHLCV Update',
                replace_existing=True
            )
            
            logger.info(
                f"Scheduled OHLCV update: {job_config['hour']:02d}:{job_config['minute']:02d} "
                f"{job_config.get('timezone', 'Europe/Madrid')}"
            )
        
        # Job 2: Calculate Indicators
        if self.config.get('indicators', {}).get('enabled', False):
            job_config = self.config['indicators']
            trigger = CronTrigger(
                hour=job_config['hour'],
                minute=job_config['minute'],
                timezone=job_config.get('timezone', 'Europe/Madrid')
            )
            
            self.scheduler.add_job(
                self.job_calculate_indicators,
                trigger=trigger,
                id='indicators_daily',
                name='Daily Indicators Calculation',
                replace_existing=True
            )
            
            logger.info(
                f"Scheduled indicators: {job_config['hour']:02d}:{job_config['minute']:02d} "
                f"{job_config.get('timezone', 'Europe/Madrid')}"
            )
        
        # Job 3: Generate Features
        if self.config.get('features', {}).get('enabled', False):
            job_config = self.config['features']
            trigger = CronTrigger(
                hour=job_config['hour'],
                minute=job_config['minute'],
                timezone=job_config.get('timezone', 'Europe/Madrid')
            )
            
            self.scheduler.add_job(
                self.job_generate_features,
                trigger=trigger,
                id='features_daily',
                name='Daily Features Generation',
                replace_existing=True
            )
            
            logger.info(
                f"Scheduled features: {job_config['hour']:02d}:{job_config['minute']:02d} "
                f"{job_config.get('timezone', 'Europe/Madrid')}"
            )
    
    def job_update_ohlcv(self):
        """
        Job: Update OHLCV data for all symbols.
        
        Downloads last 5 days to ensure no gaps.
        """
        logger.info("=== Starting OHLCV Update Job ===")
        
        try:
            symbols = self.symbol_registry.get_all()
            
            total_inserted = 0
            total_updated = 0
            errors = []
            
            for symbol in symbols:
                try:
                    logger.info(f"Updating {symbol.ticker}...")
                    
                    # Download last 5 days (to fill any gaps)
                    df = self.yahoo_provider.get_latest(symbol.ticker, days=5)
                    
                    if df.empty:
                        logger.warning(f"No data returned for {symbol.ticker}")
                        continue
                    
                    # Ingest to database
                    result = self.ohlcv_ingester.ingest(df)
                    
                    total_inserted += result['inserted']
                    total_updated += result['updated']
                    
                    if result['rejected'] > 0:
                        logger.warning(
                            f"{symbol.ticker}: {result['rejected']} records rejected"
                        )
                
                except Exception as e:
                    logger.error(f"Error updating {symbol.ticker}: {e}")
                    errors.append((symbol.ticker, str(e)))
            
            logger.info(
                f"=== OHLCV Update Complete: {total_inserted} inserted, "
                f"{total_updated} updated, {len(errors)} errors ==="
            )
            
            if errors:
                for ticker, error in errors:
                    logger.error(f"  {ticker}: {error}")
        
        except Exception as e:
            logger.error(f"Fatal error in OHLCV job: {e}", exc_info=True)
    
    def job_calculate_indicators(self):
        """
        Job: Calculate indicators for all symbols.
        
        Recalculates for last 250 days to handle rolling windows.
        """
        logger.info("=== Starting Indicators Calculation Job ===")
        
        try:
            symbols = self.symbol_registry.get_all()
            
            total_indicators = 0
            errors = []
            
            for symbol in symbols:
                try:
                    logger.info(f"Calculating indicators for {symbol.ticker}...")
                    
                    # Load last 250 days of OHLCV (for SMA200 + margin)
                    end_date = date.today()
                    start_date = end_date - timedelta(days=250)
                    
                    from sqlalchemy import text
                    import pandas as pd
                    
                    query = text("""
                        SELECT time, open, high, low, close, volume
                        FROM market_data.ohlcv
                        WHERE symbol = :symbol 
                          AND timeframe = '1d'
                          AND time >= :start
                        ORDER BY time
                    """)
                    
                    with self.indicator_engine.engine.connect() as conn:
                        df = pd.read_sql(
                            query,
                            conn,
                            params={'symbol': symbol.ticker, 'start': start_date}
                        )
                    
                    if df.empty:
                        logger.warning(f"No OHLCV data found for {symbol.ticker}")
                        continue
                    
                    df.set_index('time', inplace=True)
                    
                    # Calculate and persist
                    result = self.indicator_engine.calculate_and_persist(
                        df, symbol.ticker, '1d'
                    )
                    
                    total_indicators += result['inserted'] + result['updated']
                    
                    logger.info(
                        f"{symbol.ticker}: {result['inserted']} new, {result['updated']} updated"
                    )
                
                except Exception as e:
                    logger.error(f"Error calculating indicators for {symbol.ticker}: {e}")
                    errors.append((symbol.ticker, str(e)))
            
            logger.info(
                f"=== Indicators Calculation Complete: {total_indicators} total, "
                f"{len(errors)} errors ==="
            )
            
            if errors:
                for ticker, error in errors:
                    logger.error(f"  {ticker}: {error}")
        
        except Exception as e:
            logger.error(f"Fatal error in indicators job: {e}", exc_info=True)
    
    def job_generate_features(self):
        """
        Job: Generate features for all symbols.
        
        Generates features for last 60 days (enough for rolling windows).
        """
        logger.info("=== Starting Features Generation Job ===")
        
        try:
            symbols = self.symbol_registry.get_all()
            
            total_features = 0
            errors = []
            
            for symbol in symbols:
                try:
                    logger.info(f"Generating features for {symbol.ticker}...")
                    
                    # Generate for last 60 days
                    end_date = date.today()
                    start_date = end_date - timedelta(days=60)
                    
                    features_df = self.feature_store.generate_features(
                        symbol.ticker, start_date, end_date, '1d'
                    )
                    
                    if not features_df.empty:
                        self.feature_store.save(symbol.ticker, features_df)
                        total_features += len(features_df)
                        
                        logger.info(f"{symbol.ticker}: {len(features_df)} feature rows generated")
                
                except Exception as e:
                    logger.error(f"Error generating features for {symbol.ticker}: {e}")
                    errors.append((symbol.ticker, str(e)))
            
            logger.info(
                f"=== Features Generation Complete: {total_features} total rows, "
                f"{len(errors)} errors ==="
            )
            
            if errors:
                for ticker, error in errors:
                    logger.error(f"  {ticker}: {error}")
        
        except Exception as e:
            logger.error(f"Fatal error in features job: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler gracefully."""
        self.scheduler.shutdown()
        logger.info("Scheduler shutdown")
    
    def get_jobs(self):
        """Get list of scheduled jobs."""
        return self.scheduler.get_jobs()
    
    def __repr__(self) -> str:
        """String representation of scheduler."""
        return f"DataScheduler(jobs={len(self.scheduler.get_jobs())})"
