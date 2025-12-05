"""
Tool for regime prediction for mcp-ml-models.

Updated in Phase A2 to use real models via Factory.
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Optional, Any, Dict
from pathlib import Path

# Ensure src is in path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ml.factory import RegimeDetectorFactory, get_regime_detector
from src.ml.interfaces import RegimePrediction, RegimeType
from src.ml.exceptions import (
    ModelNotFittedError,
    InvalidFeaturesError,
    MLError
)

logger = logging.getLogger(__name__)

# Simple in-memory cache
_prediction_cache: Dict[str, tuple] = {}  # key -> (prediction, timestamp)
CACHE_TTL_SECONDS = 300  # 5 minutes


class RegimeTool:
    """
    Tool to get market regime prediction.
    
    Integrates with ML Factory to use the configured model.
    Includes cache to avoid repeated predictions.
    """
    
    def __init__(self, config_path: str = "config/ml_models.yaml"):
        """
        Initialize the tool.
        
        Args:
            config_path: Path to ML models configuration
        """
        self.config_path = config_path
        self._factory: Optional[RegimeDetectorFactory] = None
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Initialize factory if not already done."""
        if not self._initialized:
            try:
                self._factory = RegimeDetectorFactory.get_instance(self.config_path)
                self._initialized = True
                logger.info("RegimeTool initialized correctly")
            except Exception as e:
                logger.error(f"Error initializing RegimeTool: {e}")
                raise
    
    async def predict(
        self,
        features: Optional[Dict[str, float]] = None,
        symbol: Optional[str] = None,
        use_cache: bool = True,
        model_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict current market regime.
        
        Args:
            features: Dict with features {name: value}
                     If None, tries to get current features
            symbol: Specific symbol (for cache key)
            use_cache: Whether to use prediction cache
            model_type: Specific model type (None = active)
        
        Returns:
            Dict with prediction and metadata
        """
        self._ensure_initialized()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(features, symbol, model_type)
            
            # Check cache
            if use_cache and cache_key in _prediction_cache:
                cached_pred, cached_time = _prediction_cache[cache_key]
                age = (datetime.now() - cached_time).total_seconds()
                
                if age < CACHE_TTL_SECONDS:
                    logger.debug(f"Cache hit for {cache_key} (age: {age:.0f}s)")
                    return {
                        **cached_pred,
                        "cached": True,
                        "cache_age_seconds": age
                    }
            
            # Get detector
            if model_type:
                detector = self._factory.create_regime_detector(model_type)
            else:
                detector = self._factory.get_active_detector()
            
            # Validate model is ready
            if not detector.is_fitted:
                return {
                    "error": "Model not trained",
                    "regime": RegimeType.UNKNOWN.value,
                    "confidence": 0.0,
                    "model_id": detector.model_id,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Prepare features
            if features is None:
                features = await self._get_current_features(symbol)
            
            # Convert dict to array
            import numpy as np
            feature_names = detector.required_features
            X = np.array([[features.get(f, 0.0) for f in feature_names]])
            
            # Predict
            prediction = detector.predict(X)
            
            # Format result
            result = {
                "regime": prediction.regime.value,
                "confidence": prediction.confidence,
                "probabilities": prediction.probabilities,
                "model_id": prediction.model_id,
                "inference_time_ms": prediction.inference_time_ms,
                "features_used": prediction.features_used,
                "timestamp": prediction.timestamp.isoformat(),
                "is_tradeable": prediction.is_tradeable,
                "is_high_confidence": prediction.is_high_confidence,
                "cached": False
            }
            
            # Add metadata if exists
            if prediction.metadata:
                result["metadata"] = prediction.metadata
            
            # Save to cache
            if use_cache:
                _prediction_cache[cache_key] = (result, datetime.now())
            
            logger.info(
                f"Prediction: {prediction.regime.value} "
                f"(confidence: {prediction.confidence:.0%}, "
                f"model: {prediction.model_id})"
            )
            
            return result
            
        except ModelNotFittedError as e:
            logger.warning(f"Model not trained: {e}")
            return {
                "error": str(e),
                "regime": RegimeType.UNKNOWN.value,
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
        
        except InvalidFeaturesError as e:
            logger.warning(f"Invalid features: {e}")
            return {
                "error": str(e),
                "regime": RegimeType.UNKNOWN.value,
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error in prediction: {e}", exc_info=True)
            return {
                "error": f"Internal error: {str(e)}",
                "regime": RegimeType.UNKNOWN.value,
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
    
    def _generate_cache_key(
        self,
        features: Optional[Dict],
        symbol: Optional[str],
        model_type: Optional[str]
    ) -> str:
        """Generate unique cache key."""
        parts = [
            model_type or "active",
            symbol or "market",
        ]
        
        if features:
            # Simplified feature hash
            feature_str = "_".join(f"{k}:{v:.4f}" for k, v in sorted(features.items()))
            parts.append(feature_str[:50])
        
        return ":".join(parts)
    
    async def _get_current_features(self, symbol: Optional[str] = None) -> Dict[str, float]:
        """
        Get current features from system.
        
        In production, this would connect to mcp-market-data and mcp-technical.
        For now returns example values.
        """
        # TODO: Integrate with mcp-market-data and mcp-technical
        # For now, example values for testing
        logger.warning("Using example features - implement real integration")
        
        return {
            "returns_5d": 0.015,
            "volatility_20d": 0.18,
            "adx_14": 28.5,
            "volume_ratio": 1.1
        }
    
    def clear_cache(self) -> int:
        """
        Clear prediction cache.
        
        Returns:
            Number of entries removed
        """
        global _prediction_cache
        count = len(_prediction_cache)
        _prediction_cache = {}
        logger.info(f"Cache cleared: {count} entries removed")
        return count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(_prediction_cache),
            "ttl_seconds": CACHE_TTL_SECONDS,
            "keys": list(_prediction_cache.keys())
        }


# Global tool instance
_regime_tool: Optional[RegimeTool] = None


def get_regime_tool(config_path: str = "config/ml_models.yaml") -> RegimeTool:
    """Get singleton tool instance."""
    global _regime_tool
    if _regime_tool is None:
        _regime_tool = RegimeTool(config_path)
    return _regime_tool


# Function for MCP handler
async def handle_get_regime(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler for MCP tool get_regime.
    
    Args:
        args: Tool arguments:
            - features: Optional dict with features
            - symbol: Optional symbol
            - model_type: Optional model type
            - use_cache: Whether to use cache (default True)
    
    Returns:
        Prediction result
    """
    tool = get_regime_tool()
    
    return await tool.predict(
        features=args.get("features"),
        symbol=args.get("symbol"),
        use_cache=args.get("use_cache", True),
        model_type=args.get("model_type")
    )
