import asyncio
from coser_bot.database.db import Database

async def init_db():
    db = Database()
    await db.connect()
    await db.initialize()
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(init_db()) 