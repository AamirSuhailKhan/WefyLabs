from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.infrastructure.persistence.sqlalchemy_lead_repository import SQLAlchemyLeadRepository

class UnitOfWork:
    """
    Async Unit of Work pattern guaranteeing transaction atomicity.
    Commits changes automatically on clean exit, rolls back on exception.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.leads = SQLAlchemyLeadRepository(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

@asynccontextmanager
async def get_unit_of_work() -> AsyncGenerator[UnitOfWork, None]:
    async with AsyncSessionLocal() as session:
        uow = UnitOfWork(session)
        try:
            yield uow
            await uow.commit()
        except Exception:
            await uow.rollback()
            raise
        finally:
            await session.close()
