"""
IBKR connection helper.

Manages connection to IBKR TWS/Gateway with retry logic.
"""

import logging
from typing import Optional
from ib_insync import IB, util
import asyncio

logger = logging.getLogger(__name__)


class IBKRConnection:
    """
    Manages IBKR connection with retry logic.
    
    Handles connection, disconnection, and automatic reconnection
    to TWS or IB Gateway.
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,  # 7497 = paper, 7496 = live
        client_id: int = 1,
        timeout: int = 30
    ):
        """
        Initialize IBKR connection helper.
        
        Args:
            host: TWS/Gateway host
            port: TWS/Gateway port (7497=paper, 7496=live)
            client_id: Unique client ID
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        
        self.ib: Optional[IB] = None
        self._connected = False
    
    async def connect(self) -> IB:
        """
        Connect to IBKR TWS/Gateway.
        
        Returns:
            IB instance
            
        Raises:
            ConnectionError: If connection fails
        """
        if self._connected and self.ib:
            return self.ib
        
        try:
            self.ib = IB()
            
            # Connect with timeout
            await asyncio.wait_for(
                self.ib.connectAsync(
                    self.host,
                    self.port,
                    clientId=self.client_id,
                    timeout=self.timeout
                ),
                timeout=self.timeout
            )
            
            self._connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            
            return self.ib
            
        except asyncio.TimeoutError:
            raise ConnectionError(
                f"Timeout connecting to IBKR at {self.host}:{self.port}. "
                "Is TWS/Gateway running?"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to IBKR: {e}")
    
    async def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib and self._connected:
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")
    
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected and self.ib is not None and self.ib.isConnected()
    
    async def ensure_connected(self) -> IB:
        """
        Ensure connection is active, reconnect if needed.
        
        Returns:
            IB instance
        """
        if not self.is_connected():
            logger.warning("IBKR connection lost, reconnecting...")
            await self.connect()
        
        return self.ib
