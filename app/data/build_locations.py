import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

folder = Path(__file__).parent

def download(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "WeatherAnalytics/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()

print("Downloading province names…", flush=True)
admin_text = download(
    "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
).decode("utf-8")

provinces = {}
for line in admin_text.splitlines():
    fields = line.split("\t")
    if len(fields) >= 4 and fields[0].startswith("CN."):
        provinces[fields[0].split(".", 1)[1]] = fields[1]

print("Downloading China locations…", flush=True)
archive_data = download(
    "https://download.geonames.org/export/dump/CN.zip"
)

locations = []
with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
    with archive.open("CN.txt") as raw:
        reader = csv.reader(
            io.TextIOWrapper(raw, encoding="utf-8"),
            delimiter="\t",
        )
        for fields in reader:
            if len(fields) < 19:
                continue
            # Populated places: cities, towns and villages.
            if fields[6] != "P":
                continue
            # Exclude abandoned, destroyed and historical places.
            if fields[7] in {"PPLQ", "PPLW", "PPLH"}:
                continue

            province = provinces.get(fields[10])
            if not province:
                continue

            locations.append({
                "id": int(fields[0]),
                "name": fields[1],
                "province": province,
                "latitude": float(fields[4]),
                "longitude": float(fields[5]),
                "population": int(fields[14] or 0),
                "search": (
                    fields[1] + " " + fields[2] + " " +
                    fields[3] + " " + province
                ).casefold(),
            })

locations.sort(
    key=lambda item: (
        item["province"],
        -item["population"],
        item["name"],
    )
)

if not locations:
    raise SystemExit("No locations found. Existing data was not replaced.")

target = folder / "china_locations.json"
temporary = target.with_suffix(".tmp")
temporary.write_text(
    json.dumps(locations, ensure_ascii=False),
    encoding="utf-8",
)
temporary.replace(target)

(folder / "SOURCE.txt").write_text(
    "Source: GeoNames geographical database\n"
    "https://www.geonames.org/\n"
    "Licence: Creative Commons Attribution 4.0\n"
    "Coverage follows GeoNames country and administrative coding.\n",
    encoding="utf-8",
)

print(
    f"Ready: {len(locations):,} locations across "
    f"{len(set(item['province'] for item in locations))} "
    "province-level areas."
)
