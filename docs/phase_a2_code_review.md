# Phase A2 Code Review

Consolidated source code for Phase A2 components.

## src/ml/interfaces.py

```py
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

```

## src/ml/exceptions.py

```py
"""
Specific exceptions for the ML module.

Allows granular error handling across different layers.
"""


class MLError(Exception):
    """Base exception for ML errors."""
    pass


class ModelNotFittedError(MLError):
    """The model has not been trained yet."""
    pass


class InvalidFeaturesError(MLError):
    """Invalid input features."""
    pass


class ModelLoadError(MLError):
    """Error loading model from disk."""
    pass


class ModelSaveError(MLError):
    """Error saving model to disk."""
    pass


class TrainingError(MLError):
    """Error during training."""
    pass


class ConfigurationError(MLError):
    """Model configuration error."""
    pass


class InferenceError(MLError):
    """Error during inference/prediction."""
    pass

```

## src/ml/models/hmm_regime.py

```py
"""
Market regime detector using Hidden Markov Models.

Implement the RegimeDetector interface using hmmlearn.GaussianHMM
to detect 4 market states: BULL, BEAR, SIDEWAYS, VOLATILE.
"""

import logging
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import joblib
import yaml
from hmmlearn import hmm

from ..interfaces import (
    RegimeDetector,
    RegimePrediction,
    RegimeType,
    ModelMetrics,
)
from ..exceptions import (
    ModelNotFittedError,
    InvalidFeaturesError,
    ModelLoadError,
    ModelSaveError,
    TrainingError,
)

logger = logging.getLogger(__name__)


@dataclass
class HMMConfig:
    """
    Configuration for the HMM model.
    
    Attributes:
        n_states: Number of hidden states (default: 4)
        n_iter: Maximum EM iterations
        covariance_type: Type of covariance matrix
        features: List of features to use
        random_state: Seed for reproducibility
        tol: Convergence tolerance
        min_covar: Minimum covariance (avoids singularity)
    """
    n_states: int = 4
    n_iter: int = 100
    covariance_type: str = "full"  # "full", "diag", "tied", "spherical"
    features: List[str] = None
    random_state: int = 42
    tol: float = 1e-4
    min_covar: float = 1e-3
    
    def __post_init__(self):
        if self.features is None:
            self.features = [
                "returns_5d",
                "volatility_20d",
                "adx_14",
                "volume_ratio"
            ]
        
        # Validations
        if self.n_states < 2:
            raise ValueError("n_states must be >= 2")
        if self.n_iter < 10:
            raise ValueError("n_iter must be >= 10")
        if self.covariance_type not in ["full", "diag", "tied", "spherical"]:
            raise ValueError(f"Invalid covariance_type: {self.covariance_type}")
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HMMConfig":
        return cls(**data)
    
    def config_hash(self) -> str:
        """Short hash of config for versioning."""
        content = str(sorted(self.to_dict().items()))
        return hashlib.md5(content.encode()).hexdigest()[:6]


class HMMRegimeDetector(RegimeDetector):
    """
    Market regime detector based on Hidden Markov Model.
    
    Uses hmmlearn.GaussianHMM to model hidden market states
    based on observable technical features.
    
    Example:
        config = HMMConfig(n_states=4, features=["returns_5d", "volatility_20d"])
        detector = HMMRegimeDetector(config)
        
        # Train
        detector.fit(X_train, feature_names=["returns_5d", "volatility_20d"])
        
        # Predict
        prediction = detector.predict(X_current)
        print(f"Regime: {prediction.regime}, Confidence: {prediction.confidence}")
    """
    
    # State index to RegimeType mapping
    # Adjusted after training based on characteristics
    DEFAULT_STATE_MAPPING = {
        0: RegimeType.BULL,
        1: RegimeType.BEAR,
        2: RegimeType.SIDEWAYS,
        3: RegimeType.VOLATILE,
    }
    
    def __init__(self, config: Optional[HMMConfig] = None):
        """
        Initialize HMM detector.
        
        Args:
            config: Model configuration. If None, uses defaults.
        """
        self.config = config or HMMConfig()
        self._model: Optional[hmm.GaussianHMM] = None
        self._state_mapping: Dict[int, RegimeType] = {}
        self._is_fitted: bool = False
        self._version: str = "v0"
        self._trained_at: Optional[datetime] = None
        self._train_metrics: Dict[str, Any] = {}
        self._feature_means: Optional[np.ndarray] = None
        self._feature_stds: Optional[np.ndarray] = None
        self._predictions_count: int = 0
        self._inference_times: List[float] = []
        
        logger.info(f"HMMRegimeDetector initialized with config: {self.config.to_dict()}")
    
    @property
    def model_id(self) -> str:
        """Unique model identifier."""
        return f"hmm_{self._version}_{self.config.config_hash()}"
    
    @property
    def is_fitted(self) -> bool:
        """Indicates if model is trained."""
        return self._is_fitted and self._model is not None
    
    @property
    def required_features(self) -> List[str]:
        """List of required features."""
        return self.config.features.copy()
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "HMMRegimeDetector":
        """
        Train HMM model with historical data.
        
        Uses Expectation-Maximization (EM) algorithm to learn HMM parameters:
        - Transition matrix
        - Emission means and covariances
        - Start probabilities
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Ignored (HMM is unsupervised)
            feature_names: Feature names for logging
        
        Returns:
            self for chaining
        
        Raises:
            TrainingError: If training fails
            InvalidFeaturesError: If data is invalid
        """
        logger.info(f"Starting HMM training with {len(X)} samples")
        start_time = time.time()
        
        try:
            # Validate input
            X = self._validate_and_prepare_input(X)
            
            # Normalize features (important for HMM)
            X_normalized, self._feature_means, self._feature_stds = self._normalize_features(X)
            
            logger.info(f"Features normalized. Shape: {X_normalized.shape}")
            
            # Create HMM model
            self._model = hmm.GaussianHMM(
                n_components=self.config.n_states,
                covariance_type=self.config.covariance_type,
                n_iter=self.config.n_iter,
                random_state=self.config.random_state,
                tol=self.config.tol,
                verbose=False,
                init_params="stmc",  # Initialize startprob, transmat, means, covars
            )
            
            # Set min covariance
            self._model.min_covar = self.config.min_covar
            
            # Train
            logger.info("Running EM algorithm...")
            self._model.fit(X_normalized)
            
            # Check convergence
            if not self._model.monitor_.converged:
                logger.warning(
                    f"HMM did not converge in {self.config.n_iter} iterations. "
                    f"Consider increasing n_iter."
                )
            
            # Map states to regimes based on learned characteristics
            self._state_mapping = self._infer_state_mapping(X_normalized)
            
            # Calculate training metrics
            self._calculate_train_metrics(X_normalized)
            
            # Mark as fitted
            self._is_fitted = True
            self._trained_at = datetime.now()
            self._version = f"v1_{self._trained_at.strftime('%Y%m%d')}"
            
            elapsed = time.time() - start_time
            logger.info(
                f"Training completed in {elapsed:.2f}s. "
                f"Log-likelihood: {self._train_metrics.get('log_likelihood', 'N/A')}"
            )
            
            return self
            
        except Exception as e:
            logger.error(f"Error in HMM training: {e}")
            raise TrainingError(f"HMM training failed: {e}") from e
    
    def _validate_and_prepare_input(self, X: np.ndarray) -> np.ndarray:
        """Validate and prepare input for training/prediction."""
        if X is None:
            raise InvalidFeaturesError("Input X cannot be None")
        
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] != len(self.config.features):
            raise InvalidFeaturesError(
                f"Expected {len(self.config.features)} features, "
                f"received: {X.shape[1]}"
            )
        
        # Check NaN/Inf
        if np.isnan(X).any():
            nan_count = np.isnan(X).sum()
            raise InvalidFeaturesError(f"Input contains {nan_count} NaN values")
        
        if np.isinf(X).any():
            inf_count = np.isinf(X).sum()
            raise InvalidFeaturesError(f"Input contains {inf_count} Inf values")
        
        return X
    
    def _normalize_features(
        self,
        X: np.ndarray,
        fit: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Normalize features using z-score.
        
        Args:
            X: Features to normalize
            fit: If True, calculate mean/std. If False, use existing.
        
        Returns:
            Tuple of (X_normalized, means, stds)
        """
        if fit:
            means = X.mean(axis=0)
            stds = X.std(axis=0)
            # Avoid division by zero
            stds = np.where(stds < 1e-8, 1.0, stds)
        else:
            if self._feature_means is None or self._feature_stds is None:
                raise ModelNotFittedError("Model not trained, no normalization parameters")
            means = self._feature_means
            stds = self._feature_stds
        
        X_normalized = (X - means) / stds
        return X_normalized, means, stds
    
    def _infer_state_mapping(self, X_normalized: np.ndarray) -> Dict[int, RegimeType]:
        """
        Infer state index to RegimeType mapping.
        
        Analyzes state characteristics (feature means) to assign
        the most appropriate regime.
        
        Logic:
        - BULL: High return, low volatility
        - BEAR: Low return, high volatility
        - SIDEWAYS: Return near zero, low volatility
        - VOLATILE: High volatility regardless of return
        """
        state_mapping = {}
        
        # Get state predictions for all data
        states = self._model.predict(X_normalized)
        
        # Calculate average characteristics per state
        state_characteristics = {}
        for state_idx in range(self.config.n_states):
            mask = states == state_idx
            if mask.sum() == 0:
                continue
            
            state_data = X_normalized[mask]
            state_characteristics[state_idx] = {
                'mean_returns': state_data[:, 0].mean() if 'returns' in self.config.features[0] else 0,
                'mean_volatility': state_data[:, 1].mean() if len(self.config.features) > 1 else 0,
                'count': mask.sum(),
                'proportion': mask.sum() / len(states)
            }
        
        logger.info(f"State characteristics: {state_characteristics}")
        
        # Assign regimes based on characteristics
        # Sort states by volatility (typically index 1)
        states_by_vol = sorted(
            state_characteristics.keys(),
            key=lambda s: state_characteristics[s].get('mean_volatility', 0)
        )
        
        # State with highest volatility is VOLATILE
        if len(states_by_vol) >= 1:
            state_mapping[states_by_vol[-1]] = RegimeType.VOLATILE
        
        # Of the remaining, classify by return
        remaining = [s for s in states_by_vol[:-1]] if len(states_by_vol) > 1 else []
        
        if remaining:
            # Sort by return
            states_by_return = sorted(
                remaining,
                key=lambda s: state_characteristics[s].get('mean_returns', 0)
            )
            
            # Highest return = BULL
            state_mapping[states_by_return[-1]] = RegimeType.BULL
            
            # Lowest return = BEAR
            if len(states_by_return) > 1:
                state_mapping[states_by_return[0]] = RegimeType.BEAR
            
            # Intermediate = SIDEWAYS
            if len(states_by_return) > 2:
                for s in states_by_return[1:-1]:
                    state_mapping[s] = RegimeType.SIDEWAYS
        
        # Fill unassigned states with default
        for i in range(self.config.n_states):
            if i not in state_mapping:
                state_mapping[i] = self.DEFAULT_STATE_MAPPING.get(i, RegimeType.UNKNOWN)
        
        logger.info(f"Inferred state mapping: {state_mapping}")
        return state_mapping
    
    def _calculate_train_metrics(self, X_normalized: np.ndarray) -> None:
        """Calculate training metrics."""
        self._train_metrics = {
            'n_samples': len(X_normalized),
            'n_features': X_normalized.shape[1],
            'n_states': self.config.n_states,
            'converged': self._model.monitor_.converged,
            'n_iter_actual': self._model.monitor_.iter,
            'log_likelihood': float(self._model.score(X_normalized)),
        }
        
        # AIC and BIC
        n_params = self._count_parameters()
        n_samples = len(X_normalized)
        log_likelihood = self._train_metrics['log_likelihood']
        
        self._train_metrics['aic'] = 2 * n_params - 2 * log_likelihood
        self._train_metrics['bic'] = n_params * np.log(n_samples) - 2 * log_likelihood
        
        # State distribution
        states = self._model.predict(X_normalized)
        state_counts = np.bincount(states, minlength=self.config.n_states)
        state_dist = {
            self._state_mapping.get(i, RegimeType.UNKNOWN).value: int(count)
            for i, count in enumerate(state_counts)
        }
        self._train_metrics['state_distribution'] = state_dist
        
        logger.info(f"Training metrics: {self._train_metrics}")
    
    def _count_parameters(self) -> int:
        """Count number of free parameters in the model."""
        n_states = self.config.n_states
        n_features = len(self.config.features)
        
        # Start probabilities: n_states - 1 (sum to 1)
        n_params = n_states - 1
        
        # Transition matrix: n_states * (n_states - 1)
        n_params += n_states * (n_states - 1)
        
        # Emission means: n_states * n_features
        n_params += n_states * n_features
        
        # Covariances depending on type
        if self.config.covariance_type == "full":
            n_params += n_states * n_features * (n_features + 1) // 2
        elif self.config.covariance_type == "diag":
            n_params += n_states * n_features
        elif self.config.covariance_type == "tied":
            n_params += n_features * (n_features + 1) // 2
        elif self.config.covariance_type == "spherical":
            n_params += n_states
        
        return n_params
    
    def predict(self, X: np.ndarray) -> RegimePrediction:
        """
        Predict current regime given a feature vector.
        
        Args:
            X: Feature vector (1, n_features) or (n_features,)
        
        Returns:
            RegimePrediction with detected regime and metadata
        
        Raises:
            ModelNotFittedError: If model not trained
            InvalidFeaturesError: If features invalid
        """
        if not self.is_fitted:
            raise ModelNotFittedError("HMM model has not been trained")
        
        start_time = time.time()
        
        try:
            # Validate and prepare input
            X = self._validate_and_prepare_input(X)
            # Normalize using training parameters
            X_normalized, _, _ = self._normalize_features(X, fit=False)
            
            # Get probabilities
            # hmmlearn 0.3.3 returns (log_prob, posteriors) from score_samples
            log_prob, _ = self._model.score_samples(X_normalized)
            posteriors = self._model.predict_proba(X_normalized)
            
            # Take last observation if multiple
            if len(posteriors) > 1:
                posteriors = posteriors[-1:]
            
            posterior = posteriors[0]
            
            # Most likely state
            state_idx = np.argmax(posterior)
            regime = self._state_mapping.get(state_idx, RegimeType.UNKNOWN)
            confidence = float(posterior[state_idx])
            
            # Build probabilities dictionary
            probabilities = {
                self._state_mapping.get(i, RegimeType.UNKNOWN).value: float(p)
                for i, p in enumerate(posterior)
            }
            
            inference_time = (time.time() - start_time) * 1000  # ms
            self._inference_times.append(inference_time)
            self._predictions_count += 1
            
            features_used = {
                name: float(X[0, i].item())
                for i, name in enumerate(self.config.features)
            }
            
            prediction = RegimePrediction(
                regime=regime,
                confidence=confidence,
                probabilities=probabilities,
                model_id=self.model_id,
                inference_time_ms=inference_time,
                features_used=features_used,
                metadata={
                    'state_index': int(state_idx),
                    'log_likelihood': float(log_prob),
                }
            )
            
            logger.debug(
                f"Prediction: {regime.value} (confidence: {confidence:.2%}, "
                f"time: {inference_time:.1f}ms)"
            )
            
            return prediction
            
        except (ModelNotFittedError, InvalidFeaturesError):
            raise
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            raise InvalidFeaturesError(f"Error in prediction: {e}") from e
    
    def predict_proba(self, X: np.ndarray) -> Dict[str, float]:
        """
        Get probabilities for each regime.
        
        Args:
            X: Feature vector
        
        Returns:
            Dict with probability for each RegimeType
        """
        prediction = self.predict(X)
        return prediction.probabilities
    
    def predict_sequence(
        self,
        X: np.ndarray,
        return_proba: bool = False
    ) -> Tuple[List[RegimeType], Optional[np.ndarray]]:
        """
        Predict regime sequence for multiple observations.
        
        Uses Viterbi algorithm to find optimal state sequence.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            return_proba: If True, also return probabilities
        
        Returns:
            Tuple of (list of regimes, optional probabilities)
        """
        if not self.is_fitted:
            raise ModelNotFittedError("HMM model has not been trained")
        
        X = self._validate_and_prepare_input(X)
        X_normalized, _, _ = self._normalize_features(X, fit=False)
        
        # Viterbi for optimal sequence
        _, states = self._model.decode(X_normalized, algorithm="viterbi")
        
        regimes = [self._state_mapping.get(s, RegimeType.UNKNOWN) for s in states]
        
        if return_proba:
            proba = self._model.predict_proba(X_normalized)
            return regimes, proba
        
        return regimes, None
    
    def get_transition_matrix(self) -> pd.DataFrame:
        """
        Get state transition matrix.
        
        Returns:
            DataFrame with transition probabilities
        """
        if not self.is_fitted:
            raise ModelNotFittedError("Model not trained")
        
        labels = [
            self._state_mapping.get(i, RegimeType.UNKNOWN).value
            for i in range(self.config.n_states)
        ]
        
        return pd.DataFrame(
            self._model.transmat_,
            index=labels,
            columns=labels
        )
    
    def save(self, path: str) -> None:
        """
        Save model and configuration.
        
        Args:
            path: Base directory to save to
        
        Structure created:
            {path}/
            ├── model.pkl       # Serialized model
            ├── config.yaml     # Configuration
            ├── metrics.json    # Training metrics
            └── normalization.npz  # Normalization parameters
        """
        if not self.is_fitted:
            raise ModelNotFittedError("Cannot save untrained model")
        
        try:
            path = Path(path)
            path.mkdir(parents=True, exist_ok=True)
            
            # Save model
            model_path = path / "model.pkl"
            joblib.dump(self._model, model_path)
            logger.info(f"Model saved to {model_path}")
            
            # Save config
            config_path = path / "config.yaml"
            config_data = {
                'hmm_config': self.config.to_dict(),
                'version': self._version,
                'trained_at': self._trained_at.isoformat() if self._trained_at else None,
                'state_mapping': {
                    k: v.value for k, v in self._state_mapping.items()
                },
            }
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            logger.info(f"Config saved to {config_path}")
            
            # Save metrics
            metrics_path = path / "metrics.json"
            import json
            with open(metrics_path, 'w') as f:
                json.dump(self._train_metrics, f, indent=2)
            logger.info(f"Metrics saved to {metrics_path}")
            
            # Save normalization parameters
            norm_path = path / "normalization.npz"
            np.savez(
                norm_path,
                means=self._feature_means,
                stds=self._feature_stds
            )
            logger.info(f"Normalization saved to {norm_path}")
            
            logger.info(f"Complete model saved to {path}")
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise ModelSaveError(f"Error saving model: {e}") from e
    
    @classmethod
    def load(cls, path: str) -> "HMMRegimeDetector":
        """
        Load a previously saved model.
        
        Args:
            path: Directory with model files
        
        Returns:
            Loaded detector instance
        """
        try:
            path = Path(path)
            
            if not path.exists():
                raise ModelLoadError(f"Path does not exist: {path}")
            
            # Load config
            config_path = path / "config.yaml"
            if not config_path.exists():
                raise ModelLoadError(f"config.yaml not found in {path}")
            
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Create instance with config
            hmm_config = HMMConfig.from_dict(config_data['hmm_config'])
            detector = cls(hmm_config)
            
            # Load model
            model_path = path / "model.pkl"
            if not model_path.exists():
                raise ModelLoadError(f"model.pkl not found in {path}")
            
            detector._model = joblib.load(model_path)
            
            # Load state mapping
            detector._state_mapping = {
                int(k): RegimeType.from_string(v)
                for k, v in config_data.get('state_mapping', {}).items()
            }
            
            # Load metadata
            detector._version = config_data.get('version', 'v0')
            if config_data.get('trained_at'):
                detector._trained_at = datetime.fromisoformat(config_data['trained_at'])
            
            # Load metrics if exist
            metrics_path = path / "metrics.json"
            if metrics_path.exists():
                import json
                with open(metrics_path, 'r') as f:
                    detector._train_metrics = json.load(f)
            
            # Load normalization
            norm_path = path / "normalization.npz"
            if norm_path.exists():
                norm_data = np.load(norm_path)
                detector._feature_means = norm_data['means']
                detector._feature_stds = norm_data['stds']
            
            detector._is_fitted = True
            
            logger.info(f"Model loaded from {path}: {detector.model_id}")
            return detector
            
        except ModelLoadError:
            raise
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise ModelLoadError(f"Error loading model: {e}") from e
    
    def get_metrics(self) -> ModelMetrics:
        """Get model metrics."""
        return ModelMetrics(
            model_id=self.model_id,
            version=self._version,
            trained_at=self._trained_at,
            train_samples=self._train_metrics.get('n_samples', 0),
            log_likelihood=self._train_metrics.get('log_likelihood'),
            aic=self._train_metrics.get('aic'),
            bic=self._train_metrics.get('bic'),
            regime_distribution=self._train_metrics.get('state_distribution'),
            inference_time_avg_ms=np.mean(self._inference_times) if self._inference_times else 0.0,
            predictions_count=self._predictions_count,
            last_prediction_at=datetime.now() if self._predictions_count > 0 else None,
        )

```

