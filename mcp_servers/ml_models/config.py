"""
Configuration for ML Models MCP Server
"""

import os
from pydantic import BaseModel

class MLModelsConfig(BaseModel):
    """Configuration for ML Models Server."""
    port: int = 3005
    active_model: str = "rules"  # hmm, rules, ppo
    
    # Model specific settings
    hmm_states: int = 4
    hmm_features: list[str] = ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
    
    rules_bull_threshold: float = 0.02
    rules_bear_threshold: float = -0.02
    
    @classmethod
    def from_env(cls) -> "MLModelsConfig":
        """Load configuration from environment variables."""
        return cls(
            port=int(os.getenv("MCP_ML_PORT", "3005")),
            active_model=os.getenv("MCP_ML_ACTIVE_MODEL", "rules")
        )

config = MLModelsConfig.from_env()
