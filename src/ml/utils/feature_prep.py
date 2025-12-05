"""
Utilities for preparing features for ML models.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FeaturePreparator:
    """
    Prepares features for ML model training and inference.
    
    Functionalities:
    - Relevant feature selection
    - Missing value handling
    - Outlier winsorization
    - Conversion to numpy format
    """
    
    def __init__(
        self,
        features: List[str],
        winsorize_percentile: float = 0.01,
        fill_method: str = "ffill"
    ):
        """
        Args:
            features: List of columns to extract
            winsorize_percentile: Percentile for winsorization (0.01 = 1%)
            fill_method: Method for missing values ('ffill', 'drop', 'zero')
        """
        self.features = features
        self.winsorize_percentile = winsorize_percentile
        self.fill_method = fill_method
        self._winsorize_bounds: Optional[dict] = None
    
    def prepare(
        self,
        df: pd.DataFrame,
        fit_winsorize: bool = True
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Prepare DataFrame for ML model use.
        
        Args:
            df: DataFrame with features
            fit_winsorize: If True, calculate winsorization bounds
        
        Returns:
            Tuple of (numpy array, list of valid features)
        """
        # Verify features exist
        missing = [f for f in self.features if f not in df.columns]
        if missing:
            raise ValueError(f"Features not found in DataFrame: {missing}")
        
        # Extract features
        data = df[self.features].copy()
        
        # Handle missing values
        if self.fill_method == "ffill":
            data = data.ffill().bfill()
        elif self.fill_method == "drop":
            data = data.dropna()
        elif self.fill_method == "zero":
            data = data.fillna(0)
        
        # Winsorize outliers
        if fit_winsorize:
            self._winsorize_bounds = {}
            for col in self.features:
                lower = data[col].quantile(self.winsorize_percentile)
                upper = data[col].quantile(1 - self.winsorize_percentile)
                self._winsorize_bounds[col] = (lower, upper)
                data[col] = data[col].clip(lower, upper)
        elif self._winsorize_bounds:
            for col in self.features:
                lower, upper = self._winsorize_bounds[col]
                data[col] = data[col].clip(lower, upper)
        
        # Verify no NaN remains
        if data.isna().any().any():
            nan_cols = data.columns[data.isna().any()].tolist()
            logger.warning(f"NaN still present in columns: {nan_cols}")
            data = data.fillna(0)
        
        X = data.values.astype(np.float64)
        
        logger.info(f"Features prepared: shape={X.shape}, features={self.features}")
        return X, self.features
    
    def prepare_single(self, features_dict: dict) -> np.ndarray:
        """
        Prepare a single feature vector from dictionary.
        
        Args:
            features_dict: Dict with feature name -> value
        
        Returns:
            Numpy array (1, n_features)
        """
        values = []
        for f in self.features:
            if f not in features_dict:
                raise ValueError(f"Feature '{f}' not found in input")
            values.append(features_dict[f])
        
        X = np.array(values, dtype=np.float64).reshape(1, -1)
        
        # Apply winsorization if exists
        if self._winsorize_bounds:
            for i, col in enumerate(self.features):
                if col in self._winsorize_bounds:
                    lower, upper = self._winsorize_bounds[col]
                    X[0, i] = np.clip(X[0, i], lower, upper)
        
        return X
