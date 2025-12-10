"""
Tests for the ML Model Factory.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import yaml

from src.ml.factory import RegimeDetectorFactory, get_regime_detector
from src.ml.models.hmm_regime import HMMRegimeDetector
from src.ml.models.rules_baseline import RulesBaselineDetector
from src.ml.exceptions import ConfigurationError

class TestRegimeDetectorFactory:
    """Tests for RegimeDetectorFactory."""
    
    @pytest.fixture(autouse=True)
    def reset_factory(self):
        """Reset singleton before each test."""
        RegimeDetectorFactory.reset_instance()
        yield
        RegimeDetectorFactory.reset_instance()
    
    @pytest.fixture
    def config_file(self):
        """Create temporary configuration file."""
        config = {
            "regime_detector": {
                "active": "rules",
                "models_dir": "models",
                "models": {
                    "hmm": {
                        "n_states": 4,
                        "n_iter": 50,
                        "features": ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
                    },
                    "rules": {
                        "volatile_vol_threshold": 0.25
                    }
                }
            }
        }
        
        # Create a temp file
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            yaml.dump(config, f)
            
        yield path
        
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
    
    def test_factory_singleton(self, config_file):
        factory1 = RegimeDetectorFactory.get_instance(config_file)
        factory2 = RegimeDetectorFactory.get_instance(config_file)
        
        assert factory1 is factory2
    
    def test_load_config(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        assert factory.get_active_model_type() == "rules"
        assert "hmm" in factory.get_available_models()
        assert "rules" in factory.get_available_models()
    
    def test_create_rules_detector(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        detector = factory.create_regime_detector("rules")
        
        assert isinstance(detector, RulesBaselineDetector)
        assert detector.is_fitted  # Rules is always fitted
    
    def test_create_hmm_detector_not_trained(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        detector = factory.create_regime_detector("hmm", load_trained=False)
        
        assert isinstance(detector, HMMRegimeDetector)
        assert not detector.is_fitted  # No trained model
    
    def test_create_invalid_model(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        with pytest.raises(ConfigurationError):
            factory.create_regime_detector("invalid_model")
    
    def test_get_active_detector_cached(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        detector1 = factory.get_active_detector()
        detector2 = factory.get_active_detector()
        
        assert detector1 is detector2  # Same object (cached)
    
    def test_invalidate_cache(self, config_file):
        factory = RegimeDetectorFactory(config_file)
        
        detector1 = factory.get_active_detector()
        factory.invalidate_cache()
        detector2 = factory.get_active_detector()
        
        assert detector1 is not detector2  # Different objects
    
    def test_default_config_if_file_missing(self):
        factory = RegimeDetectorFactory("nonexistent.yaml")
        
        # Should use default config
        assert factory.get_active_model_type() == "rules"
    
    def test_convenience_function(self, config_file):
        detector = get_regime_detector(config_file)
        
        assert isinstance(detector, RulesBaselineDetector)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
