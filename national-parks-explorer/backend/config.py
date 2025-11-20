import os
from dotenv import load_dotenv

load_dotenv()

NPS_API_KEY = os.getenv("NPS_API_KEY", "")
RIDB_API_KEY = os.getenv("RIDB_API_KEY", "")
NOAA_API_TOKEN = os.getenv("NOAA_API_TOKEN", "")

RIDB_BASE_URL = os.getenv("RIDB_BASE_URL", "https://ridb.recreation.gov/api/v1")
USGS_BASE_URL = os.getenv("USGS_BASE_URL", "https://earthquake.usgs.gov/fdsnws/event/1/query")
NOAA_BASE_URL = os.getenv("NOAA_BASE_URL", "https://www.ncdc.noaa.gov/cdo-web/api/v2")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "national_parks_db"),
    "charset": "utf8mb4",
}

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me")
