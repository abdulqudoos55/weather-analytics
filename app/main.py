import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"]
    ) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS weather_readings (
                id BIGSERIAL PRIMARY KEY,
                city TEXT NOT NULL,
                observed_at TIMESTAMPTZ NOT NULL,
                temperature_c DOUBLE PRECISION,
                humidity_percent DOUBLE PRECISION,
                wind_speed_kmh DOUBLE PRECISION,
                pm25_ug_m3 DOUBLE PRECISION,
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            ALTER TABLE weather_readings
            ADD COLUMN IF NOT EXISTS condition TEXT
        """)
    yield


app = FastAPI(
    title="Weather & Air Quality API",
    lifespan=lifespan,
)


@app.get("/")
async def home():
    return {"message": "Weather backend is running"}


@app.get("/api/health")
async def health():
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"]
    ) as conn:
        cursor = await conn.execute("SELECT 1")
        await cursor.fetchone()
    return {"status": "ok", "database": "connected"}


import httpx
from fastapi import HTTPException


CITIES = {
    "jinan": (36.6512, 117.1201),
    "shanghai": (31.2304, 121.4737),
    "beijing": (39.9042, 116.4074),
}


@app.get("/api/weather/{city}")
async def weather(city: str):
    city = city.strip().lower()
    if city not in CITIES:
        raise HTTPException(
            status_code=404,
            detail="Choose jinan, shanghai, or beijing",
        )

    latitude, longitude = CITIES[city]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": (
                        "temperature_2m,"
                        "relative_humidity_2m,"
                        "wind_speed_10m"
                    ),
                    "timezone": "UTC",
                },
            )
            response.raise_for_status()
            data = response.json()
            current = data["current"]

        return {
            "city": city,
            "source": "Open-Meteo",
            "time_utc": current["time"],
            "temperature_c": current["temperature_2m"],
            "humidity_percent": current["relative_humidity_2m"],
            "wind_speed_kmh": current["wind_speed_10m"],
        }
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Weather provider unavailable or returned invalid data",
        ) from exc


from datetime import datetime, timezone


@app.post("/api/readings/{city}", status_code=201)
async def save_reading(city: str):
    reading = await weather(city)
    observed_at = datetime.fromisoformat(
        reading["time_utc"]
    ).replace(tzinfo=timezone.utc)

    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"]
    ) as conn:
        cursor = await conn.execute(
            """
            INSERT INTO weather_readings (
                city, observed_at, temperature_c,
                humidity_percent, wind_speed_kmh
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                reading["city"],
                observed_at,
                reading["temperature_c"],
                reading["humidity_percent"],
                reading["wind_speed_kmh"],
            ),
        )
        row = await cursor.fetchone()

    return {"id": row[0], **reading}


@app.get("/api/readings/{city}")
async def list_readings(city: str):
    city = city.strip().lower()
    if city not in CITIES:
        raise HTTPException(status_code=404, detail="Unknown city")

    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"],
        row_factory=psycopg.rows.dict_row,
    ) as conn:
        cursor = await conn.execute(
            """
            SELECT id, city, observed_at, temperature_c,
                   humidity_percent, wind_speed_kmh, fetched_at
            FROM weather_readings
            WHERE city = %s
            ORDER BY observed_at DESC, id DESC
            LIMIT 100
            """,
            (city,),
        )
        return {"city": city, "readings": await cursor.fetchall()}


from fastapi.responses import FileResponse
from pathlib import Path


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(
        Path(__file__).parent / "static" / "index.html"
    )


from app.china import router as china_router
app.include_router(china_router)


@app.get("/china", include_in_schema=False)
async def china_dashboard():
    return FileResponse(
        Path(__file__).parent / "static" / "china.html"
    )


from app.air import router as air_router
app.include_router(air_router)


from app.locations import router as locations_router
app.include_router(locations_router)


from fastapi.staticfiles import StaticFiles
app.mount(
    "/assets",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="assets",
)
