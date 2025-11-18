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
      INSERT INTO PARK (park_id, name, designation, description, park_code, latitude, longitude)
      VALUES (%s, %s, %s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        designation = VALUES(designation),
        description = VALUES(description),
        park_code = VALUES(park_code),
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
            park_code = p.get("parkCode")
            lat = float(p["latitude"]) if p.get("latitude") else None
            lon = float(p["longitude"]) if p.get("longitude") else None

            cur.execute(park_sql, (park_id, name, designation, description, park_code, lat, lon))

            # states string like "CO,UT"
            state_codes = (p.get("states") or "").split(",")
            for code in state_codes:
                code = code.strip()
                if not code:
                    continue
                cur.execute(state_sql, (code, state_map().get(code, "Unknown")))
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

def fetch_park_alerts():
    params = {"api_key": NPS_API_KEY, "limit": 100}
    start = 0
    while True:
        params["start"] = start
        resp = requests.get(f"{BASE_URL}/alerts", params=params)
        resp.raise_for_status()
        data = resp.json()
        parks = data.get("data", [])
        if not parks:
            break
        for park in parks:
            yield park
        start += len(parks)

def ingest_park_alerts(max_pages: int = 10):
    conn = get_connection()
    cur = conn.cursor()

    insert_sql = """
      INSERT INTO PARK_ALERT (alert_id, park_id, category, title, description, issued_at, expires_at)
      VALUES (%s, %s, %s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        category    = VALUES(category),
        title       = VALUES(title),
        description = VALUES(description),
        issued_at   = VALUES(issued_at),
        expires_at  = VALUES(expires_at)
    """

    page = 0
    start = 0

    while page < max_pages:
        params = {
            "api_key": NPS_API_KEY,
            "limit": 100,
            "start": start,
        }
        resp = requests.get(f"{BASE_URL}/alerts", params=params, timeout=15)

        if resp.status_code != 200:
            print("[ALERTS] NPS alerts request failed:", resp.status_code, resp.text[:200])
            break

        data = resp.json().get("data", [])
        if not data:
            break

        for alert in data:
            alert_id = alert.get("id")
            park_code = alert.get("parkCode")
            category = alert.get("category")
            title = alert.get("title")
            description = alert.get("description")
            issued_at = alert.get("lastIndexedDate")  # already ISO-like string
            expires_at = None  # NPS alerts don't usually include this; keep null for now

            if not alert_id or not park_code:
                continue

            # Look up internal park_id from park_code
            cur.execute(
                "SELECT park_id FROM PARK WHERE park_code = %s LIMIT 1",
                (park_code,),
            )
            row = cur.fetchone()
            if not row:
                # Park not in DB (maybe filtered out earlier) – skip this alert
                continue

            park_id = row[0]

            cur.execute(
                insert_sql,
                (alert_id, park_id, category, title, description, issued_at, expires_at),
            )

        conn.commit()

        # next page
        start += len(data)
        page += 1

    conn.close()

def state_map():
    return {
        "AL": "Alabama",
        "AK": "Alaska",
        "AZ": "Arizona",
        "AR": "Arkansas",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DE": "Delaware",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "IA": "Iowa",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "ME": "Maine",
        "MD": "Maryland",
        "MA": "Massachusetts",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MS": "Mississippi",
        "MO": "Missouri",
        "MT": "Montana",
        "NE": "Nebraska",
        "NV": "Nevada",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NY": "New York",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PA": "Pennsylvania",
        "RI": "Rhode Island",
        "SC":  "South Carolina",
        "SD":  "South Dakota",
        "TN":  "Tennessee",
        "TX":  "Texas",
        "UT":  "Utah",
        "VT":  "Vermont",
        "VA":  "Virginia",
        "WA":  "Washington",
        "WV":  "West Virginia",
        "WI":  "Wisconsin",
        "WY":  "Wyoming"
    }

#Todo: implement the following functions

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
