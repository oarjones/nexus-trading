"""
Tests for Redis MessageBus.

CRITICAL: These tests validate the core messaging infrastructure
that all agents depend on for communication.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, patch
import redis

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agents.messaging import MessageBus, CHANNEL_MODELS
from agents.schemas import (
    TradingSignal,
    RiskRequest,
    RiskResponse,
    Decision,
    Direction
)


@pytest.fixture
def redis_url():
    """Redis URL for testing."""
    return "redis://localhost:6379/0"


class MockPubSub:
    def __init__(self, channels, messages):
        self.channels = channels
        self.messages = messages  # Shared list of (channel, message)
        self.subscribed = set()

    def subscribe(self, channel):
        self.subscribed.add(channel)

    def unsubscribe(self, channel):
        if channel in self.subscribed:
            self.subscribed.remove(channel)

    def get_message(self, timeout=0.1):
        # Check shared messages
        if not self.messages:
            return None
            
        # Get first message
        channel, data = self.messages[0]
        
        # If subscribed to this channel
        if channel in self.subscribed:
            self.messages.pop(0)  # Remove it
            return {
                'type': 'message',
                'channel': channel,
                'data': data
            }
        
        # If not subscribed but message exists, maybe another pubsub handles it?
        # For simplicity in tests, we assume single consumer or we handle it in MockRedis
        return None

    def close(self):
        pass

class MockRedis:
    def __init__(self):
        self.messages = []  # List of (channel, data) shared among pubsubs? 
        # Actually each pubsub should receive messages.
        # Simple approach: Global list of messages, and pubsub reads if subscribed.
        # But restart/listen might miss previous messages. 
        # Redis PubSub is fire and forget.
        
        # Better: MockRedis keeps list of PubSubs.
        self.pubsubs = []

    def pubsub(self):
        ps = MockPubSubImpl(self)
        self.pubsubs.append(ps)
        return ps

    def publish(self, channel, data):
        count = 0
        for ps in self.pubsubs:
            if channel in ps.subscribed:
                ps.queue.append({'type': 'message', 'channel': channel, 'data': data})
                count += 1
        return count

    def ping(self):
        return True

    def close(self):
        pass

class MockPubSubImpl:
    def __init__(self, redis_client):
        self.client = redis_client
        self.subscribed = set()
        self.queue = []

    def subscribe(self, channel):
        self.subscribed.add(channel)

    def unsubscribe(self, channel):
        if channel in self.subscribed:
            self.subscribed.remove(channel)

    def get_message(self, timeout=0.1):
        if self.queue:
            return self.queue.pop(0)
        time.sleep(timeout if timeout > 0 else 0) # Simulate wait
        return None
    
    def close(self):
        if self in self.client.pubsubs:
            self.client.pubsubs.remove(self)


@pytest.fixture
def mock_redis_client():
    return MockRedis()

@pytest.fixture
def message_bus(redis_url, mock_redis_client):
    """Create a MessageBus instance for testing with mocked Redis."""
    with patch('redis.from_url', return_value=mock_redis_client):
        bus = MessageBus(redis_url)
        yield bus
        bus.close()


class TestMessageBusBasics:
    """Test basic MessageBus functionality."""
    
    def test_initialization(self, redis_url):
        """Test MessageBus can be initialized."""
        with patch('redis.from_url') as mock_redis:
            bus = MessageBus(redis_url)
            assert bus.redis_url == redis_url
            assert bus._handlers == {}
            assert bus._running is False
            bus.close()
    
    def test_subscribe(self, message_bus):
        """Test subscribing to a channel."""
        def handler(msg):
            pass
        
        message_bus.subscribe("test_channel", handler)
        assert "test_channel" in message_bus._handlers
        assert message_bus._handlers["test_channel"] == handler
    
    def test_unsubscribe(self, message_bus):
        """Test unsubscribing from a channel."""
        def handler(msg):
            pass
        
        message_bus.subscribe("test_channel", handler)
        message_bus.unsubscribe("test_channel")
        assert "test_channel" not in message_bus._handlers
    
    def test_health_check_healthy(self, message_bus):
        """Test health check when Redis is accessible."""
        health = message_bus.health_check()
        assert health["status"] == "healthy"
        assert health["redis_connected"] is True


class TestMessageSerialization:
    """Test message serialization and deserialization."""
    
    def test_publish_trading_signal(self, message_bus):
        """Test publishing a TradingSignal."""
        signal = TradingSignal(
            from_agent="technical",
            symbol="TEST",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        # Should not raise exception
        message_bus.publish("signals", signal)
    
    def test_publish_risk_request(self, message_bus):
        """Test publishing a RiskRequest."""
        signal = TradingSignal(
            from_agent="technical",
            symbol="TEST",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        request = RiskRequest(
            signal=signal,
            capital=100000.0,
            current_positions=[]
        )
        
        # Should not raise exception
        message_bus.publish("risk:requests", request)


class TestMessagePubSub:
    """Test end-to-end pub/sub functionality."""
    
    @pytest.mark.asyncio
    async def test_publish_and_receive(self, redis_url, mock_redis_client):
        """Test publishing and receiving a message."""
        with patch('redis.from_url', return_value=mock_redis_client):
            bus = MessageBus(redis_url)
        
        received_messages = []
        
        def handler(msg):
            received_messages.append(msg)
        
        # Subscribe to 'signals' channel (which is in CHANNEL_MODELS)
        bus.subscribe("signals", handler)
        
        # Start listening in background
        listen_task = asyncio.create_task(bus.listen())
        
        # Give Redis time to establish subscription
        await asyncio.sleep(0.5)
        
        # Publish a message
        signal = TradingSignal(
            from_agent="test",
            symbol="TEST",
            direction=Direction.LONG,
            confidence=0.75,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe="1d",
            reasoning="test message",
            indicators={}
        )
        
        bus.publish("signals", signal)
        
        # Wait for message to be processed
        await asyncio.sleep(1.0)
        
        # Stop listening
        bus.stop()
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        bus.close()
        
        # Verify message was received
        assert len(received_messages) == 1
        received = received_messages[0]
        assert isinstance(received, TradingSignal)
        assert received.symbol == "TEST"
        assert received.reasoning == "test message"
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, redis_url, mock_redis_client):
        """Test multiple subscribers on same channel."""
        with patch('redis.from_url', return_value=mock_redis_client):
            bus1 = MessageBus(redis_url)
            bus2 = MessageBus(redis_url)
        
        received1 = []
        received2 = []
        
        bus1.subscribe("signals", lambda msg: received1.append(msg))
        bus2.subscribe("signals", lambda msg: received2.append(msg))
        
        # Start both listeners
        task1 = asyncio.create_task(bus1.listen())
        task2 = asyncio.create_task(bus2.listen())
        
        await asyncio.sleep(0.5)
        
        # Publish message
        signal = TradingSignal(
            from_agent="test",
            symbol="MULTI",
            direction=Direction.SHORT,
            confidence=0.80,
            entry_price=50.0,
            stop_loss=55.0,
            take_profit=40.0,
            timeframe="1h",
            reasoning="multi-subscriber test",
            indicators={}
        )
        
        bus1.publish("signals", signal)
        
        await asyncio.sleep(1.0)
        
        # Clean up
        bus1.stop()
        bus2.stop()
        task1.cancel()
        task2.cancel()
        
        try:
            await task1
            await task2
        except asyncio.CancelledError:
            pass
        
        bus1.close()
        bus2.close()
        
        # Both should have received the message
        assert len(received1) == 1
        assert len(received2) == 1
        assert received1[0].symbol == "MULTI"
        assert received2[0].symbol == "MULTI"
    
    @pytest.mark.asyncio
    async def test_channel_isolation(self, redis_url, mock_redis_client):
        """Test that messages only go to subscribed channels."""
        with patch('redis.from_url', return_value=mock_redis_client):
            bus = MessageBus(redis_url)
        
        signals_messages = []
        decisions_messages = []
        
        bus.subscribe("signals", lambda msg: signals_messages.append(msg))
        bus.subscribe("decisions", lambda msg: decisions_messages.append(msg))
        
        listen_task = asyncio.create_task(bus.listen())
        await asyncio.sleep(0.5)
        
        # Publish to signals channel
        signal = TradingSignal(
            from_agent="test",
            symbol="SIGNAL_TEST",
            direction=Direction.LONG,
            confidence=0.70,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe="1d",
            reasoning="signals channel  test",
            indicators={}
        )
        bus.publish("signals", signal)
        
        await asyncio.sleep(0.5)
        
        # Publish to decisions channel
        decision = Decision(
            signal=signal,
            score=0.75,
            action="execute",
            size=100,
            adjustments=[],
            warnings=[],
            reasoning="decisions channel test"
        )
        bus.publish("decisions", decision)
        
        await asyncio.sleep(0.5)
        
        bus.stop()
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        bus.close()
        
        # Verify isolation
        assert len(signals_messages) == 1
        assert len(decisions_messages) == 1
        assert signals_messages[0].symbol == "SIGNAL_TEST"
        assert decisions_messages[0].action == "execute"


class TestChannelModels:
    """Test CHANNEL_MODELS mapping."""
    
    def test_channel_models_defined(self):
        """Test that all expected channels have model mappings."""
        expected_channels = [
            "signals",
            "risk:requests",
            "risk:responses",
            "decisions",
            "alerts",
            "status"
        ]
        
        for channel in expected_channels:
            assert channel in CHANNEL_MODELS, f"Channel '{channel}' not in CHANNEL_MODELS"
    
    def test_signals_channel_maps_to_trading_signal(self):
        """Test signals channel maps to TradingSignal."""
        assert CHANNEL_MODELS["signals"] == TradingSignal
    
    def test_risk_requests_channel_maps_correctly(self):
        """Test risk:requests channel maps to RiskRequest."""
        assert CHANNEL_MODELS["risk:requests"] == RiskRequest
    
    def test_risk_responses_channel_maps_correctly(self):
        """Test risk:responses channel maps to RiskResponse."""
        assert CHANNEL_MODELS["risk:responses"] == RiskResponse


class TestErrorHandling:
    """Test error handling in MessageBus."""
    
    def test_publish_with_invalid_redis(self):
        """Test publishing when Redis fails."""
        mock_redis = Mock()
        mock_redis.publish.side_effect = Exception("Connection error")
        
        with patch('redis.from_url', return_value=mock_redis):
            bus = MessageBus("redis://invalid:9999/0")
            
            signal = TradingSignal(
                from_agent="test",
                symbol="TEST",
                direction=Direction.LONG,
                confidence=0.75,
                entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            timeframe="1d",
            reasoning="test",
            indicators={}
        )
        
        # Should raise exception
        with pytest.raises(Exception):
            bus.publish("signals", signal)
    
    @pytest.mark.asyncio
    async def test_handler_exception_doesnt_crash_bus(self, redis_url, mock_redis_client):
        """Test that exception in handler doesn't crash the bus."""
        with patch('redis.from_url', return_value=mock_redis_client):
            bus = MessageBus(redis_url)
        
        received_count = [0]
        
        def faulty_handler(msg):
            received_count[0] += 1
            if received_count[0] == 1:
                # First message causes exception
                raise ValueError("Handler error!")
            # Second message should still be processed
        
        bus.subscribe("test_channel", faulty_handler)
        listen_task = asyncio.create_task(bus.listen())
        
        await asyncio.sleep(0.5)
        
        # Send two messages
        signal1 = TradingSignal(
            from_agent="test", symbol="MSG1", direction=Direction.LONG,
            confidence=0.75, entry_price=100.0, stop_loss=95.0,
            take_profit=110.0, timeframe="1d", reasoning="first", indicators={}
        )
        signal2 = TradingSignal(
            from_agent="test", symbol="MSG2", direction=Direction.LONG,
            confidence=0.75, entry_price=100.0, stop_loss=95.0,
            take_profit=110.0, timeframe="1d", reasoning="second", indicators={}
        )
        
        bus.publish("test_channel", signal1)
        await asyncio.sleep(0.5)
        bus.publish("test_channel", signal2)
        await asyncio.sleep(0.5)
        
        bus.stop()
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        
        bus.close()
        
        # Both messages should have been received (handler called twice)
        assert received_count[0] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
