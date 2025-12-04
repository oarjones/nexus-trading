"""
Orchestrator Agent.

Central coordinator that receives signals from analysts, validates with
Risk Manager, and emits final trading decisions.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from .base import BaseAgent
from .messaging import MessageBus
from .schemas import TradingSignal, RiskRequest, RiskResponse, Decision
import redis

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Central decision maker.
    
    Responsibilities:
    - Listen to signals from analyst agents
    - Calculate weighted score from multiple signals
    - Request validation from Risk Manager
    - Emit final trading decisions
    - Maintain audit log of all decisions
    
    Decision Criteria:
    - Score ≥ 0.65 + Risk OK → Execute 100%
    - Score 0.50-0.65 + Risk OK → Execute 50%
    - Score < 0.50 → Discard
    - Risk rejects → Discard + log reason
    """
    
    # Decision thresholds
    DECISION_THRESHOLD = 0.65
    REDUCED_THRESHOLD = 0.50
    
    # Weights by agent type (for multi-agent future)
    WEIGHTS = {
        "technical_analyst": 0.40,
        "fundamental_analyst": 0.30,  # Future
        "sentiment_analyst": 0.30,     # Future
    }
    
    def __init__(
        self,
        config: Dict[str, Any],
        message_bus: MessageBus,
        redis_client: redis.Redis
    ):
        """
        Initialize Orchestrator Agent.
        
        Args:
            config: Configuration dict with:
                - decision_threshold: Score needed for full execution
                - reduced_threshold: Score needed for reduced execution
                - state_ttl_seconds: TTL for pending validations
            message_bus: Shared MessageBus instance
            redis_client: Redis client for state management
        """
        super().__init__("orchestrator", config, message_bus)
        
        self.redis = redis_client
        
        # Configuration
        self.decision_threshold = config.get("decision_threshold", self.DECISION_THRESHOLD)
        self.reduced_threshold = config.get("reduced_threshold", self.REDUCED_THRESHOLD)
        self.state_ttl = config.get("state_ttl_seconds", 300)
        
        # In-memory tracking of pending validations
        self._pending_validations: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info(
            f"Orchestrator initialized: "
            f"decision_threshold={self.decision_threshold:.2f}, "
            f"reduced_threshold={self.reduced_threshold:.2f}"
        )
    
    async def setup(self):
        """Initialize agent - subscribe to channels."""
        self.bus.subscribe("signals", self._handle_signal)
        self.bus.subscribe("risk:responses", self._handle_risk_response)
        
        # Load previous state if exists
        await self._load_state()
        
        self.logger.info("Orchestrator setup complete")
    
    async def process(self):
        """
        Background maintenance loop.
        
        Cleans up expired pending validations.
        """
        await self._cleanup_expired()
        await asyncio.sleep(10)
    
    async def _handle_signal(self, signal: TradingSignal):
        """
        Handle incoming trading signal.
        
        Args:
            signal: TradingSignal from analyst agent
        """
        self.logger.info(
            f"Received signal: {signal.symbol} {signal.direction.value} "
            f"from {signal.from_agent} (confidence: {signal.confidence:.2f})"
        )
        
        # Calculate weighted score
        score = self._calculate_weighted_score(signal)
        
        # Check if score meets minimum threshold
        if score < self.reduced_threshold:
            self._log_decision(
                signal,
                "discarded",
                f"Score {score:.2f} < threshold {self.reduced_threshold:.2f}"
            )
            self.logger.info(f"Signal discarded: score {score:.2f} too low")
            return
        
        # Determine sizing factor based on score
        sizing_factor = 1.0 if score >= self.decision_threshold else 0.5
        
        # Get capital and positions from Redis
        capital = await self._get_capital()
        positions = await self._get_positions()
        
        # Create risk validation request
        request = RiskRequest(
            signal=signal,
            capital=capital,
            current_positions=positions
        )
        
        # Store pending validation
        self._pending_validations[request.request_id] = {
            "signal": signal,
            "score": score,
            "sizing_factor": sizing_factor,
            "timestamp": datetime.utcnow()
        }
        
        # Request validation from Risk Manager
        self.bus.publish("risk:requests", request)
        self.logger.info(f"Sent risk validation request: {request.request_id}")
    
    async def _handle_risk_response(self, response: RiskResponse):
        """
        Handle risk validation response.
        
        Args:
            response: RiskResponse from Risk Manager
        """
        # Retrieve pending validation
        pending = self._pending_validations.pop(response.request_id, None)
        
        if not pending:
            self.logger.warning(
                f"Received orphan risk response: {response.request_id}"
            )
            return
        
        signal = pending["signal"]
        score = pending["score"]
        sizing_factor = pending["sizing_factor"]
        
        self.logger.info(
            f"Received risk response for {signal.symbol}: "
            f"approved={response.approved}"
        )
        
        if not response.approved:
            # Risk rejected
            self._log_decision(
                signal,
                "rejected",
                response.rejection_reason or "Risk Manager rejection"
            )
            self.logger.warning(
                f"Risk rejected {signal.symbol}: {response.rejection_reason}"
            )
            return
        
        # Risk approved - emit decision
        final_size = int(response.adjusted_size * sizing_factor)
        
        decision = Decision(
            signal=signal,
            score=score,
            action="execute",
            size=final_size,
            adjustments=response.adjustments,
            warnings=response.warnings,
            reasoning=(
                f"Score: {score:.2f}, "
                f"Sizing: {sizing_factor:.0%}, "
                f"Risk adjustments: {len(response.adjustments)}"
            )
        )
        
        self.bus.publish("decisions", decision)
        
        self._log_decision(
            signal,
            "approved",
            f"Size: {final_size}, Score: {score:.2f}"
        )
        
        self.logger.info(
            f"Decision published: {signal.symbol} {signal.direction.value} "
            f"size={final_size}"
        )
        
        # Save state
        await self._save_state()
    
    def _calculate_weighted_score(self, signal: TradingSignal) -> float:
        """
        Calculate weighted score from signal.
        
        In Phase 3, only Technical Analyst is active, so weight is 1.0.
        In future phases with multiple analysts, this will aggregate scores.
        
        Args:
            signal: TradingSignal to score
            
        Returns:
            Weighted confidence score (0-1)
        """
        agent_weight = self.WEIGHTS.get(signal.from_agent, 0)
        
        # For now, only technical analyst is active
        # Normalize by active weight
        active_weight = self.WEIGHTS["technical_analyst"]
        normalized_weight = agent_weight / active_weight if active_weight > 0 else 0
        
        # Simply return signal confidence * normalized weight
        # When multiple analysts are active, this will aggregate their signals
        return signal.confidence * normalized_weight
    
    async def _get_capital(self) -> float:
        """
        Get current portfolio capital from Redis.
        
        Returns:
            Available capital
        """
        try:
            capital = self.redis.get("portfolio:capital")
            if capital:
                return float(capital)
        except Exception as e:
            self.logger.error(f"Error getting capital from Redis: {e}")
        
        # Default fallback
        return 100000.0
    
    async def _get_positions(self) -> list[dict]:
        """
        Get current open positions from Redis.
        
        Returns:
            List of position dicts
        """
        try:
            positions = self.redis.hgetall("positions")
            if positions:
                return [json.loads(p) for p in positions.values()]
        except Exception as e:
            self.logger.error(f"Error getting positions from Redis: {e}")
        
        # Default empty
        return []
    
    def _log_decision(self, signal: TradingSignal, action: str, reason: str):
        """
        Log decision to Redis audit log.
        
        Args:
            signal: TradingSignal
            action: Action taken (approved/rejected/discarded)
            reason: Reason for action
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "from_agent": signal.from_agent,
            "confidence": signal.confidence,
            "action": action,
            "reason": reason
        }
        
        try:
            # Add to audit log list (keep last 1000)
            self.redis.lpush("audit:decisions", json.dumps(log_entry))
            self.redis.ltrim("audit:decisions", 0, 999)
        except Exception as e:
            self.logger.error(f"Error logging decision: {e}")
    
    async def _cleanup_expired(self):
        """Clean up expired pending validations."""
        now = datetime.utcnow()
        expired_keys = []
        
        for request_id, pending in self._pending_validations.items():
            age = (now - pending["timestamp"]).total_seconds()
            if age > 30:  # 30 second timeout
                expired_keys.append(request_id)
        
        for key in expired_keys:
            pending = self._pending_validations.pop(key)
            self.logger.warning(
                f"Expired pending validation: {pending['signal'].symbol} "
                f"(age: {age:.0f}s)"
            )
    
    async def _load_state(self):
        """Load previous state from Redis (if exists)."""
        try:
            # Could restore pending validations here if needed
            pass
        except Exception as e:
            self.logger.error(f"Error loading state: {e}")
    
    async def _save_state(self):
        """Save current state to Redis."""
        try:
            # Could persist pending validations here if needed
            pass
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
