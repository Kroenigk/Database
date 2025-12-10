# National Parks Explorer

# National Parks Explorer

## Table of Contents
1. Overview  
2. What's Included  
3. Data Sources  
4. API Overview  
5. Features  
6. Database  
7. Diagrams  
8. Screenshots  
9. Quick Start
10. Data Sources

---

## 1. Overview
A full-stack National Parks Explorer application with a Streamlit frontend, Flask backend, and a MySQL database (30 tables).  
Users can explore all 63 U.S. National Parks, view trails and campgrounds, write reviews, plan trips, and create campground reservations.

---

## 2. What's Included
- Data ingestion for multiple public datasets  
- Flask backend serving REST API endpoints  
- Streamlit frontend connected to backend  
- SQL schema and table definitions  
- ER diagram (in separate file)  
- Authentication with session-based access control  
- Activity logging for key actions  
- User-facing Streamlit pages:
  - Park search  
  - Park details  
  - Trails  
  - Campgrounds  
  - Park reviews  
  - Trail reviews  
  - Trip logs  
  - Wishlist trips  
  - Favorite parks  
  - Park popularity  
  - Park tags  
  - Login / Signup  
- Multi-tab layouts within pages for organization

---

## 3. Data Sources
- **RIDB (Recreation.gov)** — facilities, campgrounds, amenities  
- **NPS API** — parks, descriptions, locations  
- **USGS** — geographic data  
- **NOAA** — climate and environmental data  
- **Custom tag dataset**  
- **Dummy popularity metrics**

---

## 4. API Overview
Backend exposes `GET`, `POST`, `PUT`, and `DELETE` endpoints for:
- Parks  
- Trails  
- Campgrounds  
- Reviews (park + trail)  
- Reservations  
- Tags  
- Wishlist trips  
- Trip logs  
- Favorite parks  

---

## 5. Features

### Read
- Park details  
- Trail details  
- Campground details  
- User reviews  
- User reservations  
- User trip logs  
- User wishlist trips  
- Park popularity data  
- Park tags  

### Write
- Create trip log  
- Create trail review  
- Create park review  
- Add wishlist trip  
- Add favorite park  

### Update
- Update trip log  
- Update wishlist trip  

### Delete
- Remove favorite park  

---

## 6. Database
- 30 total tables  
- Includes core data tables, user-generated content, join tables, and logging tables

---

## 7. Diagrams
- Mermaid ER diagram located in the `ERD.md` file

---

## 8. Screenshots
- UI screenshots are available in the `/screenshots` directory


## 9. Quick Start

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
API_BASE_URL=YOUR_HOST
```

6) Ingest data (see [backend/ingest.py](national-parks-explorer/backend/ingest.py))
```bash
python -m ingest.ingest_all
```

7) Run the backend API
```bash
python -m backend.auth_app
```

8) Run Streamlit app (see [frontend/app.py](national-parks-explorer/frontend/app.py))
```bash
streamlit run frontend/app.py
```
Open in browser:
```bash
$BROWSER http://localhost:8501
```

## 10. Data Sources
This project uses publicly available U.S. federal datasets and APIs:

- Recreation Information Database (RIDB), U.S. General Services Administration, 
    https://ridb.recreation.gov/

- National Park Service (NPS) Developer API, 
    https://www.nps.gov/subjects/developer/index.htm

- U.S. Geological Survey (USGS) Open Data,  
    https://earthquake.usgs.gov/fdsnws/event/1/query

- National Oceanic and Atmospheric Administration, NOAA Climate and Environmental Data, 
    https://www.ncdc.noaa.gov/cdo-web/api/v2/