## src/ml/models/rules_baseline.py

```py
"""
Regime detector based on simple rules.

Serves as a baseline to compare with more complex ML models.
Does not require training, is completely interpretable.
"""

import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

import numpy as np

from ..interfaces import (
    RegimeDetector,
    RegimePrediction,
    RegimeType,
    ModelMetrics,
)
from ..exceptions import InvalidFeaturesError

logger = logging.getLogger(__name__)


@dataclass
class RulesConfig:
    """
    Configuration for the rules-based detector.
    
    Defines thresholds for each regime.
    """
    # Expected features (order matters)
    features: List[str] = None
    
    # Thresholds for VOLATILE
    volatile_vol_threshold: float = 0.25
    volatile_adx_threshold: float = 40
    volatile_vol_with_adx: float = 0.20
    
    # Thresholds for BULL
    bull_return_threshold: float = 0.02
    bull_max_vol: float = 0.20
    bull_min_adx: float = 20
    
    # Thresholds for BEAR
    bear_return_threshold: float = -0.02
    bear_max_vol: float = 0.30
    bear_min_adx: float = 20
    
    # Thresholds for SIDEWAYS
    sideways_return_range: float = 0.02
    sideways_max_vol: float = 0.20
    sideways_max_adx: float = 25
    
    def __post_init__(self):
        if self.features is None:
            self.features = [
                "returns_5d",
                "volatility_20d",
                "adx_14",
                "volume_ratio"
            ]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RulesConfig":
        return cls(**data)


class RulesBaselineDetector(RegimeDetector):
    """
    Regime detector based on deterministic rules.
    
    This model does not learn from data, but applies predefined rules
    based on domain knowledge.
    
    Advantages:
    - No training required
    - Completely interpretable
    - Serves as baseline for comparing ML models
    - Fast inference
    
    Example:
        detector = RulesBaselineDetector()
        prediction = detector.predict(np.array([[0.03, 0.15, 28, 1.1]]))
        # Result: BULL with high confidence
    """
    
    VERSION = "v1_static"
    
    def __init__(self, config: Optional[RulesConfig] = None):
        """
        Initialize rules detector.
        
        Args:
            config: Configuration with thresholds. If None, uses defaults.
        """
        self.config = config or RulesConfig()
        self._predictions_count: int = 0
        self._inference_times: List[float] = []
        self._regime_counts: Dict[str, int] = {r.value: 0 for r in RegimeType}
        
        logger.info(f"RulesBaselineDetector initialized with config: {self.config.to_dict()}")
    
    @property
    def model_id(self) -> str:
        return f"rules_baseline_{self.VERSION}"
    
    @property
    def is_fitted(self) -> bool:
        # Rules do not need training
        return True
    
    @property
    def required_features(self) -> List[str]:
        return self.config.features.copy()
    
    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> "RulesBaselineDetector":
        """
        No-op for rules. Maintains compatible interface.
        
        Optionally can be used to calculate reference statistics
        of the data.
        """
        logger.info("RulesBaselineDetector.fit() - No training required")
        return self
    
    def predict(self, X: np.ndarray) -> RegimePrediction:
        """
        Predict regime using deterministic rules.
        
        Args:
            X: Feature vector [returns_5d, volatility_20d, adx_14, volume_ratio]
        
        Returns:
            RegimePrediction with regime and confidence
        """
        start_time = time.time()
        
        # Validate input
        X = self._validate_input(X)
        
        # Extract features (last row if multiple)
        if X.ndim == 2:
            features = X[-1]
        else:
            features = X
        
        returns_5d = features[0]
        volatility_20d = features[1]
        adx_14 = features[2]
        volume_ratio = features[3] if len(features) > 3 else 1.0
        
        # Apply rules
        regime, confidence, reasoning = self._apply_rules(
            returns_5d, volatility_20d, adx_14, volume_ratio
        )
        
        # Calculate pseudo-probabilities
        probabilities = self._calculate_probabilities(
            regime, confidence, returns_5d, volatility_20d, adx_14
        )
        
        inference_time = (time.time() - start_time) * 1000
        self._inference_times.append(inference_time)
        self._predictions_count += 1
        self._regime_counts[regime.value] += 1
        
        prediction = RegimePrediction(
            regime=regime,
            confidence=confidence,
            probabilities=probabilities,
            model_id=self.model_id,
            inference_time_ms=inference_time,
            features_used={
                "returns_5d": float(returns_5d),
                "volatility_20d": float(volatility_20d),
                "adx_14": float(adx_14),
                "volume_ratio": float(volume_ratio),
            },
            metadata={
                "reasoning": reasoning,
                "rules_version": self.VERSION,
            }
        )
        
        logger.debug(
            f"Rules Prediction: {regime.value} ({confidence:.0%}) - {reasoning}"
        )
        
        return prediction
    
    def _validate_input(self, X: np.ndarray) -> np.ndarray:
        """Validate input."""
        if X is None:
            raise InvalidFeaturesError("Input X cannot be None")
        
        if not isinstance(X, np.ndarray):
            X = np.array(X)
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] < 3:
            raise InvalidFeaturesError(
                f"Expected at least 3 features (returns, vol, adx), "
                f"received: {X.shape[1]}"
            )
        
        return X
    
    def _apply_rules(
        self,
        ret: float,
        vol: float,
        adx: float,
        volume: float
    ) -> Tuple[RegimeType, float, str]:
        """Apply decision rules."""
        c = self.config
        
        # 1. Check VOLATILE (Highest priority)
        if vol > c.volatile_vol_threshold:
            return RegimeType.VOLATILE, 0.8, f"High volatility ({vol:.2f} > {c.volatile_vol_threshold})"
        
        if adx > c.volatile_adx_threshold and vol > c.volatile_vol_with_adx:
            return RegimeType.VOLATILE, 0.7, f"High ADX ({adx:.1f}) with elevated vol ({vol:.2f})"
        
        # 2. Check BULL
        if ret > c.bull_return_threshold and vol < c.bull_max_vol and adx > c.bull_min_adx:
            return RegimeType.BULL, 0.8, f"Strong uptrend (ret={ret:.2%}, adx={adx:.1f})"
        
        # 3. Check BEAR
        if ret < c.bear_return_threshold and vol < c.bear_max_vol and adx > c.bear_min_adx:
            return RegimeType.BEAR, 0.8, f"Strong downtrend (ret={ret:.2%}, adx={adx:.1f})"
        
        # 4. Check SIDEWAYS
        if abs(ret) <= c.sideways_return_range and vol < c.sideways_max_vol and adx < c.sideways_max_adx:
            return RegimeType.SIDEWAYS, 0.7, f"Flat market (ret={ret:.2%}, low vol/adx)"
        
        # Default / Weak signals
        if ret > 0:
            return RegimeType.BULL, 0.4, "Weak uptrend signal (default)"
        elif ret < 0:
            return RegimeType.BEAR, 0.4, "Weak downtrend signal (default)"
        else:
            return RegimeType.SIDEWAYS, 0.4, "Indeterminate (default)"
    
    def _calculate_probabilities(
        self,
        regime: RegimeType,
        confidence: float,
        ret: float,
        vol: float,
        adx: float
    ) -> Dict[str, float]:
        """Calculate pseudo-probabilities based on confidence."""
        probs = {r.value: 0.0 for r in RegimeType}
        
        # Assign confidence to detected regime
        probs[regime.value] = confidence
        
        # Distribute remaining probability
        remaining = 1.0 - confidence
        others_count = len(RegimeType) - 1
        
        # Heuristic distribution
        if regime == RegimeType.BULL:
            # If BULL, remaining goes mostly to SIDEWAYS, little to BEAR
            probs[RegimeType.SIDEWAYS.value] = remaining * 0.6
            probs[RegimeType.VOLATILE.value] = remaining * 0.3
            probs[RegimeType.BEAR.value] = remaining * 0.1
        elif regime == RegimeType.BEAR:
            probs[RegimeType.SIDEWAYS.value] = remaining * 0.6
            probs[RegimeType.VOLATILE.value] = remaining * 0.3
            probs[RegimeType.BULL.value] = remaining * 0.1
        else:
            # Uniform distribution for others
            share = remaining / others_count
            for r in RegimeType:
                if r != regime:
                    probs[r.value] = share
        
        # Normalize to ensure sum=1.0
        total = sum(probs.values())
        return {k: v / total for k, v in probs.items()}
    
    def predict_proba(self, X: np.ndarray) -> Dict[str, float]:
        return self.predict(X).probabilities
    
    def save(self, path: str) -> None:
        """Rules are static, but we save config and metrics."""
        pass  # Implementation optional for baseline
    
    @classmethod
    def load(cls, path: str) -> "RulesBaselineDetector":
        return cls()
    
    def get_metrics(self) -> ModelMetrics:
        return ModelMetrics(
            model_id=self.model_id,
            version=self.VERSION,
            inference_time_avg_ms=np.mean(self._inference_times) if self._inference_times else 0.0,
            predictions_count=self._predictions_count,
            last_prediction_at=datetime.now() if self._predictions_count > 0 else None,
            regime_distribution=self._regime_counts
        )

```

