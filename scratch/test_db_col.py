import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def check():
    async with async_session_maker() as session:
        r = await session.execute(text("SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = 'deal_offers' AND column_name = 'payment_plan'"))
        print("deal_offers.payment_plan:", r.fetchall())

asyncio.run(check())
