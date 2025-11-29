# National Parks Explorer

Minimal Python + MySQL app to ingest National Park Service (NPS) data and explore it via Streamlit with basic login.

## Quick Start

1) Enter project
```bash
cd national-parks-explorer
```

2) Create a virtual env and install deps (see [requirements.txt](national-parks-explorer/requirements.txt))
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3) Start MySQL (Docker)
```bash
docker run --name parks-mysql -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=national_parks_db -p 3306:3306 -d mysql:8
```
- If already started before
```bash
docker start parks-mysql
```

4) Apply schema (see [sql/schema.sql](national-parks-explorer/sql/schema.sql))
```bash
mysql -h 127.0.0.1 -u root -p national_parks_db < sql/schema.sql
```

5) Configure environment (edit [national-parks-explorer/.env](national-parks-explorer/.env))
Example:
```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=national_parks_db
DB_USER=root
DB_PASSWORD=rootpass
NPS_API_KEY=YOUR_API_KEY
RIDB_API_KEY=YOUR_API_KEY
NOAA_API_TOKEN=YOUR_TOKEN
NPS_BASE_URL=https://developer.nps.gov/api/v1
RIDB_BASE_URL=https://ridb.recreation.gov/api/v1
USGS_BASE_URL=https://earthquake.usgs.gov/fdsnws/event/1/query
NOAA_BASE_URL=https://www.ncdc.noaa.gov/cdo-web/api/v2
FLASK_SECRET_KEY=YOUR_KEY
```

6) Ingest data (see [backend/ingest.py](national-parks-explorer/backend/ingest.py))
```bash
python -m ingest.ingest_all
```

7) Create a user (see [backend/create_demo_user.py](national-parks-explorer/backend/create_demo_user.py))
```bash
python -m backend.create_demo_user kylie kylie@example.com MyStrongPass!
```

8) Run the backend API
```bash
python -m backend.auth_app
```

9) Run Streamlit app (see [frontend/app.py](national-parks-explorer/frontend/app.py))
```bash
streamlit run frontend/app.py
```
Open in browser:
```bash
$BROWSER http://localhost:8501
```

## What’s Included
- Data ingestion for parks and activities
- Streamlit pages: search, park details, activities filter, login
- Basic auth with sessions
