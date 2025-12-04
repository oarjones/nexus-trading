"""
Agent verification script.

Verifies that all components of the Phase 3 agent system are working correctly.
Should be run after starting agents with start_agents.py.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
import redis
import httpx

from agents import (
    MessageBus,
    TradingSignal,
    Direction,
    MCPServers
)

# Load environment
load_dotenv()


class VerificationSuite:
    """Phase 3 verification test suite."""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/trading")
        self.mcp_servers = MCPServers.from_env()
        self.results = []
    
    def log_result(self, name: str, success: bool, message: str = ""):
        """Log a verification result."""
        status = "✅" if success else "❌"
        self.results.append((name, success, message))
        print(f"{status} {name}: {message}")
    
    async def check_redis(self) -> bool:
        """Verify Redis connection."""
        try:
            client = redis.from_url(self.redis_url, decode_responses=True)
            client.ping()
            self.log_result("Redis connection", True, f"Connected to {self.redis_url}")
            client.close()
            return True
        except Exception as e:
            self.log_result("Redis connection", False, str(e))
            return False
   
    async def check_postgresql(self) -> bool:
        """Verify PostgreSQL connection."""
        try:
            # Try to import psycopg2 and connect
            import psycopg2
            from urllib.parse import urlparse
            
            parsed = urlparse(self.db_url)
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path[1:]  # Remove leading /
            )
            conn.close()
            self.log_result("PostgreSQL connection", True, "Database accessible")
            return True
        except Exception as e:
            self.log_result("PostgreSQL connection", False, str(e))
            return False
    
    async def check_mcp_server(self, name: str, url: str) -> bool:
        """Verify an MCP server is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    self.log_result(f"MCP {name} health", True, f"{url}")
                    return True
                else:
                    self.log_result(
                        f"MCP {name} health",
                        False,
                        f"HTTP {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.log_result(f"MCP {name} health", False, str(e))
            return False
    
    async def check_agent_health(self, agent_name: str) -> bool:
        """
        Check if an agent is healthy via Redis heartbeat.
        
        Agents publish heartbeats to Redis with TTL. If the key exists,
        the agent is considered healthy.
        """
        try:
            client = redis.from_url(self.redis_url, decode_responses=True)
            
            # Check heartbeat key with lowercase agent name (as used in BaseAgent)
            # Convert display name to agent name format
            agent_key_map = {
                "Risk Manager": "risk_manager",
                "Technical Analyst": "technical_analyst",
                "Orchestrator": "orchestrator"
            }
            
            agent_key_name = agent_key_map.get(agent_name, agent_name.lower().replace(" ", "_"))
            heartbeat_key = f"agent:heartbeat:{agent_key_name}"
            
            # Check if heartbeat exists
            heartbeat_data = client.get(heartbeat_key)
            
            if heartbeat_data:
                # Get TTL to show how recently it was updated
                ttl = client.ttl(heartbeat_key)
                self.log_result(
                    f"{agent_name} health",
                    True,
                    f"Heartbeat active (TTL: {ttl}s)"
                )
                client.close()
                return True
            else:
                self.log_result(
                    f"{agent_name} health",
                    False,
                    "No heartbeat found (agent not running or heartbeat expired)"
                )
                client.close()
                return False
                
        except Exception as e:
            self.log_result(f"{agent_name} health", False, str(e))
            return False
    
    async def check_pubsub(self) -> bool:
        """Verify pub/sub messaging works."""
        try:
            bus = MessageBus(self.redis_url)
            
            # Create a test message handler
            received = []
            
            def handler(msg):
                received.append(msg)
            
            # Subscribe to test channel
            bus.subscribe("test_channel", handler)
            
            # Start listening in background
            listen_task = asyncio.create_task(bus.listen())
            
            # Give it time to subscribe
            await asyncio.sleep(0.5)
            
            # Publish test message
            test_signal = TradingSignal(
                from_agent="test",
                symbol="TEST",
                direction=Direction.LONG,
                confidence=0.75,
                entry_price=100.0,
                stop_loss=95.0,
                take_profit=110.0,
                timeframe="1d",
                reasoning="Test signal",
                indicators={}
            )
            
            bus.publish("test_channel", test_signal)
            
            # Wait for message
            await asyncio.sleep(1.0)
            
            # Stop listening
            bus.stop()
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
            
            bus.close()
            
            if len(received) > 0:
                self.log_result("Pub/Sub messaging", True, "Test message delivered")
                return True
            else:
                self.log_result("Pub/Sub messaging", False, "Test message not received")
                return False
        
        except Exception as e:
            self.log_result("Pub/Sub messaging", False, str(e))
            return False
    
    async def check_signal_flow(self) -> bool:
        """
        Verify end-to-end signal → decision flow.
        
        Publishes a test signal and waits for a decision.
        Note: This requires agents to be running!
        """
        try:
            bus = MessageBus(self.redis_url)
            
            # Listen for decisions
            decisions = []
            
            def decision_handler(decision):
                decisions.append(decision)
            
            bus.subscribe("decisions", decision_handler)
            
            # Start listening
            listen_task = asyncio.create_task(bus.listen())
            await asyncio.sleep(0.5)
            
            # Publish test signal
            test_signal = TradingSignal(
                from_agent="technical_analyst",
                symbol="SAN.MC",
                direction=Direction.LONG,
                confidence=0.70,  # Above threshold
                entry_price=4.50,
                stop_loss=4.30,
                take_profit=5.00,
                timeframe="1d",
                reasoning="Verification test signal",
                indicators={"RSI": 28, "MACD_hist": 0.05}
            )
            
            bus.publish("signals", test_signal)
            
            # Wait for decision (with timeout)
            timeout = 5.0
            start = time.time()
            
            while time.time() - start < timeout:
                if len(decisions) > 0:
                    break
                await asyncio.sleep(0.5)
            
            # Stop listening
            bus.stop()
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
            
            bus.close()
            
            if len(decisions) > 0:
                decision = decisions[0]
                self.log_result(
                    "Signal → Decision flow",
                    True,
                    f"Decision received: {decision.action}"
                )
                return True
            else:
                self.log_result(
                    "Signal → Decision flow",
                    False,
                    "No decision received (agents running?)"
                )
                return False
        
        except Exception as e:
            self.log_result("Signal → Decision flow", False, str(e))
            return False
    
    async def run_all_checks(self):
        """Run all verification checks."""
        print("=" * 70)
        print("NEXUS TRADING - PHASE 3 VERIFICATION")
        print("=" * 70)
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print()
        
        # Infrastructure checks
        print("📡 Infrastructure Checks")
        print("-" * 70)
        await self.check_redis()
        await self.check_postgresql()
        print()
        
        # MCP Server checks
        print("🔧 MCP Server Checks")
        print("-" * 70)
        await self.check_mcp_server("market-data", self.mcp_servers.market_data)
        await self.check_mcp_server("technical", self.mcp_servers.technical)
        await self.check_mcp_server("risk", self.mcp_servers.risk)
        print()
        
        # Agent checks
        print("🤖 Agent Health Checks")
        print("-" * 70)
        await self.check_agent_health("Risk Manager")
        await self.check_agent_health("Technical Analyst")
        await self.check_agent_health("Orchestrator")
        print()
        
        # Messaging checks
        print("📨 Messaging Checks")
        print("-" * 70)
        await self.check_pubsub()
        print()
        
        # End-to-end checks
        print("🔄 End-to-End Flow Checks")
        print("-" * 70)
        print("⚠️  This check requires agents to be running!")
        await self.check_signal_flow()
        print()
        
        # Summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        
        total = len(self.results)
        passed = sum(1 for _, success, _ in self.results if success)
        failed = total - passed
        
        print(f"Total checks: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print()
        
        if failed == 0:
            print("🎉 ALL CHECKS PASSED - PHASE 3 VERIFIED!")
            return 0
        else:
            print("⚠️  SOME CHECKS FAILED - REVIEW LOGS ABOVE")
            print()
            print("Failed checks:")
            for name, success, message in self.results:
                if not success:
                    print(f"  - {name}: {message}")
            return 1


async def main():
    """Main entry point."""
    suite = VerificationSuite()
    exit_code = await suite.run_all_checks()
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
