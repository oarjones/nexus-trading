"""
Database Infrastructure.

Provides SQLAlchemy engine and models for persistence.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

logger = logging.getLogger(__name__)

Base = declarative_base()

# --- Models ---

class PortfolioModel(Base):
    __tablename__ = 'portfolios'

    strategy_id = Column(String, primary_key=True)
    currency = Column(String, default="EUR")
    initial_capital = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    trades_count = Column(Integer, default=0)
    total_value = Column(Float, nullable=False) # Snapshot of total value
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    positions = relationship("PositionModel", back_populates="portfolio", cascade="all, delete-orphan")


class PositionModel(Base):
    __tablename__ = 'positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String, ForeignKey('portfolios.strategy_id'), nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(Float, nullable=False)
    current_price = Column(Float, default=0.0)
    entry_time = Column(DateTime, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    
    portfolio = relationship("PortfolioModel", back_populates="positions")



class TradeModel(Base):
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String, ForeignKey('portfolios.strategy_id'), nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False) # BUY / SELL
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    pnl = Column(Float, nullable=True) # Realized PnL (for sells)


class PortfolioHistoryModel(Base):
    """Snapshot of portfolio value over time for Equity Curve charting."""
    __tablename__ = 'portfolio_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String, ForeignKey('portfolios.strategy_id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    total_value = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)



# --- Database Connection ---

class Database:
    _instance: Optional['Database'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'engine'):
            return
            
        db_url = os.getenv("DATABASE_URL")
        # Fix for SQLAlchemy requiring postgresql:// instead of postgres://
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            
        if not db_url:
            # Fallback for local dev without env (dangerous but helpful)
            logger.warning("DATABASE_URL not set, using sqlite fallback for dev")
            db_url = "sqlite:///nexus_trading.db"
            
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info(f"Database initialized: {db_url.split('@')[-1]}") # Log host/db only

    def create_tables(self):
        """Create tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created/verified")

    def get_session(self):
        """Get a new session."""
        return self.SessionLocal()


# Global accessor
def get_db() -> Database:
    return Database()
