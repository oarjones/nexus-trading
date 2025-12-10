"""
Symbol Registry Module

Provides centralized management of trading symbols with metadata including
market classification, data sources, timezone information, and currency.

Example:
    >>> registry = SymbolRegistry('config/symbols.yaml')
    >>> eu_stocks = registry.get_by_market('EU')
    >>> yahoo_symbols = registry.get_by_source('yahoo')
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class Symbol:
    """
    Represents a trading symbol with metadata.
    
    Attributes:
        ticker: Symbol ticker (e.g., 'SAN.MC', 'AAPL', 'EURUSD=X')
        name: Full name of the instrument
        market: Market classification ('EU', 'US', 'FOREX', 'CRYPTO')
        source: Primary data source ('yahoo', 'ibkr', 'kraken')
        timezone: Timezone for trading hours (e.g., 'Europe/Madrid', 'America/New_York')
        currency: Quote currency (e.g., 'EUR', 'USD')
        asset_type: Type of asset ('stock', 'etf', 'forex', 'crypto')
        sector: Industry sector (e.g., 'technology', 'financials', 'healthcare')
        liquidity_tier: Liquidity classification (1=highest, 2=high, 3=moderate)
        defensive: Whether this is a defensive/safe-haven asset
    """
    ticker: str
    name: str
    market: str
    source: str
    timezone: str
    currency: str
    asset_type: str = 'stock'
    sector: str = 'unknown'
    liquidity_tier: int = 2
    defensive: bool = False
    ibkr_ticker: Optional[str] = None
    ibkr_exchange: Optional[str] = None
    
    def __post_init__(self):
        """Validate symbol data after initialization."""
        if not self.ticker:
            raise ValueError("Symbol ticker cannot be empty")
        if self.market not in ['EU', 'US', 'FOREX', 'CRYPTO']:
            logger.warning(f"Unusual market classification for {self.ticker}: {self.market}")
        if self.source not in ['yahoo', 'ibkr', 'kraken']:
            logger.warning(f"Unusual data source for {self.ticker}: {self.source}")
        if self.liquidity_tier not in [1, 2, 3]:
            logger.warning(f"Invalid liquidity_tier for {self.ticker}: {self.liquidity_tier}")


class SymbolRegistry:
    """
    Manages the catalog of trading symbols.
    
    Loads symbol definitions from a YAML configuration file and provides
    methods to filter and query symbols by various criteria.
    
    Example:
        >>> registry = SymbolRegistry('config/symbols.yaml')
        >>> all_symbols = registry.get_all()
        >>> eu_stocks = registry.get_by_market('EU')
        >>> yahoo_symbols = registry.get_by_source('yahoo')
        >>> san = registry.get_by_ticker('SAN.MC')
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the symbol registry.
        
        Args:
            config_path: Path to YAML configuration file containing symbol definitions
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        self.config_path = Path(config_path)
        self.symbols: List[Symbol] = []
        self._load_symbols()
    
    def _load_symbols(self):
        """
        Load symbols from YAML configuration file.
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If YAML is invalid or has missing required fields
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Symbol configuration not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'symbols' not in data:
                raise ValueError("Config file must contain 'symbols' key")
            
            symbol_list = data['symbols']
            if not isinstance(symbol_list, list):
                raise ValueError("'symbols' must be a list")
            
            for item in symbol_list:
                try:
                    symbol = Symbol(**item)
                    self.symbols.append(symbol)
                except TypeError as e:
                    logger.error(f"Invalid symbol definition: {item}. Error: {e}")
                    raise ValueError(f"Invalid symbol definition: {item}") from e
            
            logger.info(f"Loaded {len(self.symbols)} symbols from {self.config_path}")
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.config_path}: {e}") from e
    
    def get_all(self) -> List[Symbol]:
        """
        Get all symbols.
        
        Returns:
            List of all Symbol objects
        """
        return self.symbols.copy()
    
    def get_by_market(self, market: str) -> List[Symbol]:
        """
        Filter symbols by market.
        
        Args:
            market: Market classification ('EU', 'US', 'FOREX', 'CRYPTO')
            
        Returns:
            List of symbols matching the market
        """
        return [s for s in self.symbols if s.market == market]
    
    def get_by_source(self, source: str) -> List[Symbol]:
        """
        Filter symbols by data source.
        
        Args:
            source: Data source identifier ('yahoo', 'ibkr', 'kraken')
            
        Returns:
            List of symbols using the specified source
        """
        return [s for s in self.symbols if s.source == source]
    
    def get_by_ticker(self, ticker: str) -> Optional[Symbol]:
        """
        Get a specific symbol by ticker.
        
        Args:
            ticker: Symbol ticker (e.g., 'SAN.MC')
            
        Returns:
            Symbol object if found, None otherwise
        """
        for symbol in self.symbols:
            if symbol.ticker == ticker:
                return symbol
        return None
    
    def get_by_asset_type(self, asset_type: str) -> List[Symbol]:
        """
        Filter symbols by asset type.
        
        Args:
            asset_type: Type of asset ('stock', 'etf', 'forex', 'crypto')
            
        Returns:
            List of symbols matching the asset type
        """
        return [s for s in self.symbols if s.asset_type == asset_type]
    
    def get_tickers(self) -> List[str]:
        """
        Get list of all tickers.
        
        Returns:
            List of ticker strings
        """
        return [s.ticker for s in self.symbols]
    
    def count(self) -> int:
        """
        Get count of symbols in registry.
        
        Returns:
            Number of symbols
        """
        return len(self.symbols)
    
    def get_by_sector(self, sector: str) -> List[Symbol]:
        """
        Filter symbols by sector.
        
        Args:
            sector: Industry sector (e.g., 'technology', 'financials')
            
        Returns:
            List of symbols in the specified sector
        """
        return [s for s in self.symbols if s.sector == sector]
    
    def get_by_liquidity_tier(self, tier: int) -> List[Symbol]:
        """
        Filter symbols by liquidity tier.
        
        Args:
            tier: Liquidity tier (1=highest, 2=high, 3=moderate)
            
        Returns:
            List of symbols with specified liquidity tier
        """
        return [s for s in self.symbols if s.liquidity_tier == tier]
    
    def get_defensive(self) -> List[Symbol]:
        """
        Get all defensive/safe-haven symbols.
        
        Returns:
            List of defensive symbols (bonds, gold, utilities, etc.)
        """
        return [s for s in self.symbols if s.defensive]
    
    def get_high_liquidity(self) -> List[Symbol]:
        """
        Get symbols with highest liquidity (tier 1 and 2).
        
        Returns:
            List of high-liquidity symbols
        """
        return [s for s in self.symbols if s.liquidity_tier <= 2]
    
    def get_sectors(self) -> List[str]:
        """
        Get list of all unique sectors.
        
        Returns:
            List of sector names
        """
        return list(set(s.sector for s in self.symbols))
    
    def __repr__(self) -> str:
        """String representation of registry."""
        return f"SymbolRegistry(symbols={self.count()}, config='{self.config_path}')"
