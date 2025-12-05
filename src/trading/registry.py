"""
Strategy Registry for managing trading strategies.

Handles:
- Loading strategies from PostgreSQL
- State management in Redis (active, paused, etc.)
- Regime-based activation
- Dynamic weight calculation based on performance
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
import logging
import json

import redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class StrategyState(str, Enum):
    """
    Strategy operational states.
    
    States:
        ACTIVE: Strategy can generate signals and execute trades
        PAUSED: Strategy paused manually (no new trades)
        REGIME_DISABLED: Automatically disabled due to unfavorable regime
        DRAWDOWN_DISABLED: Disabled due to exceeding drawdown limit
        PAPER_ONLY: Generates signals but doesn't execute (testing mode)
    """
    ACTIVE = "active"
    PAUSED = "paused"
    REGIME_DISABLED = "regime_disabled"
    DRAWDOWN_DISABLED = "drawdown_disabled"
    PAPER_ONLY = "paper_only"


@dataclass
class StrategyConfig:
    """
    Configuration for a trading strategy.
    
    Attributes:
        id: Unique strategy identifier
        name: Human-readable strategy name
        enabled: Whether strategy is enabled in DB
        markets: List of markets (e.g., ['BME', 'XETRA'])
        regime_filter: Compatible market regimes
        timeframe: Trading timeframe (e.g., '1d', '1h')
        params: Strategy-specific parameters (dict)
        risk_params: Risk management parameters (dict)
        description: Strategy description
    """
    id: str
    name: str
    enabled: bool
    markets: List[str]
    regime_filter: List[str]
    timeframe: str
    params: Dict
    risk_params: Dict
    description: Optional[str] = None


class StrategyRegistry:
    """
    Central registry for managing trading strategies.
    
    Responsibilities:
    - Load enabled strategies from PostgreSQL
    - Manage strategy states in Redis
    - Filter strategies by market regime
    - Calculate dynamic strategy weights based on performance
    
    Usage:
        >>> registry = StrategyRegistry(db_session, redis_client)
        >>> registry.load_strategies()
        >>> active = registry.get_active_for_regime("trending_bull")
        >>> weights = registry.calculate_weights(["swing_momentum_eu"], performance_data)
    """
    
    def __init__(self, db: Session, redis_client: redis.Redis):
        """
        Initialize Strategy Registry.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Redis client for state management
        """
        self.db = db
        self.redis = redis_client
        self._strategies: Dict[str, StrategyConfig] = {}
        self.logger = logging.getLogger(f"{__name__}.StrategyRegistry")
    
    def load_strategies(self) -> int:
        """
        Load all enabled strategies from PostgreSQL.
        
        Returns:
            Number of strategies loaded
            
        Raises:
            Exception: If database query fails
        """
        try:
            query = text("""
                SELECT id, name, enabled, markets, regime_filter, 
                       timeframe, params, risk_params, description
                FROM config.strategies
                WHERE enabled = true
                ORDER BY id
            """)
            
            result = self.db.execute(query)
            rows = result.fetchall()
            
            self._strategies.clear()
            
            for row in rows:
                config = StrategyConfig(
                    id=row.id,
                    name=row.name,
                    enabled=row.enabled,
                    markets=list(row.markets),
                    regime_filter=list(row.regime_filter),
                    timeframe=row.timeframe,
                    params=dict(row.params),
                    risk_params=dict(row.risk_params),
                    description=row.description
                )
                
                self._strategies[config.id] = config
                
                # Initialize state in Redis if not exists
                if not self.redis.exists(f"strategy:{config.id}"):
                    self._initialize_state(config.id)
            
            self.logger.info(f"Loaded {len(self._strategies)} enabled strategies")
            return len(self._strategies)
            
        except Exception as e:
            self.logger.error(f"Failed to load strategies: {e}", exc_info=True)
            raise
    
    def _initialize_state(self, strategy_id: str) -> None:
        """
        Initialize strategy state in Redis.
        
        Args:
            strategy_id: Strategy identifier
        """
        self.redis.hset(
            f"strategy:{strategy_id}",
            mapping={
                "state": StrategyState.PAUSED.value,  # Start paused by default
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "reason": "Initial state"
            }
        )
        self.logger.debug(f"Initialized state for strategy {strategy_id}")
    
    def get_state(self, strategy_id: str) -> StrategyState:
        """
        Get current state of a strategy from Redis.
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            Current strategy state
        """
        state_bytes = self.redis.hget(f"strategy:{strategy_id}", "state")
        
        if state_bytes is None:
            self.logger.warning(f"No state found for {strategy_id}, initializing")
            self._initialize_state(strategy_id)
            return StrategyState.PAUSED
        
        state_str = state_bytes.decode() if isinstance(state_bytes, bytes) else state_bytes
        return StrategyState(state_str)
    
    def set_state(
        self, 
        strategy_id: str, 
        state: StrategyState, 
        reason: str = ""
    ) -> None:
        """
        Change strategy state with audit logging.
        
        Args:
            strategy_id: Strategy identifier
            state: New state to set
            reason: Reason for state change
            
        Raises:
            ValueError: If strategy not found or invalid state transition
        """
        if strategy_id not in self._strategies:
            raise ValueError(f"Strategy {strategy_id} not found in registry")
        
        current_state = self.get_state(strategy_id)
        
        # Validate state transition
        if not self._is_valid_transition(current_state, state):
            raise ValueError(
                f"Invalid state transition for {strategy_id}: "
                f"{current_state} → {state}"
            )
        
        # Update Redis
        self.redis.hset(
            f"strategy:{strategy_id}",
            mapping={
                "state": state.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "previous_state": current_state.value
            }
        )
        
        # Audit log
        self.logger.info(
            f"Strategy {strategy_id} state changed: "
            f"{current_state} → {state} (reason: {reason})"
        )
    
    def _is_valid_transition(
        self, 
        current: StrategyState, 
        new: StrategyState
    ) -> bool:
        """
        Validate if state transition is allowed.
        
        Args:
            current: Current state
            new: Proposed new state
            
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            StrategyState.ACTIVE: {
                StrategyState.PAUSED,
                StrategyState.REGIME_DISABLED,
                StrategyState.DRAWDOWN_DISABLED,
                StrategyState.PAPER_ONLY
            },
            StrategyState.PAUSED: {
                StrategyState.ACTIVE,
                StrategyState.PAPER_ONLY
            },
            StrategyState.REGIME_DISABLED: {
                StrategyState.ACTIVE,  # Auto-reactivate when regime changes
                StrategyState.PAUSED
            },
            StrategyState.DRAWDOWN_DISABLED: {
                StrategyState.ACTIVE,  # Manual reactivation only
                StrategyState.PAUSED
            },
            StrategyState.PAPER_ONLY: {
                StrategyState.ACTIVE,
                StrategyState.PAUSED
            }
        }
        
        allowed = valid_transitions.get(current, set())
        return new in allowed
    
    def get_active_for_regime(self, regime: str) -> List[StrategyConfig]:
        """
        Get all active strategies compatible with current regime.
        
        Args:
            regime: Current market regime (e.g., 'trending_bull')
            
        Returns:
            List of active strategy configurations
        """
        active_strategies = []
        
        for strategy_id, config in self._strategies.items():
            # Check if state is ACTIVE
            if self.get_state(strategy_id) != StrategyState.ACTIVE:
                continue
            
            # Check if regime is compatible
            if regime in config.regime_filter:
                active_strategies.append(config)
        
        self.logger.debug(
            f"Found {len(active_strategies)} active strategies for regime '{regime}'"
        )
        return active_strategies
    
    def calculate_weights(
        self,
        active_strategy_ids: List[str],
        performance: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Calculate dynamic strategy weights based on performance.
        
        Weight formula:
            raw_weight = sharpe_3m * (1 - current_dd / max_dd)
        
        Constraints (adaptive based on number of strategies):
            - 2 strategies: No constraints (0-100%) to show performance differences
            - 3+ strategies: Min 10%, Max 50% to enforce diversification
            - Weights always sum to 1.0
        
        Args:
            active_strategy_ids: List of active strategy IDs
            performance: Dict of {strategy_id: {sharpe_3m, drawdown, ...}}
            
        Returns:
            Dict of {strategy_id: weight}
            
        Example:
            >>> performance = {
            ...     "swing_momentum": {"sharpe_3m": 1.5, "drawdown": 0.05},
            ...     "mean_reversion": {"sharpe_3m": 1.0, "drawdown": 0.03}
            ... }
            >>> weights = registry.calculate_weights(["swing_momentum", "mean_reversion"], performance)
            >>> # weights = {"swing_momentum": ~0.6, "mean_reversion": ~0.4} (varies by performance)
        """
        if not active_strategy_ids:
            return {}
        
        weights = {}
        total_raw = 0.0
        
        # Calculate raw weights
        for strategy_id in active_strategy_ids:
            if strategy_id not in self._strategies:
                self.logger.warning(f"Strategy {strategy_id} not in registry, skipping")
                continue
            
            perf = performance.get(strategy_id, {})
            sharpe = perf.get("sharpe_3m", 0.5)  # Default conservative Sharpe
            dd_actual = perf.get("drawdown", 0.0)
            dd_max = self._strategies[strategy_id].risk_params.get("max_drawdown", 0.15)
            
            # Formula: sharpe * (1 - dd_penalty)
            dd_penalty = dd_actual / dd_max if dd_max > 0 else 0
            raw_weight = max(0, sharpe * (1 - dd_penalty))
            
            weights[strategy_id] = raw_weight
            total_raw += raw_weight
        
        if total_raw == 0:
            # Equal weights if no performance data
            equal_weight = 1.0 / len(active_strategy_ids)
            return {sid: equal_weight for sid in active_strategy_ids}
        
        # Normalize to sum to 1.0
        for strategy_id in weights:
            weights[strategy_id] /= total_raw
        
        # Apply min/max constraints based on number of strategies
        num_strategies = len(active_strategy_ids)
        
        if num_strategies == 2:
            # For 2 strategies, use no constraints to show performance differences
            min_weight = 0.0
            max_weight = 1.0
        else:
            # For 3+ strategies, enforce diversification
            min_weight = 0.10
            max_weight = 0.50
        
        # Iteratively apply constraints to maintain sum=1.0
        max_iterations = 10
        for _ in range(max_iterations):
            adjusted = False
            total = sum(weights.values())
            
            # Clip to constraints
            for strategy_id in list(weights.keys()):
                old_weight = weights[strategy_id]
                new_weight = max(min_weight, min(max_weight, old_weight))
                if abs(new_weight - old_weight) > 1e-9:
                    weights[strategy_id] = new_weight
                    adjusted = True
            
            if not adjusted:
                break
            
            # Redistribute excess/deficit among unconstrained strategies
            total = sum(weights.values())
            if abs(total - 1.0) > 1e-9:
                # Find strategies not at limits
                flexible_ids = [
                    sid for sid in weights
                    if min_weight < weights[sid] < max_weight
                ]
                
                if flexible_ids:
                    # Adjust flexible weights proportionally
                    adjustment_factor = (1.0 - sum(
                        weights[sid] for sid in weights if sid not in flexible_ids
                    )) / sum(weights[sid] for sid in flexible_ids)
                    
                    for sid in flexible_ids:
                        weights[sid] *= adjustment_factor
                else:
                    # All at limits, just normalize
                    weights = {sid: w / total for sid, w in weights.items()}
        
        self.logger.info(
            f"Calculated weights for {len(weights)} strategies: "
            f"{json.dumps({k: round(v, 3) for k, v in weights.items()})}"
        )
        
        return weights
    
    def get_strategy(self, strategy_id: str) -> Optional[StrategyConfig]:
        """
        Get strategy configuration by ID.
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            Strategy configuration or None if not found
        """
        return self._strategies.get(strategy_id)
    
    def list_all_strategies(self) -> List[StrategyConfig]:
        """
        Get list of all loaded strategies.
        
        Returns:
            List of all strategy configurations
        """
        return list(self._strategies.values())
    
    def get_strategy_count(self) -> int:
        """
        Get total number of loaded strategies.
        
        Returns:
            Number of strategies in registry
        """
        return len(self._strategies)
