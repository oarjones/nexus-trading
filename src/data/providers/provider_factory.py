"""
Data Provider Factory - Phase A1.3
"""

import logging
from typing import Optional, Protocol, Union
from datetime import date
import pandas as pd
import asyncio

from src.data.config import DataSourceConfig, DataSourceInfo

logger = logging.getLogger(__name__)


class DataProvider(Protocol):
    """Protocol that all data providers must implement."""
    
    @property
    def name(self) -> str:
        """Provider name."""
        ...
    
    def is_available(self) -> bool:
        """Check if provider is available."""
        ...
    
    async def get_historical(
        self,
        symbol: str,
        duration: str,
        bar_size: str,
        exchange: str = 'SMART'
    ) -> pd.DataFrame:
        """Get historical data."""
        ...
    
    async def get_quote(self, symbol: str) -> dict:
        """Get current quote."""
        ...


class ProviderFactory:
    """
    Factory to get the appropriate data provider.
    
    Implements automatic fallback logic when the primary
    provider is not available.
    
    Usage:
        factory = ProviderFactory()
        
        # Get data (uses primary or fallback automatically)
        df = await factory.get_historical("AAPL", "1 Y", "1 day")
        
        # Force a specific provider
        df = await factory.get_historical("AAPL", "1 Y", "1 day", force_source="yahoo")
    """
    
    def __init__(self, config_path: str = "config/data_sources.yaml"):
        self.config = DataSourceConfig(config_path)
        self._providers: dict[str, DataProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize enabled providers."""
        # Lazy imports to avoid circular dependencies
        from src.data.providers.ibkr import IBKRProvider
        from src.data.providers.yahoo import YahooProvider
        
        for source in self.config.get_enabled_sources():
            try:
                if source.name == 'ibkr':
                    ibkr_config = self.config.get_ibkr_config()
                    self._providers['ibkr'] = IBKRProvider(
                        host=ibkr_config.host,
                        port=ibkr_config.port,
                        client_id=ibkr_config.client_id,
                        timeout=ibkr_config.timeout_seconds
                    )
                    logger.info("IBKRProvider initialized")
                    
                elif source.name == 'yahoo':
                    yahoo_config = self.config.get_yahoo_config()
                    self._providers['yahoo'] = YahooProvider(
                        rate_limit=yahoo_config.rate_limit_seconds
                    )
                    logger.info("YahooProvider initialized")
                    
            except Exception as e:
                logger.warning(f"Could not initialize {source.name}: {e}")
    
    def get_provider(self, force_source: Optional[str] = None) -> Optional[DataProvider]:
        """
        Get the appropriate provider.
        
        Args:
            force_source: Force a specific provider (ignores priority)
        
        Returns:
            Available DataProvider or None if none available
        """
        if force_source:
            provider = self._providers.get(force_source)
            # For forced source, we return it even if not "available" (connected)
            # so the caller can try to connect
            if provider:
                return provider
            logger.warning(f"Forced provider '{force_source}' not found")
            return None
        
        # Try primary provider
        primary = self.config.get_primary_source()
        if primary and primary.name in self._providers:
            provider = self._providers[primary.name]
            if provider.is_available():
                return provider
            # If primary exists but not available, we might want to try connecting?
            # For now, we assume is_available() checks connection status
            logger.warning(f"Primary provider '{primary.name}' not available")
        
        # Try fallback
        fallback = self.config.get_fallback_source()
        if fallback and fallback.name in self._providers:
            provider = self._providers[fallback.name]
            if provider.is_available():
                logger.info(f"Using fallback: {fallback.name}")
                return provider
        
        # If no fallback available/configured, try any enabled provider
        for source in self.config.get_enabled_sources():
            if source.name in self._providers:
                provider = self._providers[source.name]
                if provider.is_available():
                     logger.info(f"Using available provider: {source.name}")
                     return provider

        logger.error("No providers available")
        return None
    
    async def get_historical(
        self,
        symbol: str,
        duration: str = "1 Y",
        bar_size: str = "1 day",
        force_source: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get historical data with automatic fallback.
        
        Args:
            symbol: Symbol to query
            duration: Historical duration
            bar_size: Bar size
            force_source: Force specific provider
        
        Returns:
            DataFrame with OHLCV or empty DataFrame if error
        """
        # Determine order of providers to try
        providers_to_try = []
        
        if force_source:
            if force_source in self._providers:
                providers_to_try.append(self._providers[force_source])
        else:
            # Primary
            primary = self.config.get_primary_source()
            if primary and primary.name in self._providers:
                providers_to_try.append(self._providers[primary.name])
            
            # Fallback
            fallback = self.config.get_fallback_source()
            if fallback and fallback.name in self._providers:
                providers_to_try.append(self._providers[fallback.name])
                
            # Others
            for name, provider in self._providers.items():
                if provider not in providers_to_try:
                    providers_to_try.append(provider)
        
        last_error = None
        
        for provider in providers_to_try:
            try:
                # Map symbol if needed
                mapped_symbol = self.config.get_symbol_for_source(symbol, provider.name)
                
                logger.info(f"Requesting historical data from {provider.name} for {mapped_symbol}")
                
                # Check availability (and try connect if needed/supported)
                if hasattr(provider, 'connect') and not provider.is_available():
                     try:
                         await provider.connect()
                     except Exception as e:
                         logger.warning(f"Could not connect to {provider.name}: {e}")
                         continue

                df = await provider.get_historical(
                    symbol=mapped_symbol,
                    duration=duration,
                    bar_size=bar_size
                )
                
                if df is not None and not df.empty:
                    self.config.mark_source_success(provider.name)
                    return df
                
            except Exception as e:
                logger.warning(f"Failed getting historical data from {provider.name}: {e}")
                self.config.mark_source_failure(provider.name)
                last_error = e
        
        logger.error(f"All providers failed for {symbol}. Last error: {last_error}")
        return pd.DataFrame()

    async def get_quote(
        self, 
        symbol: str,
        force_source: Optional[str] = None
    ) -> Optional[dict]:
        """
        Get current quote with fallback.
        """
        providers_to_try = []
        
        if force_source:
            if force_source in self._providers:
                providers_to_try.append(self._providers[force_source])
        else:
            # Primary
            primary = self.config.get_primary_source()
            if primary and primary.name in self._providers:
                providers_to_try.append(self._providers[primary.name])
            
            # Fallback
            fallback = self.config.get_fallback_source()
            if fallback and fallback.name in self._providers:
                providers_to_try.append(self._providers[fallback.name])
        
        for provider in providers_to_try:
            try:
                mapped_symbol = self.config.get_symbol_for_source(symbol, provider.name)
                
                 # Check availability
                if hasattr(provider, 'connect') and not provider.is_available():
                     try:
                         await provider.connect()
                     except Exception:
                         continue

                quote = await provider.get_quote(mapped_symbol)
                
                if quote:
                    self.config.mark_source_success(provider.name)
                    return quote
                    
            except Exception as e:
                logger.warning(f"Failed getting quote from {provider.name}: {e}")
                self.config.mark_source_failure(provider.name)
        
        return None
