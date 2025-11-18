import requests
from .config import RIDB_API_KEY
from .db import get_connection

BASE_URL = "https://ridb.recreation.gov/api/v1"

def fetch_all_facilities():
    params = {"apikey": RIDB_API_KEY, "limit": 50, "offset": 0}
    while True:
        resp = requests.get(f"{BASE_URL}/facilities", params=params)
        resp.raise_for_status()
        data = resp.json()
        recs = data.get("RECDATA", [])
        if not recs:
            break
        for r in recs:
            yield r
        params["offset"] += len(recs)

def ingest_facilities():
    conn = get_connection()
    cur = conn.cursor()

    facility_sql = """
      INSERT INTO FACILITY (facility_id, park_id, name, type)
      VALUES (%s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        type = VALUES(type)
    """

    try:
        for fac in fetch_all_facilities():
            fac_id = fac["FacilityID"]
            name = fac.get("FacilityName")
            fac_type = fac.get("FacilityTypeDescription")
            # You might map to a PARK by proximity or manual mapping; placeholder None for now
            park_id = None

            cur.execute(facility_sql, (fac_id, park_id, name, fac_type))
        conn.commit()
    finally:
        conn.close()
