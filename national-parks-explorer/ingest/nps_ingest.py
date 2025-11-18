from .db import get_connection
from .config import NPS_API_KEY
import requests

BASE_URL = "https://developer.nps.gov/api/v1"

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

    image_sql = """
      INSERT INTO IMAGE (park_id, url, alt_text, credit)
      VALUES (%s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        url = VALUES(url),
        alt_text = VALUES(alt_text),
        credit = VALUES(credit)
    """

    amenities_sql = """
      INSERT INTO AMENITY (amenity_id, park_id, name, description)
      VALUES (%s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        description = VALUES(description)
    """

    park_amenity_sql = """
      INSERT IGNORE INTO PARK_AMENITY (park_id, amenity_id)
      VALUES (%s, %s)
    """

    activity_sql = """
        INSERT INTO ACTIVITY (activity_id, name, description)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
          name = VALUES(name),
          description = VALUES(description)
    """
    park_activity_sql = """
      INSERT IGNORE INTO PARK_ACTIVITY (park_id, activity_id)
      VALUES (%s, %s)
    """

    try:
        for p in fetch_all_parks():
            park_id = p["id"]                
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
                # map state code to name could be improved with a lookup table
                cur.execute(state_sql, (code, None))
                cur.execute(park_state_sql, (park_id, code))


            # images
            for img in p.get("images", []):
                url = img.get("url")
                alt_text = img.get("altText")
                credit = img.get("credit")
                cur.execute(image_sql, (park_id, url, alt_text, credit))

            # amenities
            for amenity in p.get("amenities", []):
                amenity_id = amenity.get("id")
                amenity_name = amenity.get("name")
                amenity_desc = amenity.get("description")
                cur.execute(amenities_sql, (amenity_id, park_id, amenity_name, amenity_desc))
                cur.execute(park_amenity_sql, (park_id, amenity_id))

            # activities
            for activity in p.get("activities", []):
                activity_id = activity.get("id")
                activity_name = activity.get("name")
                activity_desc = activity.get("description")
                cur.execute(activity_sql, (activity_id, activity_name, activity_desc))
                cur.execute(park_activity_sql, (park_id, activity_id))
        conn.commit()
    finally:
        conn.close()


#Todo: implement the following functions
def fetch_park_alerts(park_id):
        pass
def ingest_park_alerts(park_id):
        #/alerts endpoint
        pass
def fetch_events(park_id):
        pass
def ingest_events(park_id):
        #/events endpoint
        # add events to a specific park for ingest park events
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
    ingest_trails()
    ingest_events()
    ingest_park_alerts()
