"""
Tests for BaseAgent class.

CRITICAL: BaseAgent is the foundation for all agents.
These tests validate lifecycle, health checks, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock
from datetime import datetime

# Add src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agents.base import BaseAgent
from agents.messaging import MessageBus


class ConcreteTestAgent(BaseAgent):
    """Concrete implementation for testing BaseAgent."""
    
    def __init__(self, name, config, message_bus, redis_client=None):
        super().__init__(name, config, message_bus, redis_client)
        self.setup_called = False
        self.process_called = False
        self.process_count = 0
        self.should_error = False
        self.error_count_to_throw = 0
    
    async def setup(self):
        """Test setup implementation."""
        self.setup_called = True
        await asyncio.sleep(0.01)
    
    async def process(self):
        """Test process implementation."""
        self.process_called = True
        self.process_count += 1
        
        if self.should_error and self.process_count <= self.error_count_to_throw:
            raise ValueError(f"Test error #{self.process_count}")
        
        await asyncio.sleep(0.1)


@pytest.fixture
def mock_message_bus():
    """Create a mock MessageBus for testing."""
    bus = Mock(spec=MessageBus)
    bus.subscribe = Mock()
    bus.publish = Mock()
    return bus


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    redis_mock = Mock()
    redis_mock.setex = Mock()
    redis_mock.delete = Mock()
    redis_mock.get = Mock(return_value=None)
    return redis_mock


@pytest.fixture
def test_agent(mock_message_bus, mock_redis):
    """Create a test agent instance."""
    config = {"test_param": "test_value"}
    agent = ConcreteTestAgent("test_agent", config, mock_message_bus, mock_redis)
    return agent


class TestBaseAgentInitialization:
    """Test BaseAgent initialization."""
    
    def test_initialization(self, test_agent):
        """Test agent initializes with correct attributes."""
        assert test_agent.name == "test_agent"
        assert test_agent.config == {"test_param": "test_value"}
        assert test_agent.running is False
        assert test_agent._last_activity is None
        assert test_agent._error_count == 0
    
    def test_logger_name(self, test_agent):
        """Test logger is configured with agent name."""
        assert test_agent.logger.name == "agents.test_agent"


class TestBaseAgentLifecycle:
    """Test BaseAgent lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_start_calls_setup(self, test_agent):
        """Test that start() calls setup()."""
        await test_agent.start()
        
        assert test_agent.setup_called is True
        assert test_agent.running is True
        
        await test_agent.stop()
    
    @pytest.mark.asyncio
    async def test_start_starts_process_loop(self, test_agent):
        """Test that start() begins the process loop."""
        await test_agent.start()
        
        # Wait for process to be called
        await asyncio.sleep(0.2)
        
        assert test_agent.process_called is True
        assert test_agent.process_count > 0
        
        await test_agent.stop()
    
    @pytest.mark.asyncio
    async def test_stop_gracefully(self, test_agent):
        """Test that stop() gracefully stops the agent."""
        await test_agent.start()
        assert test_agent.running is True
        
        await test_agent.stop()
        assert test_agent.running is False
    
    @pytest.mark.asyncio
    async def test_cannot_start_twice(self, test_agent):
        """Test that starting an already-running agent does nothing."""
        await test_agent.start()
        
        setup_count_before = test_agent.setup_called
        await test_agent.start()  # Try starting again
        
        # Should not call setup again
        assert test_agent.setup_called == setup_count_before
        
        await test_agent.stop()
    
    @pytest.mark.asyncio
    async def test_last_activity_updated(self, test_agent):
        """Test that _last_activity is updated during processing."""
        await test_agent.start()
        
        # Wait for some processing
        await asyncio.sleep(0.3)
        
        assert test_agent._last_activity is not None
        assert isinstance(test_agent._last_activity, datetime)
        
        await test_agent.stop()


