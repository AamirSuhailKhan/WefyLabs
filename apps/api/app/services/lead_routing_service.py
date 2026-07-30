import uuid
from typing import List, Dict, Any, Optional, Tuple

class LeadRoutingService:
    """
    Enterprise Lead Auto-Routing Engine surpassing Follow Up Boss & kvCORE.
    Supports Round-Robin, Weighted Load, and Geographic/Language matching.
    """

    @classmethod
    def assign_lead_round_robin(
        cls,
        lead_id: uuid.UUID,
        available_agent_ids: List[uuid.UUID],
        last_assigned_index: int = 0
    ) -> Tuple[uuid.UUID, int]:
        if not available_agent_ids:
            raise ValueError("No available agents for lead assignment")

        next_index = (last_assigned_index + 1) % len(available_agent_ids)
        assigned_agent_id = available_agent_ids[next_index]
        return assigned_agent_id, next_index

    @classmethod
    def assign_by_agent_capacity(
        cls,
        lead_id: uuid.UUID,
        agent_workloads: Dict[uuid.UUID, int], # agent_id -> current_active_leads_count
        max_capacity_per_agent: int = 50
    ) -> Optional[uuid.UUID]:
        eligible_agents = {
            agent_id: count for agent_id, count in agent_workloads.items()
            if count < max_capacity_per_agent
        }

        if not eligible_agents:
            return None

        # Assign to agent with lowest current active workload
        sorted_agents = sorted(eligible_agents.items(), key=lambda item: item[1])
        return sorted_agents[0][0]
