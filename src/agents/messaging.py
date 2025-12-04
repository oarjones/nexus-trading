"""
Redis pub/sub messaging system for inter-agent communication.

Provides MessageBus class for publishing and subscribing to channels with
automatic Pydantic model serialization/deserialization.
"""

import redis
import json
import logging
import asyncio
from typing import Callable, Dict, Any, Optional
from pydantic import BaseModel

from .schemas import (
    TradingSignal,
    RiskRequest,
    RiskResponse,
    Decision,
    Alert,
    AgentStatus
)

logger = logging.getLogger(__name__)


# Map channel names to Pydantic models for automatic deserialization
CHANNEL_MODELS = {
    "signals": TradingSignal,
    "risk:requests": RiskRequest,
    "risk:responses": RiskResponse,
    "decisions": Decision,
    "alerts": Alert,
    "status": AgentStatus,
}


class MessageBus:
    """
    Redis pub/sub message bus for agent communication.
    
    Handles publishing and subscribing to channels with automatic
    serialization/deserialization of Pydantic models.
    
    Example:
        >>> bus = MessageBus("redis://localhost:6379/0")
        >>> 
        >>> async def handle_signal(signal: TradingSignal):
        ...     print(f"Received signal for {signal.symbol}")
        >>> 
        >>> bus.subscribe("signals", handle_signal)
        >>> await bus.listen()  # Start listening loop
    """
    
    def __init__(self, redis_url: str):
        """
        Initialize message bus.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        
        logger.info(f"MessageBus initialized with Redis: {redis_url}")
    
    def subscribe(self, channel: str, handler: Callable):
        """
        Subscribe to a channel with a handler function.
        
        Args:
            channel: Channel name to subscribe to
            handler: Async function to call when message received.
                     Will be called with deserialized Pydantic model.
        
        Example:
            >>> async def my_handler(signal: TradingSignal):
            ...     print(signal.symbol)
            >>> bus.subscribe("signals", my_handler)
        """
        if channel in self._handlers:
            logger.warning(f"Overwriting existing handler for channel '{channel}'")
        
        self._handlers[channel] = handler
        self.pubsub.subscribe(channel)
        logger.info(f"Subscribed to channel: {channel}")
    
    def unsubscribe(self, channel: str):
        """
        Unsubscribe from a channel.
        
        Args:
            channel: Channel name to unsubscribe from
        """
        if channel in self._handlers:
            del self._handlers[channel]
            self.pubsub.unsubscribe(channel)
            logger.info(f"Unsubscribed from channel: {channel}")
    
    def publish(self, channel: str, message: BaseModel):
        """
        Publish a message to a channel.
        
        Args:
            channel: Channel name
            message: Pydantic model instance to publish
        
        Example:
            >>> signal = TradingSignal(
            ...     from_agent="technical",
            ...     symbol="AAPL",
            ...     direction="long",
            ...     confidence=0.75,
            ...     ...
            ... )
            >>> bus.publish("signals", signal)
        """
        try:
            # Serialize to JSON
            json_data = message.model_dump_json()
            
            # Publish to Redis
            subscribers = self.redis.publish(channel, json_data)
            
            logger.debug(
                f"Published to '{channel}': "
                f"{message.__class__.__name__} (subscribers: {subscribers})"
            )
        except Exception as e:
            logger.error(f"Error publishing to '{channel}': {e}", exc_info=True)
            raise
    
    async def listen(self):
        """
        Start listening for messages on subscribed channels.
        
        This is a blocking async method that continuously listens for messages
        and calls the appropriate handlers.
        
        Should be run in a background task:
            >>> asyncio.create_task(bus.listen())
        """
        self._running = True
        logger.info("MessageBus listening started")
        
        try:
            while self._running:
                # Check for messages (non-blocking with timeout)
                message = self.pubsub.get_message(timeout=0.1)
                
                if message and message['type'] == 'message':
                    await self._handle_message(message)
                
                # Yield control to event loop
                await asyncio.sleep(0.01)
        
        except Exception as e:
            logger.error(f"Error in listen loop: {e}", exc_info=True)
            raise
        finally:
            logger.info("MessageBus listening stopped")
    
    async def _handle_message(self, message: dict):
        """
        Handle incoming message from Redis.
        
        Args:
            message: Raw message dict from Redis pubsub
        """
        try:
            channel = message['channel']
            data = message['data']
            
            if channel not in self._handlers:
                logger.warning(f"No handler for channel '{channel}'")
                return
            
            # Deserialize JSON
            json_data = json.loads(data)
            
            # Get appropriate Pydantic model for this channel
            model_class = CHANNEL_MODELS.get(channel)
            
            if model_class:
                # Deserialize to Pydantic model
                model_instance = model_class(**json_data)
                
                # Call handler with model
                handler = self._handlers[channel]
                if asyncio.iscoroutinefunction(handler):
                    await handler(model_instance)
                else:
                    handler(model_instance)
            else:
                # No model defined, pass raw dict
                logger.warning(f"No Pydantic model for channel '{channel}', passing raw dict")
                handler = self._handlers[channel]
                if asyncio.iscoroutinefunction(handler):
                    await handler(json_data)
                else:
                    handler(json_data)
        
        except Exception as e:
            logger.error(
                f"Error handling message from '{message.get('channel')}': {e}",
                exc_info=True
            )
    
    def stop(self):
        """Stop the listening loop."""
        self._running = False
        logger.info("MessageBus stop requested")
    
    def close(self):
        """Close Redis connections."""
        self.stop()
        self.pubsub.close()
        self.redis.close()
        logger.info("MessageBus closed")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check health of message bus.
        
        Returns:
            Dict with health status
        """
        try:
            # Test Redis ping
            self.redis.ping()
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "subscribed_channels": list(self._handlers.keys()),
                "num_subscribers": len(self._handlers)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e)
            }
