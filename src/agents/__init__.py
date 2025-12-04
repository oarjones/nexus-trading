"""
Autonomous trading agents.

This package contains the autonomous agent system for the trading bot:
- BaseAgent: Abstract base class for all agents
- MessageBus: Redis pub/sub messaging system
- Schemas: Pydantic models for messages
- Specialized agents: Technical Analyst, Risk Manager, Orchestrator
"""

__version__ = "0.1.0"

from .base import BaseAgent
from .messaging import MessageBus
from .schemas import (
    TradingSignal,
    RiskRequest,
    RiskResponse,
    Decision,
    Alert,
    AgentStatus,
    Direction,
    MessageType,
)
from .config import load_config, get_agent_config
from .mcp_client import MCPClient, MCPServers

# Specialized agents
from .technical import TechnicalAnalystAgent
from .risk_manager import RiskManagerAgent
from .orchestrator import OrchestratorAgent

__all__ = [
    # Base classes
    "BaseAgent",
    "MessageBus",
    
    # Schemas
    "TradingSignal",
    "RiskRequest",
    "RiskResponse",
    "Decision",
    "Alert",
    "AgentStatus",
    "Direction",
    "MessageType",
    
    # Config
    "load_config",
    "get_agent_config",
    
    # MCP Client
    "MCPClient",
    "MCPServers",
    
    # Specialized Agents
    "TechnicalAnalystAgent",
    "RiskManagerAgent",
    "OrchestratorAgent",
]
