"""Offline schema v5 -> v6: stop Sophos, run this module, restart."""

import asyncio

import asyncpg

from sophos.config import settings
from sophos.db import _CREATE_PLUGINS_TABLE


async def migrate() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        async with conn.transaction():
            version = await conn.fetchval("SELECT version FROM schema_meta WHERE singleton FOR UPDATE")
            if version != 5:
                raise RuntimeError(f"Expected schema v5, found v{version}")
            await conn.execute(_CREATE_PLUGINS_TABLE)
            await conn.execute("UPDATE schema_meta SET version = 6 WHERE singleton")
        print("Schema v6 ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
