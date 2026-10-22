import asyncio
import os
import sys
from pathlib import Path

api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv('apps/api/.env')

from sqlalchemy import text
from app.database import async_session_maker

async def migrate():
    async with async_session_maker() as session:
        print("Adding missing columns to property_price_history...")
        sql = """
        ALTER TABLE property_price_history
        ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'INR',
        ADD COLUMN IF NOT EXISTS price_type VARCHAR(50) DEFAULT 'LIST_PRICE',
        ADD COLUMN IF NOT EXISTS unit_id UUID,
        ADD COLUMN IF NOT EXISTS source VARCHAR(100) DEFAULT 'manual',
        ADD COLUMN IF NOT EXISTS effective_from TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS effective_to TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS observed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        """
        await session.execute(text(sql))
        await session.commit()
        print("Successfully updated property_price_history columns.")

if __name__ == "__main__":
    asyncio.run(migrate())
