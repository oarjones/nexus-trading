#!/usr/bin/env python3
"""
Test script for HMM Regime Detector.
Generates synthetic data and verifies model training and prediction.
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import shutil

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ml.models.hmm_regime import HMMRegimeDetector, HMMConfig
from src.ml.utils.feature_prep import FeaturePreparator
from src.ml.interfaces import RegimeType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_synthetic_data(n_days=1000):
    """Generate synthetic market data with regimes."""
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=n_days, freq='D')
    
    # Simulate regimes: 0=BULL, 1=BEAR, 2=SIDEWAYS, 3=VOLATILE
    regime_length = n_days // 8
    regimes = []
    for _ in range(8):
        regime = np.random.choice([0, 1, 2, 3])
        regimes.extend([regime] * regime_length)
    regimes = regimes[:n_days]
    
    data = {'timestamp': dates}
    features = ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
    
    for f in features:
        data[f] = []
    
    for r in regimes:
        if r == 0:  # BULL
            returns = np.random.normal(0.002, 0.01)
            vol = np.random.uniform(0.10, 0.15)
            adx = np.random.uniform(25, 40)
        elif r == 1:  # BEAR
            returns = np.random.normal(-0.002, 0.015)
            vol = np.random.uniform(0.20, 0.30)
            adx = np.random.uniform(25, 40)
        elif r == 2:  # SIDEWAYS
            returns = np.random.normal(0, 0.005)
            vol = np.random.uniform(0.08, 0.12)
            adx = np.random.uniform(10, 20)
        else:  # VOLATILE
            returns = np.random.normal(0, 0.03)
            vol = np.random.uniform(0.30, 0.50)
            adx = np.random.uniform(20, 35)
            
        data["returns_5d"].append(returns * 5)
        data["volatility_20d"].append(vol)
        data["adx_14"].append(adx)
        data["volume_ratio"].append(np.random.uniform(0.8, 1.5))
        
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df, features

def main():
    print("TESTING HMM REGIME DETECTOR")
    print("=" * 50)
    
    try:
        # 1. Generate Data
        print("Generating synthetic data...")
        df, features = generate_synthetic_data()
        print(f"Generated {len(df)} samples")
        
        # 2. Prepare Features
        print("Preparing features...")
        preparator = FeaturePreparator(features=features)
        X, _ = preparator.prepare(df, fit_winsorize=True)
        print(f"Features shape: {X.shape}")
        
        # 3. Train Model
        print("Training HMM model...")
        config = HMMConfig(n_states=4, n_iter=50, features=features)
        detector = HMMRegimeDetector(config)
        detector.fit(X)
        
        metrics = detector.get_metrics()
        print(f"Training converged: {metrics.regime_distribution}")
        print(f"Log-likelihood: {metrics.log_likelihood:.2f}")
        
        # 4. Test Prediction
        print("Testing prediction...")
        test_sample = X[-1:]
        pred = detector.predict(test_sample)
        print(f"Prediction: {pred.regime.value} ({pred.confidence:.2%})")
        
        # 5. Test Save/Load
        print("Testing save/load...")
        test_dir = Path("models/test_hmm")
        if test_dir.exists():
            shutil.rmtree(test_dir)
            
        detector.save(str(test_dir))
        loaded = HMMRegimeDetector.load(str(test_dir))
        
        pred_loaded = loaded.predict(test_sample)
        if pred.regime == pred_loaded.regime:
            print("OK: Save/Load verification passed")
        else:
            print("FAIL: Save/Load verification failed")
            return 1
            
        # Cleanup
        if test_dir.exists():
            shutil.rmtree(test_dir)
            
        print("\nOK: HMM IMPLEMENTATION VERIFIED")
        return 0
        
    except Exception as e:
        print(f"\nFAIL: Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
