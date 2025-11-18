from .db import get_connection
from .config import NPS_API_KEY
import requests

BASE_URL = "https://developer.nps.gov/api/v1"
#* Parks
#* Activities
#* Campgrounds
#* Amenities
#* Events

def fetch_all_parks():
    params = {"api_key": NPS_API_KEY, "limit": 100}
    start = 0
    while True:
        params["start"] = start
        resp = requests.get(f"{BASE_URL}/parks", params=params)
        resp.raise_for_status()
        data = resp.json()
        parks = data.get("data", [])
        if not parks:
            break
        for park in parks:
            yield park
        start += len(parks)

def ingest_parks():
    conn = get_connection()
    cur = conn.cursor()

    park_sql = """
      INSERT INTO PARK (park_id, name, designation, description, latitude, longitude)
      VALUES (%s, %s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        designation = VALUES(designation),
        description = VALUES(description),
        latitude = VALUES(latitude),
        longitude = VALUES(longitude)
    """

    state_sql = """
      INSERT IGNORE INTO STATE (state_code, name)
      VALUES (%s, %s)
    """

    park_state_sql = """
      INSERT IGNORE INTO PARK_STATE (park_id, state_code)
      VALUES (%s, %s)
    """

    try:
        for p in fetch_all_parks():
            park_id = p["id"]                  # CHAR from NPS
            name = p.get("fullName")
            designation = p.get("designation")
            description = p.get("description")
            lat = float(p["latitude"]) if p.get("latitude") else None
            lon = float(p["longitude"]) if p.get("longitude") else None

            cur.execute(park_sql, (park_id, name, designation, description, lat, lon))

            # states string like "CO,UT"
            state_codes = (p.get("states") or "").split(",")
            for code in state_codes:
                code = code.strip()
                if not code:
                    continue
                # you can leave STATE.name NULL or map manually later
                cur.execute(state_sql, (code, None))
                cur.execute(park_state_sql, (park_id, code))

        conn.commit()
    finally:
        conn.close()


#Todo: implement the following functions
def ingest_states():
    pass
def fetch_state_parks(state_code):
     pass
def ingest_state_parks(state_code):
    pass

def fetch_park_activities(park_id):
     pass
def ingest_park_activities(park_id):
    pass
def ingest_amenities():
        #/amenities endpoint
        pass
def fetch_amenties():
        pass
def ingest_images():
        pass
def ingest_park_alerts(park_id):
        #/alerts endpoint
        pass
def fetch_events(park_id):
        pass
def ingest_events(park_id):
        #/events endpoint
        pass
def ingest_park_events(park_id):
        pass
def ingest_trails():
        #/places and /thingstodo endpoint
        # need to scrape for trails
        pass

def ingest_nps_all():
    """
    Convenience wrapper used by ingest_all.py
    """
    ingest_parks()
    ingest_states()
    ingest_park_activities()
    ingest_amenities()
    ingest_images()
    ingest_trails()
    ingest_events()
    ingest_state_parks()
    ingest_park_alerts()
