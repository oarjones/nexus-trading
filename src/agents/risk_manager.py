"""
Risk Manager Agent.

Validates trading operations against hardcoded risk limits and calculates
appropriate position sizing with adjustments.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from uuid import uuid4

from .base import BaseAgent
from .messaging import MessageBus
from .schemas import RiskRequest, RiskResponse, Alert
from .mcp_client import MCPClient, MCPServers

logger = logging.getLogger(__name__)


class RiskManagerAgent(BaseAgent):
    """
    Risk Manager Agent - Validates trades and calculates sizing.
    
    Responsibilities:
    - Listen to risk:requests channel
    - Validate against HARDCODED limits
    - Calculate position sizing with adjustments
    - Publish responses on risk:responses channel
    - Monitor drawdown continuously (kill switch)
    
    HARDCODED LIMITS (NOT configurable):
    - MAX_POSITION_PCT = 0.20 (20% max per position)
    - MAX_SECTOR_PCT = 0.40 (40% max per sector)
    - MAX_CORRELATION = 0.70 (70% max correlation)
    - MAX_DRAWDOWN = 0.15 (15% max drawdown - KILL SWITCH)
    - MIN_CASH_PCT = 0.10 (10% min cash reserve)
    """
    
    # HARDCODED LIMITS - DO NOT MODIFY
    MAX_POSITION_PCT = 0.20
    MAX_SECTOR_PCT = 0.40
    MAX_CORRELATION = 0.70
    MAX_DRAWDOWN = 0.15
    MIN_CASH_PCT = 0.10
    
    def __init__(
        self,
        config: Dict[str, Any],
        message_bus: MessageBus,
        mcp_servers: MCPServers
    ):
        """
        Initialize Risk Manager Agent.
        
        Args:
            config: Configuration dict with:
                - base_risk_per_trade: Base risk per trade (e.g., 0.01 = 1%)
                - kelly_fraction: Kelly criterion fraction (e.g., 0.25 = 25%)
                - drawdown_check_seconds: How often to check drawdown
            message_bus: Shared MessageBus instance
            mcp_servers: MCP server URLs
        """
        super().__init__("risk_manager", config, message_bus)
        
        self.mcp_servers = mcp_servers
        self.mcp_client = MCPClient()
        
        # Configuration
        self.base_risk_per_trade = config.get("base_risk_per_trade", 0.01)
        self.kelly_fraction = config.get("kelly_fraction", 0.25)
        self.drawdown_check_seconds = config.get("drawdown_check_seconds", 10)
        
        # State
        self._kill_switch_activated = False
        
        self.logger.info(
            f"Risk Manager initialized: "
            f"base_risk={self.base_risk_per_trade:.1%}, "
            f"kelly_fraction={self.kelly_fraction:.0%}"
        )
        self.logger.warning(
            f"HARDCODED LIMITS: "
            f"max_position={self.MAX_POSITION_PCT:.0%}, "
            f"max_sector={self.MAX_SECTOR_PCT:.0%}, "
            f"max_drawdown={self.MAX_DRAWDOWN:.0%}"
        )
    
    async def setup(self):
        """Initialize agent - subscribe to risk requests."""
        self.bus.subscribe("risk:requests", self._handle_request)
        self.logger.info("Risk Manager setup complete, listening for requests")
   
    async def process(self):
        """
        Background monitoring loop.
        
        Risk Manager is primarily reactive (handles requests via message bus),
        but continuously monitors drawdown in background.
        """
        await self._check_drawdown()
        await asyncio.sleep(self.drawdown_check_seconds)
    
    async def _handle_request(self, request: RiskRequest):
        """
        Handle risk validation request.
        
        Args:
            request: RiskRequest from Orchestrator
        """
        self.logger.info(
            f"Received risk request: {request.signal.symbol} "
            f"{request.signal.direction.value} (confidence: {request.signal.confidence:.2f})"
        )
        
        # Check kill switch
        if self._kill_switch_activated:
            response = RiskResponse(
                request_id=request.request_id,
                approved=False,
                original_size=0,
                adjusted_size=0,
                adjustments=[],
                warnings=[],
                rejection_reason="KILL SWITCH ACTIVATED: Max drawdown exceeded"
            )
            self.bus.publish("risk:responses", response)
            return
        
        # Validate limits
        approved, rejection_reason = await self._validate_limits(request)
        
        if not approved:
            response = RiskResponse(
                request_id=request.request_id,
                approved=False,
                original_size=0,
                adjusted_size=0,
                adjustments=[],
                warnings=[],
                rejection_reason=rejection_reason
            )
            self.logger.warning(f"Request rejected: {rejection_reason}")
        else:
            # Calculate sizing
            size_result = await self._calculate_sizing(request)
            
            response = RiskResponse(
                request_id=request.request_id,
                approved=True,
                original_size=size_result["original"],
                adjusted_size=size_result["adjusted"],
                adjustments=size_result["adjustments"],
                warnings=size_result["warnings"]
            )
            self.logger.info(
                f"Request approved: original={size_result['original']}, "
                f"adjusted={size_result['adjusted']}"
            )
        
        self.bus.publish("risk:responses", response)
    
    async def _validate_limits(self, request: RiskRequest) -> Tuple[bool, Optional[str]]:
        """
        Validate request against HARDCODED limits.
        
        Args:
            request: RiskRequest to validate
            
        Returns:
            Tuple of (approved, rejection_reason)
        """
        signal = request.signal
        capital = request.capital
        
        # Get current exposure
        try:
            exposure = await self.mcp_client.call(
                self.mcp_servers.risk,
                "get_exposure",
                {
                    "portfolio_value": capital,
                    "positions": request.current_positions
                }
            )
        except Exception as e:
            self.logger.error(f"Error getting exposure: {e}")
            return False, f"Error retrieving portfolio exposure: {e}"
        
        # 1. Check minimum cash
        cash_pct = exposure.get("cash_pct", 0)
        if cash_pct < self.MIN_CASH_PCT:
            return False, f"Insufficient cash ({cash_pct:.1%} < {self.MIN_CASH_PCT:.0%})"
        
        # 2. Check drawdown
        current_dd = await self._get_current_drawdown()
        if current_dd > self.MAX_DRAWDOWN:
            return False, f"Drawdown exceeded ({current_dd:.1%} > {self.MAX_DRAWDOWN:.0%})"
        
        # 3. Check sector concentration
        sector = self._get_sector(signal.symbol)
        sector_exposure = exposure.get("exposure_by_sector", {}).get(sector, 0)
        sector_pct = sector_exposure / capital if capital > 0 else 0
        
        if sector_pct > self.MAX_SECTOR_PCT:
            return False, f"Sector '{sector}' exposure exceeded ({sector_pct:.1%} > {self.MAX_SECTOR_PCT:.0%})"
        
        return True, None
    
    async def _calculate_sizing(self, request: RiskRequest) -> Dict[str, Any]:
        """
        Calculate position sizing with adjustments.
        
        Args:
            request: RiskRequest
            
        Returns:
            Dict with original, adjusted, adjustments, warnings
        """
        signal = request.signal
        capital = request.capital
        adjustments = []
        warnings = []
        
        # Base position sizing
        risk_amount = capital * self.base_risk_per_trade * signal.confidence
        distance_to_stop = abs(signal.entry_price - signal.stop_loss)
        
        if distance_to_stop == 0:
            distance_to_stop = signal.entry_price * 0.02  # Default 2%
            warnings.append("Stop distance was 0, using 2% default")
        
        shares = int(risk_amount / distance_to_stop)
        original_shares = shares
        position_value = shares * signal.entry_price
        
        # Adjustment 1: Max position limit
        max_value = capital * self.MAX_POSITION_PCT
        if position_value > max_value:
            factor = max_value / position_value
            shares = int(shares * factor)
            adjustments.append({
                "reason": "max_position_limit",
                "factor": round(factor, 2),
                "limit": f"{self.MAX_POSITION_PCT:.0%}"
            })
        
        # Adjustment 2: Correlation (simplified - would need correlation matrix)
        # For now, just a placeholder check
        correlation = await self._get_portfolio_correlation(signal.symbol)
        if correlation > 0.5:
            factor = 0.7
            shares = int(shares * factor)
            adjustments.append({
                "reason": "high_correlation",
                "factor": factor,
                "correlation": round(correlation, 2)
            })
        
        # Adjustment 3: Regime (volatility)
        try:
            regime = await self.mcp_client.call(
                self.mcp_servers.technical,
                "get_regime",
                {"symbol": signal.symbol}
            )
            
            if regime.get("regime") == "high_volatility":
                factor = 0.5
                shares = int(shares * factor)
                adjustments.append({
                    "reason": "high_volatility_regime",
                    "factor": factor
                })
        except Exception as e:
            self.logger.warning(f"Could not get regime data: {e}")
        
        # Warnings for approaching limits
        try:
            exposure = await self.mcp_client.call(
                self.mcp_servers.risk,
                "get_exposure",
                {
                    "portfolio_value": capital,
                    "positions": request.current_positions
                }
            )
            
            sector = self._get_sector(signal.symbol)
            sector_exposure = exposure.get("exposure_by_sector", {}).get(sector, 0)
            sector_pct = sector_exposure / capital if capital > 0 else 0
            
            if sector_pct > 0.30:
                warnings.append(
                    f"Approaching sector limit ({sector_pct:.0%}/{self.MAX_SECTOR_PCT:.0%})"
                )
        except Exception as e:
            self.logger.warning(f"Could not check sector exposure: {e}")
        
        return {
            "original": original_shares,
            "adjusted": shares,
            "adjustments": adjustments,
            "warnings": warnings
        }
    
    async def _check_drawdown(self):
        """
        Monitor drawdown and activate kill switch if exceeded.
        
        This runs continuously in the background.
        """
        try:
            dd = await self._get_current_drawdown()
            
            if dd > self.MAX_DRAWDOWN and not self._kill_switch_activated:
                # ACTIVATE KILL SWITCH
               
                self._kill_switch_activated = True
                
                alert = Alert(
                    from_agent=self.name,
                    severity="critical",
                    message=f"KILL SWITCH ACTIVATED: Drawdown {dd:.1%} > {self.MAX_DRAWDOWN:.0%}",
                    context={"drawdown": dd, "limit": self.MAX_DRAWDOWN}
                )
                
                self.bus.publish("alerts", alert)
                self.logger.critical(f"KILL SWITCH ACTIVATED: Drawdown {dd:.1%}")
        
        except Exception as e:
            self.logger.error(f"Error checking drawdown: {e}")
    
    async def _get_current_drawdown(self) -> float:
        """
        Get current portfolio drawdown.
        
        Returns:
            Drawdown as decimal (e.g., 0.10 = 10%)
        """
        # Placeholder - would need to query portfolio state
        # For now, return 0
        # TODO: Implement actual drawdown calculation from portfolio history
        return 0.0
    
    async def _get_portfolio_correlation(self, symbol: str) -> float:
        """
        Get correlation of symbol with current portfolio.
        
        Args:
            symbol: Symbol to check correlation for
            
        Returns:
            Correlation coefficient (0-1)
        """
        # Placeholder - would need correlation matrix calculation
        # For now, return low correlation
        # TODO: Implement actual correlation calculation
        return 0.3
    
    def _get_sector(self, symbol: str) -> str:
        """
        Get sector for a symbol.
        
        Args:
            symbol: Symbol to get sector for
            
        Returns:
            Sector name
        """
        # Simplified mapping for Spanish stocks
        # In production, this would come from a database
        sector_map = {
            "SAN.MC": "Banking",
            "BBVA.MC": "Banking",
            "ITX.MC": "Retail",
            "IBE.MC": "Utilities",
            "TEF.MC": "Telecommunications"
        }
        
        return sector_map.get(symbol, "Unknown")
