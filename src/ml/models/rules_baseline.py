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
