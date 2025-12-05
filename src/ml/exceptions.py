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
