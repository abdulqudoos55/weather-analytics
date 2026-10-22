import json
import sqlite3
from pathlib import Path

folder = Path(__file__).parent
print("Building searchable location database…", flush=True)
items = json.loads(
    (folder / "china_locations.json").read_text(encoding="utf-8")
)
db = sqlite3.connect(folder / "locations.sqlite")
db.execute("DROP TABLE IF EXISTS locations")
db.execute("""
CREATE TABLE locations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    province TEXT NOT NULL,
    population INTEGER NOT NULL,
    search TEXT NOT NULL
)
""")
db.executemany(
    "INSERT INTO locations VALUES (?, ?, ?, ?, ?)",
    (
        (
            item["id"], item["name"], item["province"],
            item["population"], item["search"],
        )
        for item in items
    ),
)
db.execute("""
CREATE INDEX location_province_population
ON locations(province, population DESC)
""")
db.execute("CREATE INDEX location_population ON locations(population DESC)")
db.commit()
print(f"Search database ready: {db.execute('SELECT COUNT(*) FROM locations').fetchone()[0]:,} locations")
db.close()
