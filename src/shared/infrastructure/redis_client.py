"""
Redis Client Wrapper.

Provides a singleton Redis client for the application.
Reads configuration from environment variables.
"""

import os
import redis
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisClient:
    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization if already connected
        if self._client is not None:
            return

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self._client = redis.from_url(
                redis_url, 
                decode_responses=True,
                socket_connect_timeout=2
            )
            logger.info(f"Redis client initialized: {redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self._client = None

    def get_client(self) -> redis.Redis:
        """Get the underlying redis client."""
        if self._client is None:
            # Retry connection or raise
            self.__init__()
            if self._client is None:
                raise ConnectionError("Redis client is not available")
        return self._client

    def is_connected(self) -> bool:
        """Check connection."""
        try:
            return self.get_client().ping()
        except Exception:
            return False

# Global accessor
def get_redis_client() -> redis.Redis:
    return RedisClient().get_client()
