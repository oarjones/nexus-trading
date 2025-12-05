"""
Interactive Brokers (IBKR) Data Provider - Fase A1.3

Provides real-time quotes and historical data from Interactive Brokers
using the ib_insync library. Requires TWS or IB Gateway running.

Example:
    >>> provider = IBKRProvider(host='127.0.0.1', port=7497, client_id=1)
    >>> await provider.connect()
    >>> quote = await provider.get_quote('AAPL')
    >>> df = await provider.get_historical('AAPL', '1 Y', '1 day')
"""

from datetime import timezone
import logging
import asyncio
from datetime import datetime, date
from typing import Optional, Dict
import pandas as pd
from ib_insync import IB, Stock, Contract, util

logger = logging.getLogger(__name__)


class IBKRProvider:
    """
    Interactive Brokers data provider for real-time and historical data.
    
    Features:
    - Async connection to TWS/IB Gateway
    - Real-time quote retrieval (bid/ask/last)
    - Historical bars download
    - Connection health monitoring
    - Paper trading verification (safety check)
    - Automatic reconnection logic
    
    Attributes:
        host: IBKR Gateway/TWS host (default: 127.0.0.1)
        port: IBKR port (7497 for paper trading, 7496 for live)
        client_id: Client ID for connection (default: 1)
        ib: IB() instance from ib_insync
        connected: Connection status
    """
    
    # Port constants
    PAPER_TRADING_PORT = 7497
    LIVE_TRADING_PORT = 7496
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,
        client_id: int = 1,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize IBKR provider.
        
        Args:
            host: TWS/Gateway host address
            port: TWS/Gateway port (7497=paper, 7496=live)
            client_id: Unique client identifier
            timeout: Connection timeout in seconds
            max_retries: Maximum connection retries
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.ib = IB()
        self.connected = False
        
        logger.info(
            f"IBKR Provider initialized for {host}:{port} "
            f"(client_id={client_id})"
        )
    
    async def connect(self) -> bool:
        """
        Connect to TWS or IB Gateway with retry logic.
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If connection fails after retries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Connecting to IBKR at {self.host}:{self.port} (Attempt {attempt}/{self.max_retries})...")
                
                await self.ib.connectAsync(
                    self.host,
                    self.port,
                    clientId=self.client_id,
                    timeout=self.timeout
                )
                
                self.connected = True
                
                # Verify paper trading (safety check)
                if self.port == self.LIVE_TRADING_PORT:
                    logger.warning("⚠️  CONNECTED TO LIVE TRADING ACCOUNT!")
                else:
                    logger.info("✓ Connected to paper trading account")
                
                # Get account info
                # accounts = self.ib.managedAccounts()
                # logger.info(f"Connected accounts: {accounts}")
                
                return True
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2)  # Wait before retry
                else:
                    logger.error(f"Failed to connect to IBKR after {self.max_retries} attempts")
                    self.connected = False
                    # Don't raise here, just return False to allow fallback
                    return False
        return False
    
    def disconnect(self):
        """Disconnect from IBKR."""
        if self.connected:
            try:
                self.ib.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting from IBKR: {e}")
            finally:
                self.connected = False
                logger.info("Disconnected from IBKR")
    
    def _create_contract(self, symbol: str, exchange: str = 'SMART') -> Contract:
        """
        Create IBKR contract for a symbol.
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            exchange: Exchange to route through (default: 'SMART')
            
        Returns:
            Contract object
        """
        # Handle special cases if needed (e.g. forex)
        if len(symbol) == 7 and symbol[3] == '.': # e.g. EUR.USD
             # Forex logic could go here, for now assuming Stock
             pass
             
        contract = Stock(symbol, exchange, 'USD')
        return contract
    
    async def get_quote(self, symbol: str, exchange: str = 'SMART') -> Optional[Dict]:
        """
        Get current market quote for a symbol.
        
        Args:
            symbol: Stock ticker
            exchange: Exchange (default: 'SMART')
            
        Returns:
            Dictionary with quote data: {bid, ask, last, volume, timestamp}
            None if quote unavailable
            
        Raises:
            ConnectionError: If not connected to IBKR
        """
        if not self.connected:
            # Try auto-reconnect
            if not await self.connect():
                raise ConnectionError("Not connected to IBKR. Call connect() first.")
        
        try:
            contract = self._create_contract(symbol, exchange)
            
            # Request market data
            self.ib.reqMktData(contract, '', False, False)
            
            # Wait for data (max 2 seconds)
            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() < 2:
                await asyncio.sleep(0.1)
                ticker = self.ib.ticker(contract)
                if ticker.bid and ticker.ask: # We have some data
                    break
            
            # Get ticker data
            ticker = self.ib.ticker(contract)
            
            # Cancel market data subscription
            self.ib.cancelMktData(contract)
            
            if ticker:
                # Handle potential NaNs
                bid = float(ticker.bid) if ticker.bid == ticker.bid else None
                ask = float(ticker.ask) if ticker.ask == ticker.ask else None
                last = float(ticker.last) if ticker.last == ticker.last else None
                
                # If last is missing, try to use mid point
                if last is None and bid is not None and ask is not None:
                    last = (bid + ask) / 2
                
                quote = {
                    'symbol': symbol,
                    'bid': bid,
                    'ask': ask,
                    'last': last,
                    'volume': int(ticker.volume) if ticker.volume == ticker.volume else 0,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                logger.debug(f"Quote for {symbol}: {quote}")
                return quote
            else:
                logger.warning(f"No quote data available for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    async def get_historical(
        self,
        symbol: str,
        duration: str = '1 Y',
        bar_size: str = '1 day',
        exchange: str = 'SMART',
        what_to_show: str = 'TRADES'
    ) -> pd.DataFrame:
        """
        Download historical bars from IBKR.
        
        Args:
            symbol: Stock ticker
            duration: Duration string (e.g., '1 Y', '6 M', '30 D')
            bar_size: Bar size ('1 min', '5 mins', '1 hour', '1 day')
            exchange: Exchange (default: 'SMART')
            what_to_show: Data type ('TRADES', 'MIDPOINT', 'BID', 'ASK')
            
        Returns:
            DataFrame with OHLCV data in standard format
            
        Raises:
            ConnectionError: If not connected to IBKR
        """
        if not self.connected:
             # Try auto-reconnect
            if not await self.connect():
                raise ConnectionError("Not connected to IBKR. Call connect() first.")
        
        try:
            contract = self._create_contract(symbol, exchange)
            
            # Qualify contract
            await self.ib.qualifyContractsAsync(contract)
            
            logger.info(
                f"Downloading {duration} of {symbol} with {bar_size} bars..."
            )
            
            # Request historical data
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',  # Current time
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )
            
            if not bars:
                logger.warning(f"No historical data returned for {symbol}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = util.df(bars)
            
            if df is None or df.empty:
                 logger.warning(f"Empty DataFrame returned for {symbol}")
                 return pd.DataFrame()

            # Standardize format
            standardized = pd.DataFrame()
            standardized['time'] = pd.to_datetime(df['date'])
            standardized['symbol'] = symbol
            standardized['timeframe'] = self._normalize_bar_size(bar_size)
            standardized['open'] = df['open'].astype(float)
            standardized['high'] = df['high'].astype(float)
            standardized['low'] = df['low'].astype(float)
            standardized['close'] = df['close'].astype(float)
            standardized['volume'] = df['volume'].astype(float)
            standardized['source'] = 'ibkr'
            
            standardized.set_index('time', inplace=True)
            
            logger.info(f"Downloaded {len(standardized)} bars for {symbol}")
            
            return standardized
            
        except Exception as e:
            logger.error(f"Error downloading historical data for {symbol}: {e}")
            raise
    
    def _normalize_bar_size(self, bar_size: str) -> str:
        """
        Normalize IBKR bar size to standard timeframe format.
        
        Args:
            bar_size: IBKR bar size string
            
        Returns:
            Standard timeframe string
        """
        mapping = {
            '1 min': '1m',
            '5 mins': '5m',
            '15 mins': '15m',
            '30 mins': '30m',
            '1 hour': '1h',
            '1 day': '1d',
            '1 week': '1w',
            '1 month': '1M'
        }
        return mapping.get(bar_size, bar_size)
    
    async def get_account_summary(self) -> Dict:
        """
        Get account summary information.
        
        Returns:
            Dictionary with account info
            
        Raises:
            ConnectionError: If not connected
        """
        if not self.connected:
            if not await self.connect():
                raise ConnectionError("Not connected to IBKR. Call connect() first.")
        
        try:
            # Request account summary
            summary = self.ib.accountSummary()
            
            account_info = {}
            for item in summary:
                account_info[item.tag] = item.value
            
            logger.debug(f"Account summary: {list(account_info.keys())}")
            
            return account_info
            
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {}
    
    def is_connected(self) -> bool:
        """Check if currently connected to IBKR."""
        return self.connected and self.ib.isConnected()
    
    @property
    def name(self) -> str:
        """Provider name."""
        return "ibkr"
        
    def is_available(self) -> bool:
        """Check if provider is available (connected)."""
        return self.is_connected()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.disconnect()
    
    def __repr__(self) -> str:
        """String representation of provider."""
        status = "connected" if self.connected else "disconnected"
        return f"IBKRProvider(host={self.host}, port={self.port}, {status})"


# Convenience function for synchronous usage
def connect_ibkr(
    host: str = '127.0.0.1',
    port: int = 7497,
    client_id: int = 1
) -> IBKRProvider:
    """
    Synchronous helper to create and connect IBKR provider.
    
    Args:
        host: TWS/Gateway host
        port: TWS/Gateway port
        client_id: Client ID
        
    Returns:
        Connected IBKRProvider instance
        
    Example:
        >>> provider = connect_ibkr()
        >>> # Use provider...
        >>> provider.disconnect()
    """
    provider = IBKRProvider(host, port, client_id)
    
    # Run connection in event loop
    loop = asyncio.get_event_loop()
    loop.run_until_complete(provider.connect())
    
    return provider
