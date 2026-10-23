import io
import os
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://download.geonames.org/export/dump/"
FOLDER = Path(__file__).resolve().parent


def download(name):
    path = FOLDER / name
    temporary = path.with_suffix(path.suffix + ".download")
    print("Downloading", name, flush=True)
    request = urllib.request.Request(
        BASE + name,
        headers={"User-Agent": "WeatherAnalytics/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        with temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    temporary.replace(path)
    return path


countries = {}
country_path = download("countryInfo.txt")
for line in country_path.read_text(encoding="utf-8").splitlines():
    if not line or line.startswith("#"):
        continue
    columns = line.split("\t")
    if len(columns) > 4:
        countries[columns[0]] = columns[4]

regions = {}
region_path = download("admin1CodesASCII.txt")
for line in region_path.read_text(encoding="utf-8").splitlines():
    columns = line.split("\t")
    if len(columns) >= 3:
        regions[columns[0]] = columns[1]

archive = download("cities500.zip")
temporary_db = FOLDER / "world_locations.build.sqlite"
destination = FOLDER / "world_locations.sqlite"

if temporary_db.exists():
    temporary_db.unlink()

with sqlite3.connect(temporary_db) as db:
    db.execute("""
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            country_code TEXT NOT NULL,
            country TEXT NOT NULL,
            province TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timezone TEXT NOT NULL,
            population INTEGER NOT NULL,
            search TEXT NOT NULL
        )
    """)

    batch = []
    with zipfile.ZipFile(archive) as zipped:
        with zipped.open("cities500.txt") as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8"):
                columns = line.rstrip("\r\n").split("\t")
                if len(columns) < 19:
                    continue

                code = columns[8]
                country = countries.get(code, code)
                province = regions.get(
                    code + "." + columns[10], ""
                )
                search = " ".join([
                    columns[1], columns[2], columns[3],
                    province, country, code,
                ]).casefold()

                batch.append((
                    int(columns[0]),
                    columns[2] or columns[1],
                    code,
                    country,
                    province,
                    float(columns[4]),
                    float(columns[5]),
                    columns[17],
                    int(columns[14] or 0),
                    search,
                ))

                if len(batch) >= 2000:
                    db.executemany(
                        "INSERT INTO locations VALUES (?,?,?,?,?,?,?,?,?,?)",
                        batch,
                    )
                    batch.clear()

    if batch:
        db.executemany(
            "INSERT INTO locations VALUES (?,?,?,?,?,?,?,?,?,?)",
            batch,
        )

    db.execute("""
        CREATE INDEX locations_country_region
        ON locations(country_code, province, population DESC)
    """)

    count = db.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    country_count = db.execute(
        "SELECT COUNT(DISTINCT country_code) FROM locations"
    ).fetchone()[0]

    if count < 10000:
        raise RuntimeError("Dataset appears incomplete; existing database preserved.")

os.replace(temporary_db, destination)

print(f"Ready: {count:,} locations across {country_count} country/area codes.")
print("Database:", destination)
