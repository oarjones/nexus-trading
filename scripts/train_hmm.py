import asyncio
import logging
import sys
from pathlib import Path
# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from datetime import datetime, timedelta

import pandas as pd
import pandas_ta as ta
import yfinance as yf
from src.ml.models.hmm_regime import HMMRegimeDetector, HMMConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fetch_data(symbol: str = "SPY", years: int = 10) -> pd.DataFrame:
    """Download historical data."""
    start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
    logger.info(f"Downloading {symbol} data from {start_date}...")
    
    df = yf.download(symbol, start=start_date, progress=False)
    
    if df.empty:
        raise ValueError(f"No data found for {symbol}")
        
    # Flat column names if MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    return df

def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical features for HMM."""
    logger.info("Calculating features...")
    
    # Copy to avoid warnings
    df = df.copy()
    
    # 1. 5-day Returns
    df['returns_5d'] = df['Close'].pct_change(5)
    
    # 2. 20-day Volatility
    df['returns_1d'] = df['Close'].pct_change()
    df['volatility_20d'] = df['returns_1d'].rolling(20).std()
    
    # 3. ADX 14
    # pandas-ta adx returns DataFrame with ADX_14, DMP_14, DMN_14
    adx = df.ta.adx(length=14)
    if adx is not None and 'ADX_14' in adx.columns:
        df['adx_14'] = adx['ADX_14']
    else:
        logger.warning("Could not calculate ADX, using simplistic fallback")
        df['adx_14'] = 20.0 # Fallback
        
    # 4. Volume Ratio
    df['volume_sma_20'] = df['Volume'].rolling(20).mean()
    df['volume_ratio'] = df['Volume'] / df['volume_sma_20']
    
    # Select features and drop NaNs
    features = ['returns_5d', 'volatility_20d', 'adx_14', 'volume_ratio']
    df_clean = df[features].dropna()
    
    logger.info(f"Prepared {len(df_clean)} samples with features: {features}")
    return df_clean

def main():
    try:
        # 1. Get Data
        df = fetch_data("SPY")
        
        # 2. Prepare Features
        df_features = prepare_features(df)
        
        if len(df_features) < 100:
            raise ValueError("Not enough data to train model")
            
        # 3. Configure Model
        features_list = ['returns_5d', 'volatility_20d', 'adx_14', 'volume_ratio']
        config = HMMConfig(
            n_states=4,
            n_iter=100,
            features=features_list,
            random_state=42
        )
        
        detector = HMMRegimeDetector(config)
        
        # 4. Train
        logger.info("Training HMM model...")
        X = df_features.values
        detector.fit(X)
        
        # 5. Save
        save_path = Path("models/hmm_spy_v1")
        detector.save(str(save_path))
        
        logger.info(f"Model successfully saved to {save_path}")
        
        # 6. Verify by loading
        logger.info("Verifying model load...")
        loaded_detector = HMMRegimeDetector.load(str(save_path))
        
        # Predict on last data point
        last_sample = X[-1:]
        prediction = loaded_detector.predict(last_sample)
        
        logger.info(f"Current Regime: {prediction.regime.value}")
        logger.info(f"Confidence: {prediction.confidence:.2f}")
        logger.info("Probabilities:")
        for r, p in prediction.probabilities.items():
            logger.info(f"  {r}: {p:.4f}")
            
    except Exception as e:
        logger.error(f"Training failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
