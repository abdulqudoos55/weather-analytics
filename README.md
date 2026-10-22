# Weather Analytics

A personal full-stack weather and air-quality dashboard for China.

## Features

- Search cities and filter by province
- Current weather and seven-day forecasts
- PM2.5, PM10, and US AQI
- Interactive temperature charts
- PostgreSQL weather history with duplicate protection
- Automatic recording every 30 minutes using systemd
- Responsive interface with a decorative Shanghai skyline


## Screenshots

### Weather and air quality

![Current weather and air-quality dashboard](docs/images/dashboard.png)

### Seven-day forecast

![Seven-day weather forecast](docs/images/forecast.png)

### Temperature trends and recorded weather

![Temperature chart and recorded weather history](docs/images/history.png)

## Technologies

Python, FastAPI, asynchronous programming, REST APIs, PostgreSQL,
SQLite, HTML, CSS, JavaScript, Chart.js, Docker Compose, Linux,
and systemd.

## Setup

1. Install Python 3.12 or newer and Docker with Docker Compose.
2. Copy .env.example to .env.
3. Set a strong POSTGRES_PASSWORD in .env.
4. Run: python3 app/data/build_locations.py
5. Run: python3 app/data/build_location_db.py
6. Run: docker compose up -d --build
7. Open: http://37.27.39.68:8001/dashboard


## Automatic recording

The deployment files assume the project is at /opt/weather-analytics.

Copy deploy/weather-collector.service and deploy/weather-collector.timer
to /etc/systemd/system/, then run:

    sudo systemctl daemon-reload
    sudo systemctl enable --now weather-collector.timer

A city joins the recording list after its first successful dashboard
recording. Collection continues at :00 and :30 even when the browser closes.

Recorded timestamps represent the provider's weather time.
Actual collection time is stored separately.
Air-quality values are displayed but are not yet stored in history.

## Data sources

Weather and geocoding: Open-Meteo — https://open-meteo.com/
Air quality: CAMS — https://atmosphere.copernicus.eu/
Location data: GeoNames — https://www.geonames.org/ (CC BY 4.0)


Data are model-based estimates. US AQI differs from China's AQI scale.

## Project status

Personal portfolio demonstration.
