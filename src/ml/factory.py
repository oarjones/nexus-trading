"""
Factory for creating ML models based on configuration.

Allows instantiating the correct model based on YAML files,
facilitating switching between implementations without code changes.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Type
import yaml

from .interfaces import RegimeDetector, ModelFactory
from .models.hmm_regime import HMMRegimeDetector, HMMConfig
from .models.rules_baseline import RulesBaselineDetector, RulesConfig
from .exceptions import ConfigurationError, ModelLoadError

logger = logging.getLogger(__name__)


# Registry of available models
MODEL_REGISTRY: Dict[str, Type[RegimeDetector]] = {
    "hmm": HMMRegimeDetector,
    "rules": RulesBaselineDetector,
    # Future: "ppo": PPORegimeDetector,
}


class RegimeDetectorFactory(ModelFactory):
    """
    Factory for creating regime detectors.
    
    Reads configuration from YAML and creates the appropriate model.
    Maintains a cache of the active model to avoid reloading.
    
    Example:
        factory = RegimeDetectorFactory("config/ml_models.yaml")
        
        # Create active model based on config
        detector = factory.create_regime_detector()
        
        # Create specific model
        hmm_detector = factory.create_regime_detector("hmm")
    """
    
    _instance: Optional["RegimeDetectorFactory"] = None
    _active_detector: Optional[RegimeDetector] = None
    
    def __init__(self, config_path: str = "config/ml_models.yaml"):
        """
        Initialize the factory.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
        
        logger.info(f"RegimeDetectorFactory initialized with config: {self.config_path}")
    
    @classmethod
    def get_instance(cls, config_path: str = "config/ml_models.yaml") -> "RegimeDetectorFactory":
        """
        Get singleton instance of the factory.
        
        Args:
            config_path: Path to configuration (only used on first call)
        
        Returns:
            Unique factory instance
        """
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for tests)."""
        cls._instance = None
        cls._active_detector = None
    
    def _load_config(self) -> None:
        """Load configuration from YAML."""
        if not self.config_path.exists():
            logger.warning(f"Config not found at {self.config_path}, using defaults")
            self._config = self._get_default_config()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "regime_detector": {
                "active": "rules",  # Safe default
                "models_dir": "models",
                "models": {
                    "hmm": {
                        "n_states": 4,
                        "n_iter": 100,
                        "covariance_type": "full",
                        "features": ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
                    },
                    "rules": {
                        "volatile_vol_threshold": 0.25,
                        "bull_return_threshold": 0.02,
                        "bear_return_threshold": -0.02
                    }
                }
            }
        }
    
    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._load_config()
        # Invalidate cached detector
        RegimeDetectorFactory._active_detector = None
        logger.info("Configuration reloaded, cached detector invalidated")
    
    def get_regime_config(self) -> Dict[str, Any]:
        """Get regime_detector configuration."""
        return self._config.get("regime_detector", {})
    
    def get_active_model_type(self) -> str:
        """Return the active model type based on config."""
        return self.get_regime_config().get("active", "rules")
    
    def get_available_models(self) -> list:
        """List available model types."""
        return list(MODEL_REGISTRY.keys())
    
    def get_models_dir(self) -> Path:
        """Get models directory."""
        models_dir = self.get_regime_config().get("models_dir", "models")
        return Path(models_dir)
    
    def create_regime_detector(
        self,
        model_type: Optional[str] = None,
        load_trained: bool = True
    ) -> RegimeDetector:
        """
        Create a regime detector.
        
        Args:
            model_type: Model type. If None, uses active from config.
            load_trained: If True, attempts to load trained model.
        
        Returns:
            RegimeDetector instance
        
        Raises:
            ConfigurationError: If unknown type or invalid config
        """
        if model_type is None:
            model_type = self.get_active_model_type()
        
        model_type = model_type.lower()
        
        if model_type not in MODEL_REGISTRY:
            available = ", ".join(MODEL_REGISTRY.keys())
            raise ConfigurationError(
                f"Unknown model type: '{model_type}'. "
                f"Available: {available}"
            )
        
        logger.info(f"Creating detector of type: {model_type}")
        
        # Get specific model config
        model_config = self.get_regime_config().get("models", {}).get(model_type, {})
        
        if model_type == "hmm":
            return self._create_hmm_detector(model_config, load_trained)
        elif model_type == "rules":
            return self._create_rules_detector(model_config)
        else:
            # Extensibility for future models
            raise ConfigurationError(f"Creation of '{model_type}' not implemented")
    
    def _create_hmm_detector(
        self,
        config: Dict[str, Any],
        load_trained: bool
    ) -> HMMRegimeDetector:
        """Create HMM detector."""
        hmm_config = HMMConfig(
            n_states=config.get("n_states", 4),
            n_iter=config.get("n_iter", 100),
            covariance_type=config.get("covariance_type", "full"),
            features=config.get("features"),
            random_state=config.get("random_state", 42),
        )
        
        detector = HMMRegimeDetector(hmm_config)
        
        if load_trained:
            # Attempt to load trained model
            # Note: This assumes a specific structure/naming convention
            # Ideally, we should track the latest model version in a file or DB
            model_path = self.get_models_dir() / "hmm_regime" / "latest"
            
            if model_path.exists():
                try:
                    detector = HMMRegimeDetector.load(str(model_path))
                    logger.info(f"HMM model loaded from {model_path}")
                except Exception as e:
                    logger.warning(f"Could not load HMM model: {e}")
            else:
                logger.warning(
                    f"No trained HMM model at {model_path}. "
                    "Returning untrained model."
                )
        
        return detector
    
    def _create_rules_detector(self, config: Dict[str, Any]) -> RulesBaselineDetector:
        """Create rules detector."""
        rules_config = RulesConfig(
            volatile_vol_threshold=config.get("volatile_vol_threshold", 0.25),
            bull_return_threshold=config.get("bull_return_threshold", 0.02),
            bear_return_threshold=config.get("bear_return_threshold", -0.02),
            # ... other parameters can be added here
        )
        
        return RulesBaselineDetector(rules_config)
    
    def get_active_detector(self) -> RegimeDetector:
        """
        Get the active detector (cached).
        
        Uses singleton pattern to avoid reloading the model
        on every call.
        
        Returns:
            Cached regime detector
        """
        if RegimeDetectorFactory._active_detector is None:
            RegimeDetectorFactory._active_detector = self.create_regime_detector()
        
        return RegimeDetectorFactory._active_detector
    
    def invalidate_cache(self) -> None:
        """Invalidate the cached detector."""
        RegimeDetectorFactory._active_detector = None
        logger.info("Detector cache invalidated")


# Convenience function to get detector
def get_regime_detector(
    config_path: str = "config/ml_models.yaml",
    model_type: Optional[str] = None
) -> RegimeDetector:
    """
    Convenience function to get a regime detector.
    
    Args:
        config_path: Path to configuration
        model_type: Specific type or None to use active
    
    Returns:
        Configured regime detector
    """
    factory = RegimeDetectorFactory.get_instance(config_path)
    
    if model_type:
        return factory.create_regime_detector(model_type)
    
    return factory.get_active_detector()
