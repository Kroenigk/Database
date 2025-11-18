import os
from dotenv import load_dotenv

load_dotenv()

NPS_API_KEY = os.getenv("NPS_API_KEY")
RIDB_API_KEY = os.getenv("RIDB_API_KEY")
NOAA_API_TOKEN = os.getenv("NOAA_API_TOKEN")
USGS_BASE_URL = os.getenv("USGS_BASE_URL")
NOAA_BASE_URL = os.getenv("NOAA_BASE_URL")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "national_parks_db"),
}
