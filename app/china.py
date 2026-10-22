import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/china")


async def fetch_json(url, params):
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Weather service unavailable. Please try again.",
        ) from exc


@router.get("/locations")
async def locations(q: str = Query(min_length=2, max_length=100)):
    data = await fetch_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        {
            "name": q.strip(),
            "count": 30,
            "language": "en",
            "countryCode": "CN",
        },
    )
    return {
        "locations": [
            {
                "id": item["id"],
                "name": item["name"],
                "province": item.get("admin1", ""),
                "district": item.get("admin2", ""),
                "latitude": item["latitude"],
                "longitude": item["longitude"],
            }
            for item in data.get("results", [])
            if item.get("country_code") == "CN"
        ]
    }


def condition(code):
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "Partly cloudy"
    if code == 3:
        return "Overcast"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55):
        return "Drizzle"
    if code in (56, 57):
        return "Freezing drizzle"
    if code in (61, 63, 65):
        return "Rain"
    if code in (66, 67):
        return "Freezing rain"
    if code in (71, 73, 75, 77):
        return "Snow"
    if code in (80, 81, 82):
        return "Rain showers"
    if code in (85, 86):
        return "Snow showers"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return "Unavailable"


@router.get("/forecast/{location_id}")
async def forecast(location_id: int):
    location = await fetch_json(
        "https://geocoding-api.open-meteo.com/v1/get",
        {"id": location_id, "language": "en"},
    )
    if location.get("country_code") != "CN":
        raise HTTPException(
            status_code=404,
            detail="Choose a location in China.",
        )

    data = await fetch_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": (
                "temperature_2m,relative_humidity_2m,"
                "wind_speed_10m,weather_code"
            ),
            "daily": (
                "weather_code,temperature_2m_max,"
                "temperature_2m_min,precipitation_probability_max,"
                "wind_speed_10m_max"
            ),
            "timezone": "Asia/Shanghai",
            "forecast_days": 7,
        },
    )

    current = data.get("current")
    daily = data.get("daily")
    if not current or not daily:
        raise HTTPException(
            status_code=502,
            detail="Provider returned incomplete forecast data.",
        )

    return {
        "city": location["name"],
        "province": location.get("admin1", ""),
        "timezone": "Asia/Shanghai",
        "source": "Open-Meteo",
        "current": {
            "time": current["time"],
            "temperature_c": current["temperature_2m"],
            "humidity_percent": current["relative_humidity_2m"],
            "wind_speed_kmh": current["wind_speed_10m"],
            "condition": condition(current["weather_code"]),
        },
        "days": [
            {
                "date": date,
                "condition": condition(daily["weather_code"][i]),
                "high_c": daily["temperature_2m_max"][i],
                "low_c": daily["temperature_2m_min"][i],
                "precipitation_probability_percent":
                    daily["precipitation_probability_max"][i],
                "max_wind_kmh": daily["wind_speed_10m_max"][i],
            }
            for i, date in enumerate(daily["time"])
        ],
    }


import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from zoneinfo import ZoneInfo


@router.post("/saved/{location_id}", status_code=201)
async def save_location_weather(location_id: int):
    data = await forecast(location_id)
    current = data["current"]
    observed = datetime.fromisoformat(current["time"]).replace(
        tzinfo=ZoneInfo("Asia/Shanghai")
    )
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"]
    ) as conn:
        await conn.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (location_id,),
        )
        cursor = await conn.execute(
            """
            INSERT INTO weather_readings (
                city, observed_at, temperature_c,
                humidity_percent, wind_speed_kmh, condition
            )
            SELECT %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM weather_readings
                WHERE city = %s AND observed_at = %s
            )
            RETURNING id
            """,
            (
                f"cn:{location_id}", observed,
                current["temperature_c"],
                current["humidity_percent"],
                current["wind_speed_kmh"],
                current["condition"],
                f"cn:{location_id}", observed,
            ),
        )
        row = await cursor.fetchone()
    return {"id": row[0] if row else None, "city": data["city"]}


@router.get("/saved/{location_id}")
async def location_history(location_id: int):
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"], row_factory=dict_row
    ) as conn:
        cursor = await conn.execute(
            """
            SELECT DISTINCT ON (observed_at) observed_at, temperature_c, humidity_percent,
                   wind_speed_kmh, condition
            FROM weather_readings
            WHERE city = %s
            ORDER BY observed_at DESC, id DESC
            LIMIT 50
            """,
            (f"cn:{location_id}",),
        )
        return {"readings": await cursor.fetchall()}
