"""
Machine Learning module for Nexus Trading.

Exports main interfaces and factory.
"""

from .interfaces import (
    RegimeType,
    RegimePrediction,
    ModelMetrics,
    RegimeDetector,
    ModelFactory,
)

from .exceptions import (
    MLError,
    ModelNotFittedError,
    InvalidFeaturesError,
    ModelLoadError,
    ModelSaveError,
    TrainingError,
    ConfigurationError,
    InferenceError,
)

__all__ = [
    # Interfaces
    "RegimeType",
    "RegimePrediction",
    "ModelMetrics",
    "RegimeDetector",
    "ModelFactory",
    # Exceptions
    "MLError",
    "ModelNotFittedError",
    "InvalidFeaturesError",
    "ModelLoadError",
    "ModelSaveError",
    "TrainingError",
    "ConfigurationError",
    "InferenceError",
]
