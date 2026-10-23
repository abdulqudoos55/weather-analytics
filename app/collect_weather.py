import asyncio
import logging
import os

import psycopg

from app.china import save_location_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


async def main():
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"]
    ) as conn:
        cursor = await conn.execute("""
            SELECT DISTINCT city
            FROM weather_readings
            WHERE city LIKE 'cn:%'
            ORDER BY city
        """)
        cities = await cursor.fetchall()

    failures = 0
    for (key,) in cities:
        try:
            location_id = int(key.split(":", 1)[1])
            result = await asyncio.wait_for(
                save_location_weather(location_id),
                timeout=90,
            )
            logging.info("Recorded %s (%s)", result["city"], key)
        except Exception:
            failures += 1
            logging.exception("Failed to record %s", key)
        await asyncio.sleep(1)

    logging.info(
        "Finished: %s cities, %s failures",
        len(cities), failures,
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

