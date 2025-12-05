"""
Tool to get ML model information.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ml.factory import RegimeDetectorFactory

logger = logging.getLogger(__name__)


async def handle_get_model_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get information about ML model.
    
    Args:
        args:
            - model_type: Model type (optional, default = active)
    
    Returns:
        Dict with model info
    """
    try:
        factory = RegimeDetectorFactory.get_instance()
        model_type = args.get("model_type")
        
        if model_type:
            detector = factory.create_regime_detector(model_type, load_trained=True)
        else:
            detector = factory.get_active_detector()
        
        metrics = detector.get_metrics()
        
        return {
            "model_id": metrics.model_id,
            "version": metrics.version,
            "model_type": model_type or factory.get_active_model_type(),
            "is_fitted": detector.is_fitted,
            "required_features": detector.required_features,
            "trained_at": metrics.trained_at.isoformat() if metrics.trained_at else None,
            "train_samples": metrics.train_samples,
            "predictions_count": metrics.predictions_count,
            "inference_time_avg_ms": metrics.inference_time_avg_ms,
            "regime_distribution": metrics.regime_distribution,
            "metrics": {
                "log_likelihood": metrics.log_likelihood,
                "aic": metrics.aic,
                "bic": metrics.bic,
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def handle_list_models(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List available models.
    
    Returns:
        Dict with available models and active model
    """
    try:
        factory = RegimeDetectorFactory.get_instance()
        
        return {
            "available_models": factory.get_available_models(),
            "active_model": factory.get_active_model_type(),
            "models_dir": str(factory.get_models_dir()),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
