"""
Database Connection Pool

Singleton pattern for managing database connections across all modules.
Reduces connection overhead and prevents "too many connections" errors.

Usage:
    from src.database import DatabasePool
    
    engine = DatabasePool(db_url).get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM table"))
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class DatabasePool:
    """
    Singleton connection pool for all database operations.
    
    Provides a shared SQLAlchemy engine with connection pooling
    to avoid creating multiple connections redundantly.
    
    Attributes:
        engine: Shared SQLAlchemy engine with connection pool
    
    Example:
        >>> pool = DatabasePool("postgresql://user:pass@localhost/db")
        >>> engine = pool.get_engine()
        >>> with engine.connect() as conn:
        >>>     result = conn.execute(text("SELECT 1"))
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, db_url: str = None):
        """
        Create or return existing singleton instance.
        
        Args:
            db_url: Database connection string (required first time)
        
        Returns:
            DatabasePool singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize(db_url)
        return cls._instance
    
    def _initialize(self, db_url: str):
        """
        Initialize the database engine with pooling.
        
        Args:
            db_url: SQLAlchemy connection string
        """
        if not db_url:
            raise ValueError("Database URL required for initialization")
        
        self.engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=10,           # Max connections in pool
            max_overflow=20,        # Max extra connections when pool full
            pool_pre_ping=True,     # Verify connection before use
            pool_recycle=3600,      # Recycle connections every hour
            echo=False              # Set to True for SQL logging
        )
        
        logger.info(f"Database connection pool initialized (size=10, max_overflow=20)")
    
    def get_engine(self):
        """
        Get the shared SQLAlchemy engine.
        
        Returns:
            SQLAlchemy Engine instance
        """
        return self.engine
    
    def dispose(self):
        """
        Close all connections and dispose of the pool.
        
        Call this when shutting down the application.
        """
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection pool disposed")
    
    def get_pool_status(self) -> dict:
        """
        Get current pool statistics.
        
        Returns:
            Dictionary with pool metrics
        """
        pool = self.engine.pool
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "max_overflow": pool._max_overflow
        }
