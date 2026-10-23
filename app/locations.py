import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/locations")
DATABASE = Path(__file__).parent / "data" / "world_locations.sqlite"


def connect():
    db = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def lookup_location(location_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM locations WHERE id = ?",
            (location_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "admin1": row["province"],
        "country": row["country"],
        "country_code": row["country_code"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "timezone": row["timezone"],
    }


@router.get("")
def locations(
    q: str = Query(default="", max_length=100),
    province: str = Query(default="", max_length=100),
    country: str = Query(default="", max_length=2),
    offset: int = Query(default=0, ge=0, le=1000000),
):
    clauses, args = [], []
    if country:
        clauses.append("country_code = ?")
        args.append(country.upper())
    if province:
        clauses.append("province = ?")
        args.append(province)
    for word in q.strip().casefold().split():
        clauses.append("instr(search, ?) > 0")
        args.append(word)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as db:
        rows = db.execute(
            """
            SELECT id, name, province, country, country_code,
                   latitude, longitude, timezone
            FROM locations
            """ + where +
            " ORDER BY population DESC, name, id LIMIT 51 OFFSET ?",
            [*args, offset],
        ).fetchall()

    return {
        "locations": [dict(row) for row in rows[:50]],
        "has_more": len(rows) > 50,
    }


@router.get("/countries")
def countries():
    with connect() as db:
        rows = db.execute("""
            SELECT DISTINCT country_code AS code, country AS name
            FROM locations
            ORDER BY country
        """).fetchall()
    return {"countries": [dict(row) for row in rows]}


@router.get("/provinces")
def provinces(country: str = Query(default="CN", max_length=2)):
    with connect() as db:
        rows = db.execute(
            """
            SELECT DISTINCT province FROM locations
            WHERE country_code = ? AND province != ''
            ORDER BY province
            """,
            (country.upper(),),
        ).fetchall()
    return {"provinces": [row["province"] for row in rows]}

