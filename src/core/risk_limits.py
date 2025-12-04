"""
Centralized Risk Limits Configuration.

CRITICAL: These limits are HARDCODED and CANNOT be modified at runtime.
They represent the absolute maximum risk tolerance for the trading system.

All risk-related components (RiskManagerAgent, MCP risk server) MUST
import limits from this module to ensure consistency.
"""


class RiskLimits:
    """
    Global risk limits that cannot be modified at runtime.
    
    These limits are intentionally hardcoded to prevent accidental or
    malicious changes that could expose the system to excessive risk.
    
    DO NOT MODIFY THESE VALUES WITHOUT THOROUGH TESTING AND APPROVAL.
    """
    
    # Position Limits
    MAX_POSITION_PCT = 0.20      # 20% max per single position
    MAX_SECTOR_PCT = 0.40        # 40% max per sector
    MAX_CORRELATION = 0.70       # 70% max correlation between positions
    
    # Portfolio Limits
    MAX_DRAWDOWN = 0.15          # 15% max drawdown (triggers kill switch)
    MIN_CASH_PCT = 0.10          # 10% min cash reserve
    MAX_LEVERAGE = 1.0           # No leverage allowed
    MAX_DAILY_LOSS = 0.05        # 5% max daily loss
    
    # Risk Per Trade
    DEFAULT_RISK_PER_TRADE = 0.01    # 1% default risk per trade
    MAX_RISK_PER_TRADE = 0.02        # 2% absolute maximum per trade
    
    @classmethod
    def to_dict(cls) -> dict:
        """
        Export limits as dictionary.
        
        Returns:
            Dict with all limit values
        """
        return {
            "max_position_pct": cls.MAX_POSITION_PCT,
            "max_sector_pct": cls.MAX_SECTOR_PCT,
            "max_correlation": cls.MAX_CORRELATION,
            "max_drawdown": cls.MAX_DRAWDOWN,
            "min_cash_pct": cls.MIN_CASH_PCT,
            "max_leverage": cls.MAX_LEVERAGE,
            "max_daily_loss": cls.MAX_DAILY_LOSS,
            "default_risk_per_trade": cls.DEFAULT_RISK_PER_TRADE,
            "max_risk_per_trade": cls.MAX_RISK_PER_TRADE,
        }
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate that all limits are within sensible ranges.
        
        Returns:
            True if all limits are valid
            
        Raises:
            ValueError: If any limit is invalid
        """
        if not (0 < cls.MAX_POSITION_PCT <= 1.0):
            raise ValueError(f"MAX_POSITION_PCT must be 0-1, got {cls.MAX_POSITION_PCT}")
        
        if not (0 < cls.MAX_SECTOR_PCT <= 1.0):
            raise ValueError(f"MAX_SECTOR_PCT must be 0-1, got {cls.MAX_SECTOR_PCT}")
        
        if not (0 <= cls.MAX_CORRELATION <= 1.0):
            raise ValueError(f"MAX_CORRELATION must be 0-1, got {cls.MAX_CORRELATION}")
        
        if not (0 < cls.MAX_DRAWDOWN <= 1.0):
            raise ValueError(f"MAX_DRAWDOWN must be 0-1, got {cls.MAX_DRAWDOWN}")
        
        if not (0 < cls.MIN_CASH_PCT <= 1.0):
            raise ValueError(f"MIN_CASH_PCT must be 0-1, got {cls.MIN_CASH_PCT}")
        
        if cls.MAX_LEVERAGE < 1.0:
            raise ValueError(f"MAX_LEVERAGE must be >= 1.0, got {cls.MAX_LEVERAGE}")
        
        if not (0 < cls.MAX_DAILY_LOSS <= 1.0):
            raise ValueError(f"MAX_DAILY_LOSS must be 0-1, got {cls.MAX_DAILY_LOSS}")
        
        if cls.DEFAULT_RISK_PER_TRADE > cls.MAX_RISK_PER_TRADE:
            raise ValueError(
                f"DEFAULT_RISK_PER_TRADE ({cls.DEFAULT_RISK_PER_TRADE}) "
                f"cannot exceed MAX_RISK_PER_TRADE ({cls.MAX_RISK_PER_TRADE})"
            )
        
        return True


# Validate on module import
RiskLimits.validate()