## src/ml/factory.py

```py
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

```

## config/ml_models.yaml

```yaml
# config/ml_models.yaml
# Configuración de modelos de Machine Learning para Nexus Trading

# =============================================================================
# DETECTOR DE RÉGIMEN
# =============================================================================
regime_detector:
  # Modelo activo: "hmm" o "rules"
  # Cambiar este valor para usar diferente modelo
  active: "hmm"
  
  # Directorio donde se guardan los modelos entrenados
  models_dir: "models"
  
  # Configuración por tipo de modelo
  models:
    # -------------------------------------------------------------------------
    # Hidden Markov Model
    # -------------------------------------------------------------------------
    hmm:
      # Número de estados ocultos (regímenes)
      n_states: 4
      
      # Iteraciones máximas del algoritmo EM
      n_iter: 100
      
      # Tipo de matriz de covarianza: "full", "diag", "tied", "spherical"
      covariance_type: "full"
      
      # Features usados para detección
      features:
        - "returns_5d"
        - "volatility_20d"
        - "adx_14"
        - "volume_ratio"
      
      # Semilla para reproducibilidad
      random_state: 42
      
      # Tolerancia para convergencia
      tol: 0.0001
    
    # -------------------------------------------------------------------------
    # Baseline de Reglas
    # -------------------------------------------------------------------------
    rules:
      # Umbrales para régimen VOLATILE
      volatile_vol_threshold: 0.25
      volatile_adx_threshold: 40
      volatile_vol_with_adx: 0.20
      
      # Umbrales para régimen BULL
      bull_return_threshold: 0.02
      bull_max_vol: 0.20
      bull_min_adx: 20
      
      # Umbrales para régimen BEAR
      bear_return_threshold: -0.02
      bear_max_vol: 0.30
      bear_min_adx: 20
      
      # Umbrales para régimen SIDEWAYS
      sideways_return_range: 0.02
      sideways_max_vol: 0.20
      sideways_max_adx: 25

# =============================================================================
# CACHE DE PREDICCIONES
# =============================================================================
prediction_cache:
  enabled: true
  ttl_seconds: 300  # 5 minutos
  redis_key_prefix: "ml:regime"

# =============================================================================
# MONITOREO
# =============================================================================
monitoring:
  # Log de predicciones
  log_predictions: true
  
  # Métricas a Prometheus
  export_metrics: true
  
  # Alertas si confianza baja
  low_confidence_threshold: 0.5

```

