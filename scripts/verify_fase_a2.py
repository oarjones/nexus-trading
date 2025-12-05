#!/usr/bin/env python
# scripts/verify_fase_a2.py
"""
Verification script for Phase A2: Modular ML.

Verifies that all components are correctly implemented.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from datetime import datetime


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_check(name: str, passed: bool, detail: str = "") -> None:
    status = "OK" if passed else "FAIL"
    # Simple output without colors for compatibility
    
    if detail:
        print(f"  [{status}] {name}: {detail}")
    else:
        print(f"  [{status}] {name}")


def verify_imports() -> bool:
    """Verify that all imports work."""
    print_header("VERIFYING IMPORTS")
    
    all_passed = True
    
    # Interfaces
    try:
        from src.ml import (
            RegimeType, RegimePrediction, ModelMetrics,
            RegimeDetector, ModelFactory
        )
        print_check("Interfaces", True)
    except Exception as e:
        print_check("Interfaces", False, str(e))
        all_passed = False
    
    # Exceptions
    try:
        from src.ml import (
            MLError, ModelNotFittedError, InvalidFeaturesError,
            ModelLoadError, TrainingError
        )
        print_check("Exceptions", True)
    except Exception as e:
        print_check("Exceptions", False, str(e))
        all_passed = False
    
    # Models
    try:
        from src.ml.models import HMMRegimeDetector, HMMConfig
        print_check("HMMRegimeDetector", True)
    except Exception as e:
        print_check("HMMRegimeDetector", False, str(e))
        all_passed = False
    
    try:
        from src.ml.models import RulesBaselineDetector, RulesConfig
        print_check("RulesBaselineDetector", True)
    except Exception as e:
        print_check("RulesBaselineDetector", False, str(e))
        all_passed = False
    
    # Factory
    try:
        from src.ml.factory import RegimeDetectorFactory, get_regime_detector
        print_check("Factory", True)
    except Exception as e:
        print_check("Factory", False, str(e))
        all_passed = False
    
    return all_passed


def verify_interfaces() -> bool:
    """Verify interfaces functionality."""
    print_header("VERIFYING INTERFACES")
    
    all_passed = True
    
    from src.ml import RegimeType, RegimePrediction
    
    # RegimeType
    try:
        assert RegimeType.BULL.value == "BULL"
        assert RegimeType.from_string("bear") == RegimeType.BEAR
        assert RegimeType.from_string("invalid") == RegimeType.UNKNOWN
        print_check("RegimeType enum", True)
    except Exception as e:
        print_check("RegimeType enum", False, str(e))
        all_passed = False
    
    # RegimePrediction
    try:
        pred = RegimePrediction(
            regime=RegimeType.BULL,
            confidence=0.85,
            probabilities={"BULL": 0.85, "BEAR": 0.05, "SIDEWAYS": 0.05, "VOLATILE": 0.05},
            model_id="test_v1",
            inference_time_ms=10.5
        )
        assert pred.is_high_confidence
        assert pred.is_tradeable
        
        # Serialization
        json_str = pred.to_json()
        # Simple check
        assert "BULL" in json_str
        
        print_check("RegimePrediction", True)
    except Exception as e:
        print_check("RegimePrediction", False, str(e))
        all_passed = False
    
    return all_passed


def verify_rules_baseline() -> bool:
    """Verify rules detector."""
    print_header("VERIFYING RULES BASELINE")
    
    all_passed = True
    
    from src.ml.models import RulesBaselineDetector
    from src.ml import RegimeType
    
    detector = RulesBaselineDetector()
    
    # Always fitted
    try:
        assert detector.is_fitted
        print_check("is_fitted = True", True)
    except Exception as e:
        print_check("is_fitted = True", False, str(e))
        all_passed = False
    
    # Predict BULL
    try:
        X_bull = np.array([[0.03, 0.15, 28, 1.1]])  # High return, low vol, ADX present
        pred = detector.predict(X_bull)
        
        assert pred.regime == RegimeType.BULL
        print_check("Detects BULL", True, f"confidence: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detects BULL", False, str(e))
        all_passed = False
    
    # Predict BEAR
    try:
        X_bear = np.array([[-0.03, 0.18, 30, 1.0]])  # Negative return
        pred = detector.predict(X_bear)
        
        assert pred.regime == RegimeType.BEAR
        print_check("Detects BEAR", True, f"confidence: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detects BEAR", False, str(e))
        all_passed = False
    
    # Predict VOLATILE
    try:
        X_vol = np.array([[0.01, 0.35, 25, 1.2]])  # High volatility
        pred = detector.predict(X_vol)
        
        assert pred.regime == RegimeType.VOLATILE
        print_check("Detects VOLATILE", True, f"confidence: {pred.confidence:.0%}")
    except Exception as e:
        print_check("Detects VOLATILE", False, str(e))
        all_passed = False
    
    return all_passed


def verify_hmm_detector() -> bool:
    """Verify HMM detector."""
    print_header("VERIFYING HMM DETECTOR")
    
    all_passed = True
    
    from src.ml.models import HMMRegimeDetector, HMMConfig
    
    # Create with config
    try:
        config = HMMConfig(n_states=4, n_iter=50)
        detector = HMMRegimeDetector(config)
        
        assert not detector.is_fitted
        print_check("Initialization", True)
    except Exception as e:
        print_check("Initialization", False, str(e))
        all_passed = False
        return False
    
    # Generate synthetic data
    np.random.seed(42)
    n_samples = 300
    X_train = np.column_stack([
        np.random.randn(n_samples) * 0.02,
        np.random.uniform(0.1, 0.3, n_samples),
        np.random.uniform(15, 35, n_samples),
        np.random.uniform(0.8, 1.2, n_samples),
    ])
    
    # Train
    try:
        detector.fit(X_train)
        
        assert detector.is_fitted
        print_check("Training", True, f"samples: {n_samples}")
    except Exception as e:
        print_check("Training", False, str(e))
        all_passed = False
        return False
    
    # Predict
    try:
        X_test = X_train[-1:]
        pred = detector.predict(X_test)
        
        assert pred.regime is not None
        print_check("Prediction", True, f"Regime: {pred.regime.value}")
    except Exception as e:
        print_check("Prediction", False, str(e))
        all_passed = False
    
    return all_passed


def main():
    print("STARTING PHASE A2 VERIFICATION")
    
    checks = [
        verify_imports(),
        verify_interfaces(),
        verify_rules_baseline(),
        verify_hmm_detector(),
    ]
    
    if all(checks):
        print("\n" + "="*60)
        print("  ALL CHECKS PASSED - PHASE A2 COMPLETE")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("  SOME CHECKS FAILED")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
