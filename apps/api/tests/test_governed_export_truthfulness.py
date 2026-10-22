import pytest
from fastapi import HTTPException

from app.modules.security.router import (
    GovernedExportRequest,
    request_governed_export,
)


@pytest.mark.asyncio
async def test_governed_export_does_not_claim_success_without_export_pipeline():
    with pytest.raises(HTTPException) as raised:
        await request_governed_export(
            req=GovernedExportRequest(export_type="leads", format="csv"),
            tenant=None,
            broker=None,
            db=None,
        )

    assert raised.value.status_code == 501
    assert raised.value.detail == "Governed exports are not available yet."
