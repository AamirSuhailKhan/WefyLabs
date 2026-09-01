"""
ML Model Registry — Hot-swappable Model Registry
=================================================
Allows registering and deploying new ML model versions without downtime or code changes.
"""
import logging
from typing import Dict, Any, Optional
from .base_model import BaseMLModel
from .hybrid_model import RulePlusMLHybridModel

logger = logging.getLogger(__name__)


class MLModelRegistry:
    """
    Registry for hot-swappable ML model implementations.
    """

    def __init__(self):
        self._models: Dict[str, BaseMLModel] = {}
        self._active_version: str = "v1.0.0-hybrid"
        self._register_defaults()

    def _register_defaults(self):
        hybrid = RulePlusMLHybridModel()
        self.register_model(hybrid, is_active=True)

    def register_model(self, model: BaseMLModel, is_active: bool = False):
        self._models[model.version] = model
        if is_active:
            self._active_version = model.version
        logger.info(f"[ML_REGISTRY] Registered model {model.model_name} ({model.version}) [Active={is_active}]")

    def get_active_model(self) -> BaseMLModel:
        return self._models.get(self._active_version, RulePlusMLHybridModel())

    def get_model(self, version: str) -> Optional[BaseMLModel]:
        return self._models.get(version)
