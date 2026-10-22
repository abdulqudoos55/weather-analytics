import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/locations")
DATABASE = Path(__file__).parent / "data" / "locations.sqlite"


@router.get("")
def locations(
    q: str = Query(default="", max_length=100),
    province: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0, le=1000000),
):
    with sqlite3.connect(DATABASE) as db:
        db.row_factory = sqlite3.Row
        clauses, args = [], []
        if province:
            clauses.append("province = ?")
            args.append(province)
        if q.strip():
            clauses.append("instr(search, ?) > 0")
            args.append(q.strip().casefold())

        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = db.execute(
            "SELECT id, name, province FROM locations"
            + where
            + " ORDER BY population DESC, name, id LIMIT 51 OFFSET ?",
            [*args, offset],
        ).fetchall()

        return {
            "locations": [dict(row) for row in rows[:50]],
            "has_more": len(rows) > 50,
        }


@router.get("/provinces")
def provinces():
    with sqlite3.connect(DATABASE) as db:
        rows = db.execute(
            "SELECT DISTINCT province FROM locations ORDER BY province"
        ).fetchall()
    return {"provinces": [row[0] for row in rows]}
