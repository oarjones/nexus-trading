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
