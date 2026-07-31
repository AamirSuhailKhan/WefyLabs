import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from app.core.domain.automation.entities import WorkflowEntity

class IWorkflowRepository(ABC):
    """Abstract Hexagonal Port for Workflow Definition Storage."""

    @abstractmethod
    async def get_by_id(self, workflow_id: uuid.UUID) -> Optional[WorkflowEntity]:
        pass

    @abstractmethod
    async def save(self, workflow: WorkflowEntity) -> WorkflowEntity:
        pass

    @abstractmethod
    async def list_workflows(
        self,
        broker_id: uuid.UUID,
        is_active: Optional[bool] = None,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[WorkflowEntity], int]:
        pass

class IWorkflowExecutionEngine(ABC):
    """Abstract Port for executing DAG Node Graph Workflows."""

    @abstractmethod
    async def execute_workflow(self, workflow_id: uuid.UUID, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass
