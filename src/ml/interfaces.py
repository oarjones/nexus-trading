"""
Base interfaces for Machine Learning models.

Defines contracts that all implementations must follow,
ensuring interchangeability and consistency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import numpy as np
import json


class RegimeType(str, Enum):
    """
    Detectable market regime types.
    
    Based on: handoff_document section 4.2
    """
    BULL = "BULL"           # Bull market, clear uptrend
    BEAR = "BEAR"           # Bear market, clear downtrend
    SIDEWAYS = "SIDEWAYS"   # Sideways market, no trend
    VOLATILE = "VOLATILE"   # High volatility, uncertain regime
    UNKNOWN = "UNKNOWN"     # Undetermined (error or no data)
    
    @classmethod
    def from_string(cls, value: str) -> "RegimeType":
        """Convert string to RegimeType, with fallback to UNKNOWN."""
        try:
            return cls(value.upper())
        except ValueError:
            return cls.UNKNOWN


@dataclass(frozen=True)
class RegimePrediction:
    """
    Result of a market regime prediction.
    
    Immutable (frozen=True) for safety and hashability.
    JSON serializable for storage and APIs.
    
    Attributes:
        regime: Detected regime
        confidence: Prediction confidence (0.0 - 1.0)
        probabilities: Probabilities for each regime
        model_id: Identifier of the model used
        inference_time_ms: Inference time in milliseconds
        timestamp: Prediction timestamp
        features_used: Features used for prediction
        metadata: Additional model-specific information
    """
    regime: RegimeType
    confidence: float
    probabilities: Dict[str, float]
    model_id: str
    inference_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    features_used: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Post-initialization validations."""
        # Validate confidence range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, received: {self.confidence}")
        
        # Validate probabilities sum ~1.0
        prob_sum = sum(self.probabilities.values())
        if not 0.99 <= prob_sum <= 1.01:
            raise ValueError(f"probabilities must sum to ~1.0, sum: {prob_sum}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result['regime'] = self.regime.value
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegimePrediction":
        """Reconstruct from dictionary."""
        data = data.copy()
        data['regime'] = RegimeType.from_string(data['regime'])
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    @property
    def is_tradeable(self) -> bool:
        """
        Indicates if the regime allows trading.
        
        VOLATILE and UNKNOWN are not tradeable.
        """
        return self.regime in (RegimeType.BULL, RegimeType.BEAR, RegimeType.SIDEWAYS)
    
    @property
    def is_high_confidence(self) -> bool:
        """Indicates if confidence exceeds threshold (0.6)."""
        return self.confidence >= 0.6


@dataclass
class ModelMetrics:
    """
    Model performance metrics.
    
    Used for model comparison and performance tracking.
    """
    model_id: str
    version: str
    trained_at: Optional[datetime] = None
    train_samples: int = 0
    log_likelihood: Optional[float] = None  # For HMM
    aic: Optional[float] = None             # Akaike Information Criterion
    bic: Optional[float] = None             # Bayesian Information Criterion
    accuracy_validation: Optional[float] = None
    regime_distribution: Optional[Dict[str, float]] = None
    inference_time_avg_ms: float = 0.0
    last_prediction_at: Optional[datetime] = None
    predictions_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.trained_at:
            result['trained_at'] = self.trained_at.isoformat()
        if self.last_prediction_at:
            result['last_prediction_at'] = self.last_prediction_at.isoformat()
        return result


class RegimeDetector(ABC):
    """
    Abstract interface for market regime detectors.
    
    All implementations (HMM, Rules, PPO, etc.) MUST
    inherit from this class and implement all abstract methods.
    
    Usage example:
        detector = HMMRegimeDetector(config)
        detector.fit(training_data)
        prediction = detector.predict(current_features)
        detector.save("models/hmm_regime/v1")
    """
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Unique model identifier.
        
        Recommended format: "{type}_{version}_{hash_config}"
        Example: "hmm_v1_abc123"
        """
        pass
    
    @property
    @abstractmethod
    def is_fitted(self) -> bool:
        """Indicates if the model has been trained/configured."""
        pass
    
    @property
    @abstractmethod
    def required_features(self) -> List[str]:
        """
        List of features required for prediction.
        
        Example: ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
        """
        pass
    
    @abstractmethod
    def fit(
        self, 
        X: np.ndarray, 
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "RegimeDetector":
        """
        Train the model with historical data.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Optional labels (for supervised models)
            feature_names: Names of feature columns
        
        Returns:
            self (for chaining)
        
        Raises:
            ValueError: If invalid data
            RuntimeError: If training fails
        """
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> RegimePrediction:
        """
        Predict current regime given a feature vector.
        
        Args:
            X: Feature vector (1, n_features) or (n_features,)
        
        Returns:
            RegimePrediction with regime and metadata
        
        Raises:
            ValueError: If invalid features
            RuntimeError: If model not fitted
        """
        pass
    
    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> Dict[str, float]:
        """
        Get probabilities for each regime.
        
        Args:
            X: Feature vector
        
        Returns:
            Dict with probability for each RegimeType
        """
        pass
    
    @abstractmethod
    def save(self, path: str) -> None:
        """
        Persist model and configuration.
        
        Args:
            path: Directory to save to (subdirectories created)
        
        Files created:
            - model.pkl: Serialized model
            - config.yaml: Configuration used
            - metrics.json: Training metrics
        """
        pass
    
    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "RegimeDetector":
        """
        Load a previously saved model.
        
        Args:
            path: Directory with model files
        
        Returns:
            Loaded detector instance
        
        Raises:
            FileNotFoundError: If path does not exist
            ValueError: If corrupt or incompatible files
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> ModelMetrics:
        """
        Get model metrics.
        
        Returns:
            ModelMetrics with performance info
        """
        pass
    
    def validate_features(self, X: np.ndarray) -> bool:
        """
        Validate input format.
        
        Args:
            X: Feature array
        
        Returns:
            True if valid
        
        Raises:
            ValueError: With description of the problem
        """
        if X is None:
            raise ValueError("Features cannot be None")
        
        if not isinstance(X, np.ndarray):
            raise ValueError(f"Features must be np.ndarray, received: {type(X)}")
        
        # Reshape if 1D
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] != len(self.required_features):
            raise ValueError(
                f"Expected {len(self.required_features)} features, "
                f"received: {X.shape[1]}"
            )
        
        if np.isnan(X).any():
            raise ValueError("Features contain NaN")
        
        if np.isinf(X).any():
            raise ValueError("Features contain Inf")
        
        return True


class ModelFactory(ABC):
    """
    Abstract factory for creating regime detectors.
    
    Concrete implementations read configuration and create
    the appropriate model.
    """
    
    @abstractmethod
    def create_regime_detector(
        self, 
        model_type: Optional[str] = None
    ) -> RegimeDetector:
        """
        Create a regime detector based on configuration.
        
        Args:
            model_type: Model type ("hmm", "rules", etc.)
                       If None, uses active model in config
        
        Returns:
            RegimeDetector instance
        
        Raises:
            ValueError: If unknown type
            RuntimeError: If creation fails
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """List available model types."""
        pass
    
    @abstractmethod
    def get_active_model_type(self) -> str:
        """Return active model type from config."""
        pass