## mcp_servers/ml_models/tools/regime.py

```py
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

```

## mcp_servers/ml_models/tools/model_info.py

```py
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

```

## mcp_servers/ml_models/server.py

```py
"""
MCP Server for Machine Learning Models.

Exposes tools for:
- get_regime: Get current market regime
- get_model_info: Get active model info
- list_models: List available models
- clear_cache: Clear prediction cache
"""

import asyncio
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tool imports
from tools.regime import handle_get_regime, get_regime_tool
from tools.model_info import handle_get_model_info, handle_list_models
from tools.health import handle_health_check


# MCP Tools Definition
TOOLS = [
    {
        "name": "get_regime",
        "description": "Get current market regime (BULL, BEAR, SIDEWAYS, VOLATILE)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "object",
                    "description": "Prediction features {name: value}. If not provided, uses current values.",
                    "additionalProperties": {"type": "number"}
                },
                "symbol": {
                    "type": "string",
                    "description": "Specific symbol (optional)"
                },
                "model_type": {
                    "type": "string",
                    "enum": ["hmm", "rules"],
                    "description": "Model type to use (optional, default: active)"
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to use prediction cache (default: true)"
                }
            }
        }
    },
    {
        "name": "get_model_info",
        "description": "Get information about active or specified ML model",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "enum": ["hmm", "rules"],
                    "description": "Model type (optional)"
                }
            }
        }
    },
    {
        "name": "list_models",
        "description": "List available ML models",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "clear_cache",
        "description": "Clear prediction cache",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "health_check",
        "description": "Check ML server status",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


async def handle_tool_call(name: str, args: dict) -> dict:
    """
    Dispatcher for tool calls.
    
    Args:
        name: Tool name
        args: Tool arguments
    
    Returns:
        Tool result
    """
    handlers = {
        "get_regime": handle_get_regime,
        "get_model_info": handle_get_model_info,
        "list_models": handle_list_models,
        "clear_cache": lambda _: {"cleared": get_regime_tool().clear_cache()},
        "health_check": handle_health_check,
    }
    
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    
    return await handler(args)


async def main():
    """MCP Server Entry Point."""
    logger.info("Starting mcp-ml-models server...")
    
    # In production, this would integrate with MCP SDK
    # For now, standalone test mode
    
    print(json.dumps({
        "status": "ready",
        "tools": [t["name"] for t in TOOLS],
        "version": "1.0.0"
    }))
    
    # Keep server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())

```

