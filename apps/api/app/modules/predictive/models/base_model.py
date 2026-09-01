"""
Base Predictive Model Abstraction & Evaluation Contracts
========================================================
Standardized interfaces for training, batch prediction, probability calibration,
SHAP explainability, and serialization.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class ModelEvaluationMetrics:
    roc_auc: float = 0.0
    pr_auc: float = 0.0
    brier_score: float = 0.0
    log_loss: float = 0.0
    mae: float = 0.0
    rmse: float = 0.0
    expected_calibration_error: float = 0.0
    sample_size: int = 0
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class FeatureAttribution:
    feature_name: str
    impact_score: float  # Positive = increases likelihood, Negative = reduces likelihood
    description: str

@dataclass
class PredictionExplanationResult:
    positive_drivers: List[FeatureAttribution]
    negative_drivers: List[FeatureAttribution]
    summary_markdown: str

@dataclass
class PredictionResult:
    entity_id: str
    prediction_type: str
    raw_score: float
    calibrated_probability: float
    confidence_score: float
    confidence_level: str  # LOW | MEDIUM | HIGH
    model_version_tag: str
    feature_schema_version: str
    features_snapshot: Dict[str, Any]
    explanation: PredictionExplanationResult
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: Optional[datetime] = None

class BasePredictionModel(ABC):
    """
    Standard abstract interface implemented by all ML/Statistical predictive models.
    """

    def __init__(self, model_key: str, version_tag: str, algorithm_type: str):
        self.model_key = model_key
        self.version_tag = version_tag
        self.algorithm_type = algorithm_type
        self.weights: Dict[str, float] = {}
        self.platt_a: float = 1.0
        self.platt_b: float = 0.0

    @abstractmethod
    def train(self, training_data: List[Dict[str, Any]], labels: List[float]) -> ModelEvaluationMetrics:
        """Trains the model weights and fits probability calibration."""
        pass

    @abstractmethod
    def predict(self, feature_vector: Dict[str, Any], entity_id: str) -> PredictionResult:
        """Inference for a single feature vector."""
        pass

    @abstractmethod
    def predict_batch(self, feature_vectors: List[Dict[str, Any]]) -> List[PredictionResult]:
        """Batch inference across multiple feature vectors."""
        pass

    @abstractmethod
    def calibrate(self, raw_probability: float) -> float:
        """Applies Platt scaling or Isotonic transformation."""
        pass

    @abstractmethod
    def explain(self, feature_vector: Dict[str, Any]) -> PredictionExplanationResult:
        """Generates SHAP / feature attribution explanations."""
        pass

    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """Serializes model weights and calibration parameters to JSON."""
        pass

    @abstractmethod
    def load(self, artifact_json: Dict[str, Any]) -> None:
        """Loads serialized model weights and parameters."""
        pass
