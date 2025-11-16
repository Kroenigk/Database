# National Parks Explorer

A Python + MySQL application for exploring U.S. National Parks data. It ingests public data from the National Park Service (NPS) API into a normalized MySQL schema, then provides a Streamlit frontend to search parks by state, view details, and filter by activities. Includes a starter user authentication system and logging.

## Features
- Ingest parks, activities, derived states, and (TODO) campgrounds from NPS API.
- Normalize and store relational data (parks, states, activities, campgrounds, amenities).
- Streamlit UI: search parks by state, view park details, filter by activities, login.
- Authentication: user creation, password hashing (bcrypt), session tracking, activity log.
- Modular backend structure ready for expansion (SQLAlchemy optional).
- Clear schema with M:N relationships and auditing tables.

## Tech Stack
- Python 3.11+
- MySQL 8+
- Streamlit
- Requests
- mysql-connector-python
- Passlib (bcrypt)
- python-dotenv
- (Optional) SQLAlchemy ORM

## Getting Started

### 1. Clone and Enter Project
```bash
git clone <your-repo-url> national-parks-explorer
cd national-parks-explorer
```

### 2. Create and Populate `.env`
Copy `.env.example` and fill in real values.
```bash
cp .env.example .env
```

### 3. Install Dependencies
Use a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Start MySQL
If using Docker:
```bash
docker run --name parks-mysql -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=parksdb -p 3306:3306 -d mysql:8
```

### 5. Apply Schema
```bash
mysql -h 127.0.0.1 -u root -p parksdb < sql/schema.sql
```

### 6. Run Data Ingestion
Obtain an NPS API key: https://www.nps.gov/subjects/developer/api.htm  
Set `NPS_API_KEY` in `.env` then:
```bash
python backend/ingest.py --limit 50
```
Adjust or omit `--limit` for full load.

### 7. Launch Streamlit Frontend
```bash
streamlit run frontend/app.py
```
Multi‑page navigation appears in the sidebar.

### 8. Create a User (Example)
```bash
python -c "from backend.auth import create_user; create_user('demo','demo@example.com','ChangeMe123!')"
```

### 9. Development Notes
- `backend/models.py` includes optional SQLAlchemy stubs (disabled by default).
- Extend ingestion for campgrounds & amenities (TODO).
- Add favorites feature (TODO) via a new `favorite` table.
- Add API endpoints (TODO) if switching to Flask.

### 10. Testing (Basic Manual)
- Ensure parks populate: `SELECT COUNT(*) FROM park;`
- Verify activities: `SELECT COUNT(*) FROM activity;`
- Confirm user creation and session start on login (watch `user_session` table).

### 11. Future Enhancements (TODO)
- Full campground ingestion.
- User favorites.
- Role-based access.
- Detailed logging metadata enrichment.
- Flask REST API layer.

## Folder Structure
```
national-parks-explorer/
  [`README.md`](README.md )
  requirements.txt
  .env.example
  sql/schema.sql
  backend/
    __init__.py
    db.py
    models.py
    ingest.py
    auth.py
    utils.py
  frontend/
    app.py
    pages/
      search.py
      park_details.py
      activities_filter.py
      login.py
  demo/
    placeholder.txt
    notes.txt
```

## Troubleshooting
- MySQL auth plugin errors: ensure `mysql_native_password` or use root with proper password.
- Connection refused: confirm port mapping and container health.
- API key errors: verify `NPS_API_KEY` is valid and exported.

## License
TODO: Add a license file if open-sourcing.

Happy Exploring!