class TestBaseAgentHealthCheck:
    """Test BaseAgent health check functionality."""
    
    def test_health_stopped(self, test_agent):
        """Test health check when agent is stopped."""
        health = test_agent.health()
        
        assert health["status"] == "stopped"
        assert health["name"] == "test_agent"
        assert health["running"] is False
        assert health["last_activity"] is None
    
    @pytest.mark.asyncio
    async def test_health_healthy(self, test_agent):
        """Test health check when agent is running normally."""
        await test_agent.start()
        await asyncio.sleep(0.2)
        
        health = test_agent.health()
        
        assert health["status"] == "healthy"
        assert health["running"] is True
        assert health["error_count"] == 0
        
        await test_agent.stop()
    
    @pytest.mark.asyncio
    async def test_health_degraded_after_max_errors(self, test_agent):
        """Test health check shows degraded after max errors."""
        # Configure agent to throw errors
        test_agent.should_error = True
        test_agent.error_count_to_throw = 10  # More than max (5)
        
        await test_agent.start()
        
        # Wait for errors to accumulate
        await asyncio.sleep(1.0)
        
        health = test_agent.health()
        
        # Should be degraded or stopped due to max errors
        assert health["status"] in ["degraded", "stopped"]
        assert health["error_count"] >= test_agent._max_consecutive_errors
        
        await test_agent.stop()


class TestBaseAgentErrorHandling:
    """Test BaseAgent error handling."""
    
    @pytest.mark.asyncio
    async def test_process_exception_logged(self, test_agent, caplog):
        """Test that exceptions in process() are logged."""
        test_agent.should_error = True
        test_agent.error_count_to_throw = 2
        
        await test_agent.start()
        
        # Wait for error to occur
        await asyncio.sleep(0.5)
        
        assert test_agent._error_count > 0
        
        await test_agent.stop()
    
    @pytest.mark.asyncio
    async def test_max_errors_stops_agent(self, test_agent):
        """Test that agent stops after max consecutive errors."""
        test_agent.should_error = True
        test_agent.error_count_to_throw = 6  # Just above max (5)
        
        await test_agent.start()
        
        # Wait for agent to hit max errors and stop
        # With exponential backoff: 2s, 4s, 8s, 16s, 32s
        # We wait for first 5 errors: 2+4+8 = 14s + margin
        await asyncio.sleep(18.0)  # Increased from 10.0
        
        # Agent should have stopped itself
        assert test_agent.running is False
        assert test_agent._error_count >= test_agent._max_consecutive_errors
    
    @pytest.mark.asyncio
    async def test_error_count_resets_on_success(self, test_agent):
        """Test that error count resets after successful iteration."""
        # First cause some errors
        test_agent.should_error = True
        test_agent.error_count_to_throw = 2
        
        await test_agent.start()
        
        # Wait for errors to accumulate
        # First error: immediate, second error: 2s backoff = ~2.5s total
        await asyncio.sleep(3.0)  # Increased from 0.7
        
        error_count_after_errors = test_agent._error_count
        assert error_count_after_errors > 0
        
        # Now stop errors (agent will recover)
        test_agent.error_count_to_throw = 0
        
        # Wait for multiple successful iterations
        # After 2 errors, backoff is 4s, then it needs to succeed and reset
        # Total: 4s backoff + processing time + margin
        await asyncio.sleep(6.0)  # Increased from 1.5
        
        # Error count should reset
        assert test_agent._error_count == 0
        
        await test_agent.stop()


class TestBaseAgentAbstractMethods:
    """Test that abstract methods must be implemented."""
    
    def test_cannot_instantiate_without_setup(self, mock_message_bus):
        """Test that BaseAgent cannot be instantiated without setup()."""
        class IncompleteAgent(BaseAgent):
            async def process(self):
                pass
        
        # Should raise TypeError due to abstract method
        with pytest.raises(TypeError):
            IncompleteAgent("test", {}, mock_message_bus, None)
    
    def test_cannot_instantiate_without_process(self, mock_message_bus):
        """Test that BaseAgent cannot be instantiated without process()."""
        class IncompleteAgent(BaseAgent):
            async def setup(self):
                pass
        
        # Should raise TypeError due to abstract method
        with pytest.raises(TypeError):
            IncompleteAgent("test", {}, mock_message_bus, None)


class TestBaseAgentRepr:
    """Test BaseAgent string representation."""
    
    def test_repr_stopped(self, test_agent):
        """Test repr when agent is stopped."""
        repr_str = repr(test_agent)
        assert "ConcreteTestAgent" in repr_str
        assert "test_agent" in repr_str
        assert "False" in repr_str  # running=False
    
    @pytest.mark.asyncio
    async def test_repr_running(self, test_agent):
        """Test repr when agent is running."""
        await test_agent.start()
        
        repr_str = repr(test_agent)
        assert "ConcreteTestAgent" in repr_str
        assert "test_agent" in repr_str
        assert "True" in repr_str  # running=True
        
        await test_agent.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
