from fastapi import APIRouter, HTTPException
from app.china import fetch_json

router = APIRouter(prefix="/api/air")


@router.get("/{location_id}")
async def air_quality(location_id: int):
    location = await fetch_json(
        "https://geocoding-api.open-meteo.com/v1/get",
        {"id": location_id, "language": "en"},
    )

    data = await fetch_json(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": "pm2_5,pm10,us_aqi",
            "timezone": "auto",
        },
    )
    current = data.get("current")
    if not current:
        raise HTTPException(status_code=502, detail="Air-quality data unavailable.")

    return {
        "city": location["name"],
        "time": current.get("time"),
        "timezone": data.get("timezone", "UTC"),
        "pm25": current.get("pm2_5"),
        "pm10": current.get("pm10"),
        "us_aqi": current.get("us_aqi"),
        "source": "Open-Meteo / CAMS",
    }

