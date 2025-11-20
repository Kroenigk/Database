from .db import get_connection
from .config import NPS_API_KEY
import requests

BASE_URL = "https://developer.nps.gov/api/v1"

def _get_or_create_amenity(cur, name: str) -> int:
    """
    Get amenity_id for a given name, inserting if needed.

    AMENITY (
        amenity_id INT AUTO_INCREMENT PRIMARY KEY,
        name       VARCHAR(100) NOT NULL
    )
    """
    if not name:
        raise ValueError("Amenity name must be non-empty")

    cur.execute("SELECT amenity_id FROM AMENITY WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("INSERT INTO AMENITY (name) VALUES (%s)", (name,))
    return cur.lastrowid

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
        name        = VALUES(name),
        designation = VALUES(designation),
        description = VALUES(description),
        park_code   = VALUES(park_code),
        latitude    = VALUES(latitude),
        longitude   = VALUES(longitude)
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
        url      = VALUES(url),
        alt_text = VALUES(alt_text),
        credit   = VALUES(credit)
    """

    activity_sql = """
        INSERT INTO ACTIVITY (activity_id, name, description)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
          name        = VALUES(name),
          description = VALUES(description)
    """

    park_activity_sql = """
      INSERT IGNORE INTO PARK_ACTIVITY (park_id, activity_id)
      VALUES (%s, %s)
    """

    park_amenity_link_sql = """
      INSERT IGNORE INTO PARK_AMENITY (park_id, amenity_id)
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

            cur.execute(
                park_sql,
                (park_id, name, designation, description, park_code, lat, lon),
            )

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
                if not url:
                    continue
                cur.execute(image_sql, (park_id, url, alt_text, credit))

            # activities (NPS parks)
            for activity in p.get("activities", []):
                activity_id = activity.get("id")
                activity_name = activity.get("name")
                activity_desc = activity.get("description")
                if not activity_id or not activity_name:
                    continue
                cur.execute(activity_sql, (activity_id, activity_name, activity_desc))
                cur.execute(park_activity_sql, (park_id, activity_id))

        
            for amenity in p.get("amenities", []):
                amenity_name = amenity.get("name") or amenity.get("value")
                if not amenity_name:
                    continue
                amenity_id = _get_or_create_amenity(cur, amenity_name)
                cur.execute(park_amenity_link_sql, (park_id, amenity_id))

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

def fetch_campgrounds(park_code: str | None = None):
    """
    Generator for NPS /campgrounds endpoint.

    If park_code is given, filters campgrounds by that parkCode.
    Otherwise, returns all campgrounds.
    """
    params = {"api_key": NPS_API_KEY, "limit": 100}
    if park_code:
        params["parkCode"] = park_code

    start = 0
    while True:
        params["start"] = start
        resp = requests.get(f"{BASE_URL}/campgrounds", params=params)
        resp.raise_for_status()
        data = resp.json()
        campgrounds = data.get("data", [])
        if not campgrounds:
            break
        for cg in campgrounds:
            yield cg
        start += len(campgrounds)


def _extract_campground_amenity_names(cg: dict) -> set[str]:
    """
    Take the NPS campground 'amenities' object and flatten it
    into a set of human-readable amenity names.

    The exact shape can vary; this is intentionally conservative.
    """
    result: set[str] = set()
    amenities = cg.get("amenities") or {}

    for key, value in amenities.items():
        # strings like "Yes", "Flush Toilets", "No"
        if isinstance(value, str):
            v = value.strip()
            if v and v.lower() not in {"no", "none", "n/a"}:
                result.add(v)

        # lists of strings like ["Flush Toilets", "Vault Toilets"]
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    continue
                v = item.strip()
                if v and v.lower() not in {"no", "none", "n/a"}:
                    result.add(v)

        # dicts can be ignored or handled specially if you discover them

    return result


def ingest_campgrounds(park_code: str | None = None):
    """
    Ingest NPS campgrounds into CAMPGROUND and CAMPGROUND_AMENITY.

    CAMPGROUND (
        campground_id INT AUTO_INCREMENT PRIMARY KEY,
        park_id       CHAR(36)     NOT NULL,
        name          VARCHAR(150) NOT NULL,
        description   TEXT,
        latitude      DECIMAL(9,6),
        longitude     DECIMAL(9,6)
    )

    Strategy:
      - Use NPS /campgrounds (optionally filtered by parkCode).
      - For each campground:
          * Map NPS parkCode -> internal PARK.park_id
          * Upsert CAMPGROUND using (park_id, name) as logical key
          * Extract amenity names and link via CAMPGROUND_AMENITY
    """
    conn = get_connection()
    cur = conn.cursor()

    # Preload park_code -> park_id mapping to avoid constant SELECTs
    cur.execute("SELECT park_id, park_code FROM PARK WHERE park_code IS NOT NULL")
    park_by_code = {row[1]: row[0] for row in cur.fetchall() if row[1]}

    campground_select_sql = """
        SELECT campground_id
        FROM CAMPGROUND
        WHERE park_id = %s AND name = %s
        LIMIT 1
    """

    campground_insert_sql = """
        INSERT INTO CAMPGROUND (park_id, name, description, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
    """

    campground_update_sql = """
        UPDATE CAMPGROUND
        SET description = %s,
            latitude    = %s,
            longitude   = %s
        WHERE campground_id = %s
    """

    link_sql = """
        INSERT IGNORE INTO CAMPGROUND_AMENITY (campground_id, amenity_id)
        VALUES (%s, %s)
    """

    try:
        cg_iter = fetch_campgrounds(park_code)

        for cg in cg_iter:
            cg_name = cg.get("name")
            cg_desc = cg.get("description")
            cg_lat = float(cg["latitude"]) if cg.get("latitude") else None
            cg_lon = float(cg["longitude"]) if cg.get("longitude") else None

            cg_park_code = cg.get("parkCode")
            if not cg_name or not cg_park_code:
                continue

            park_id = park_by_code.get(cg_park_code)
            if not park_id:
                # Park for this campground not in DB – skip
                continue

            # Upsert CAMPGROUND by (park_id, name)
            cur.execute(campground_select_sql, (park_id, cg_name))
            row = cur.fetchone()
            if row:
                campground_id = row[0]
                cur.execute(
                    campground_update_sql,
                    (cg_desc, cg_lat, cg_lon, campground_id),
                )
            else:
                cur.execute(
                    campground_insert_sql,
                    (park_id, cg_name, cg_desc, cg_lat, cg_lon),
                )
                campground_id = cur.lastrowid

            # Amenities
            amenity_names = _extract_campground_amenity_names(cg)
            for a_name in amenity_names:
                amenity_id = _get_or_create_amenity(cur, a_name)
                cur.execute(link_sql, (campground_id, amenity_id))

        conn.commit()
        print("NPS: campgrounds ingested.")
    finally:
        conn.close()
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
    ingest_campgrounds()
    ingest_trails()
    ingest_park_alerts()
