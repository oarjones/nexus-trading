"""
Base agent class for all autonomous agents.

Provides common infrastructure for agent lifecycle management,
health checks, and message bus integration.
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any

from .messaging import MessageBus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Provides:
    - Lifecycle management (start/stop)
    - Health checks
    - Message bus integration
    - Exception handling and logging
    
    Subclasses must implement:
    - async setup(): Initialize agent-specific resources
    - async process(): Main agent loop logic
    
    Example:
        >>> class MyAgent(BaseAgent):
        ...     async def setup(self):
        ...         self.bus.subscribe("my_channel", self.handle_message)
        ...     
        ...     async def process(self):
        ...         # Do work
        ...         await asyncio.sleep(10)
        ...     
        ...     async def handle_message(self, msg):
        ...         print(f"Got message: {msg}")
    """
    
    def __init__(self, name: str, config: Dict[str, Any], message_bus: MessageBus):
        """
        Initialize base agent.
        
        Args:
            name: Agent name (unique identifier)
            config: Configuration dictionary
            message_bus: Shared MessageBus instance
        """
        self.name = name
        self.config = config
        self.bus = message_bus
        self.running = False
        self._last_activity: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._error_count = 0
        self._max_consecutive_errors = 5
        
        # Configure logger for this agent
        self.logger = logging.getLogger(f"agents.{name}")
        self.logger.info(f"Agent '{name}' initialized")
    
    @abstractmethod
    async def setup(self):
        """
        Initialize agent-specific resources.
        
        Called once when agent starts, before the main process loop.
        Use for:
        - Subscribing to message channels
        - Initializing connections
        - Loading state from database/Redis
        
        Must be implemented by subclass.
        """
        pass
    
    @abstractmethod
    async def process(self):
        """
        Main agent logic loop.
        
        Called repeatedly while agent is running.
        This method should:
        - Perform agent-specific work
        - Use await asyncio.sleep() to yield control
        - NOT run an infinite loop (that's handled by _run_loop)
        
        Must be implemented by subclass.
        """
        pass
    
    async def start(self):
        """
        Start the agent.
        
        Calls setup() then starts the main process loop in background.
        """
        if self.running:
            self.logger.warning(f"Agent '{self.name}' is already running")
            return
        
        self.logger.info(f"Starting agent '{self.name}'...")
        
        try:
            # Run setup
            await self.setup()
            
            # Mark as running
            self.running = True
            
            # Start process loop in background
            self._task = asyncio.create_task(self._run_loop())
            
            self.logger.info(f"Agent '{self.name}' started successfully")
        
        except Exception as e:
            self.logger.error(f"Failed to start agent '{self.name}': {e}", exc_info=True)
            self.running = False
            raise
    
    async def stop(self):
        """
        Stop the agent gracefully.
        
        Waits for current process iteration to complete.
        """
        if not self.running:
            self.logger.warning(f"Agent '{self.name}' is not running")
            return
        
        self.logger.info(f"Stopping agent '{self.name}'...")
        
        self.running = False
        
        # Wait for task to complete
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=30.0)
            except asyncio.TimeoutError:
                self.logger.warning(f"Agent '{self.name}' stop timed out, cancelling task")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        
        self.logger.info(f"Agent '{self.name}' stopped")
    
    def health(self) -> Dict[str, Any]:
        """
        Get agent health status.
        
        Returns:
            Dict with health information:
            - status: "healthy", "degraded", or "stopped"
            - name: Agent name
            - running: Whether agent is running
            - last_activity: Timestamp of last activity
            - error_count: Number of consecutive errors
        """
        # Determine status
        if not self.running:
            status = "stopped"
        elif self._error_count >= self._max_consecutive_errors:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "name": self.name,
            "running": self.running,
            "last_activity": self._last_activity.isoformat() if self._last_activity else None,
            "error_count": self._error_count
        }
    
    async def _run_loop(self):
        """
        Internal main loop.
        
        Continuously calls process() while running, with exception handling.
        """
        self.logger.info(f"Agent '{self.name}' process loop started")
        
        while self.running:
            try:
                # Call agent-specific process method
                await self.process()
                
                # Update activity timestamp
                self._last_activity = datetime.utcnow()
                
                # Reset error count on successful iteration
                if self._error_count > 0:
                    self.logger.info(f"Agent '{self.name}' recovered from errors")
                    self._error_count = 0
            
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
                
                # Backoff before retry
                await asyncio.sleep(min(2 ** self._error_count, 60))
            
            # Small yield to event loop
            await asyncio.sleep(0.1)
        
        self.logger.info(f"Agent '{self.name}' process loop exited")
    
    def __repr__(self) -> str:
        """String representation of agent."""
        return f"{self.__class__.__name__}(name='{self.name}', running={self.running})"
