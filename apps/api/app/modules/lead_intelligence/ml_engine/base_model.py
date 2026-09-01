"""
Base ML Model — Abstract Machine Learning Interface
===================================================
Defines plugin contract for all model implementations (Hybrid, XGBoost, Random Forest, LLM).
Models can be swapped without changing CRM application code.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseMLModel(ABC):
    """
    Abstract base class for all Lead Scoring ML Model implementations.
    """
    version: str = "v1.0.0"
    model_name: str = "base_model"

    @abstractmethod
    def predict(self, features: Dict[str, Any], rule_adjustment: float = 0.0) -> Dict[str, Any]:
        """
        Runs model inference on feature vector.
        Returns:
            {
                "raw_score": 75.4,
                "confidence": 0.91,
                "model_version": "v1.0.0",
                "feature_contributions": {...}
            }
        """
        pass
