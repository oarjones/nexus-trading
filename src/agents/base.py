"""
Base agent class for all autonomous agents.

Provides common infrastructure for agent lifecycle management,
error handling, health checks, and heartbeat monitoring.
"""

import asyncio
import logging
import redis
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .messaging import MessageBus


class BaseAgent(ABC):
    """
    Abstract base class for all trading agents.
    
    Provides:
    - Lifecycle management (start, stop, run loop)
    - Error handling with exponential backoff
    - Health checks
    - Redis-based heartbeat for monitoring
    - Structured logging
    """
    
    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        message_bus: MessageBus,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Initialize base agent.
        
        Args:
            name: Unique agent name
            config: Configuration dictionary
            message_bus: Shared MessageBus instance
            redis_client: Redis client for heartbeat (optional)
        """
        self.name = name
        self.config = config
        self.bus = message_bus
        self.redis = redis_client
        self.running = False
        self._last_activity: Optional[datetime] = None
        self._error_count = 0
        self._max_consecutive_errors = config.get("max_consecutive_errors", 5)
        self._heartbeat_ttl = config.get("heartbeat_ttl_seconds", 60)
        
        # Setup logging
        self.logger = logging.getLogger(f"agents.{name}")
        self.logger.setLevel(logging.INFO)
    
    @abstractmethod
    async def setup(self):
        """
        Initialize agent-specific resources.
        
        Called once before the agent starts running.
        Use this to subscribe to channels, connect to DBs, etc.
        """
        pass
    
    @abstractmethod
    async def process(self):
        """
        Main agent logic executed in a loop.
        
        This method is called repeatedly while the agent is running.
        Add sleep() calls to control loop frequency.
        """
        pass
    
    async def start(self):
        """Start the agent lifecycle."""
        self.logger.info(f"Starting agent '{self.name}'...")
        
        try:
            await self.setup()
            self.running = True
            self.logger.info(f"Agent '{self.name}' started successfully")
            
            # Start main loop
            asyncio.create_task(self._run_loop())
            
        except Exception as e:
            self.logger.error(f"Failed to start agent '{self.name}': {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop the agent gracefully."""
        self.logger.info(f"Stopping agent '{self.name}'...")
        self.running = False
        
        # Remove heartbeat
        if self.redis:
            try:
                self.redis.delete(f"agent:heartbeat:{self.name}")
            except Exception as e:
                self.logger.warning(f"Could not remove heartbeat: {e}")
    
    def health(self) -> Dict[str, Any]:
        """
        Get agent health status.
        
        Returns:
            Dictionary with status, last_activity, name
        """
        return {
            "status": "healthy" if self.running else "stopped",
            "last_activity": self._last_activity.isoformat() if self._last_activity else None,
            "name": self.name,
            "error_count": self._error_count
        }
    
    def _publish_heartbeat(self):
        """
        Publish heartbeat to Redis.
        
        Sets a key with TTL so monitoring can detect dead agents.
        Key expires after heartbeat_ttl seconds if not refreshed.
        """
        if not self.redis:
            return
        
        try:
            heartbeat_key = f"agent:heartbeat:{self.name}"
            heartbeat_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "running" if self.running else "stopped",
                "error_count": self._error_count
            }
            
            # Use SETEX to set key with TTL in one atomic operation
            self.redis.setex(
                heartbeat_key,
                self._heartbeat_ttl,
                str(heartbeat_data)  # Redis stores as string
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to publish heartbeat: {e}")
    
    async def _run_loop(self):
        """
        Internal main loop with error handling.
        
        Continuously calls process() while running=True.
        Implements exponential backoff on errors.
        """
        self.logger.info(f"Agent '{self.name}' entering main loop")
        
        while self.running:
            try:
                # Execute agent logic
                await self.process()
                
                # Update activity timestamp
                self._last_activity = datetime.now(timezone.utc)
                
                # Reset error count on success
                self._error_count = 0
                
                # Publish heartbeat
                self._publish_heartbeat()
            
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                self.logger.info(f"Agent '{self.name}' process loop cancelled")
                break
            
            except Exception as e:
                self._error_count += 1
                self.logger.error(
                    f"Error in agent '{self.name}' process loop "
                    f"(error {self._error_count}/{self._max_consecutive_errors}): {e}",
                    exc_info=True
                )
                
                # If too many consecutive errors, stop agent
                if self._error_count >= self._max_consecutive_errors:
                    self.logger.critical(
                        f"Agent '{self.name}' exceeded max consecutive errors, stopping"
                    )
                    self.running = False
                    break
                
                # Backoff before retry (exponential with max 60s)
                backoff_seconds = min(2 ** self._error_count, 60)
                self.logger.info(f"Backing off for {backoff_seconds}s before retry")
                await asyncio.sleep(backoff_seconds)
            
            # Small yield to event loop
            await asyncio.sleep(0.1)
        
        self.logger.info(f"Agent '{self.name}' process loop exited")
    
    def __repr__(self) -> str:
        """String representation of agent."""
        return f"{self.__class__.__name__}(name='{self.name}', running={self.running})"
