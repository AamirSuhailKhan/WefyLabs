import math
from typing import List
from app.models.lead import Lead
from app.modules.leads.dto.lead_dto import LeadResponseDTO, LeadPaginatedResponseDTO

class LeadMapper:
    @staticmethod
    def to_response_dto(lead: Lead) -> LeadResponseDTO:
        return LeadResponseDTO.model_validate(lead)

    @staticmethod
    def to_paginated_dto(
        items: List[Lead],
        total: int,
        page: int,
        limit: int
    ) -> LeadPaginatedResponseDTO:
        pages = math.ceil(total / limit) if total > 0 else 0
        dtos = [LeadMapper.to_response_dto(item) for item in items]
        return LeadPaginatedResponseDTO(
            items=dtos,
            total=total,
            page=page,
            pages=pages,
            limit=limit,
            has_next=page < pages,
            has_prev=page > 1
        )
