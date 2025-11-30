from backend.db import get_connection
from backend.config import (NPS_API_KEY, NPS_BASE_URL)
import requests
import time
import re  

BASE_URL = NPS_BASE_URL

# Only ingest the 63 primary U.S. National Parks
MAIN_PARK_CODES: set[str] = {
    "acad","npsa","arch","badl","bibe","bisc","blca","brca","cany","care",
    "cave","chis","cong","crla","cuva","deva","dena","drto","ever","gaar",
    "jeff","glac","glba","grca","grte","grba","grsa","grsm","gumo","hale",
    "havo","hosp","indu","isro","jotr","katm","kefj","kova","lacl","lavo",
    "maca","meve","mora","neri","noca","olym","pefo","pinn","redw","romo",
    "sagu","seki","shen","thro","viis","voya","whsa","wica","wrst","yell",
    "yose","zion"
}

MAX_RETRY_AFTER_SECONDS = 10

# -------------------------
# NPS API helpers
# This helps handle rate limiting (429) with backoff.
# ---------
def _nps_get(path: str, params: dict, max_retries: int = 5):
    url = f"{BASE_URL}/{path.lstrip('/')}"
    params = {**params, "api_key": NPS_API_KEY}

    last_status = None

    for attempt in range(max_retries):
        resp = requests.get(url, params=params, timeout=15)
        last_status = resp.status_code

        if resp.status_code == 200:
            return resp

        if resp.status_code == 429:
            raw = resp.headers.get("Retry-After")
            try:
                delay_val = int(raw) if raw else 5 + attempt * 2
            except ValueError:
                delay_val = 5
            delay = min(delay_val, MAX_RETRY_AFTER_SECONDS)
            print(f"[NPS] 429 on {path}, sleeping {delay}s...")
            time.sleep(delay)
            continue

        resp.raise_for_status()

    raise RuntimeError(f"NPS request failed after retries: {url} (last={last_status})")

# -------------------------
# PARKS
# ------------------------
def fetch_all_parks():
    """
    Fetch all parks from NPS; filtered later to only MAIN_PARK_CODES.
    """
    params = {"limit": 100}
    start = 0

    while True:
        params["start"] = start
        resp = _nps_get("parks", params)
        data = resp.json().get("data", [])
        if not data:
            break
        for park in data:
            yield park
        start += len(data)


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

    state_sql = "INSERT IGNORE INTO STATE (state_code, name) VALUES (%s, %s)"
    park_state_sql = "INSERT IGNORE INTO PARK_STATE (park_id, state_code) VALUES (%s, %s)"

    image_sql = """
      INSERT INTO IMAGE (park_id, url, alt_text, credit)
      VALUES (%s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE url=VALUES(url), alt_text=VALUES(alt_text), credit=VALUES(credit)
    """

    activity_sql = """
      INSERT INTO ACTIVITY (activity_id, name, description)
      VALUES (%s, %s, %s)
      ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description)
    """

    park_activity_sql = "INSERT IGNORE INTO PARK_ACTIVITY (park_id, activity_id) VALUES (%s, %s)"

    try:
        for p in fetch_all_parks():
            park_id = p["id"]
            name = p.get("fullName")
            designation = p.get("designation") or ""
            description = p.get("description")
            park_code_raw = p.get("parkCode") or ""
            park_code = park_code_raw.strip().lower()
            lat = float(p["latitude"]) if p.get("latitude") else None
            lon = float(p["longitude"]) if p.get("longitude") else None

            # Only ingest main 63 parks
            if park_code not in MAIN_PARK_CODES:
                continue

            cur.execute(
                park_sql,
                (park_id, name, designation, description, park_code, lat, lon),
            )

            # Parse state list
            for code in (p.get("states") or "").split(","):
                code = code.strip()
                if code:
                    cur.execute(state_sql, (code, state_map().get(code, "Unknown")))
                    cur.execute(park_state_sql, (park_id, code))

            # images
            for img in p.get("images", []):
                url = img.get("url")
                if url:
                    cur.execute(
                        image_sql,
                        (park_id, url, img.get("altText"), img.get("credit")),
                    )

            # activities
            for act in p.get("activities", []):
                act_id = act.get("id")
                act_name = act.get("name")
                if act_id and act_name:
                    cur.execute(activity_sql, (act_id, act_name, act.get("description")))
                    cur.execute(park_activity_sql, (park_id, act_id))

        conn.commit()
        print("NPS: parks ingested.")
    finally:
        conn.close()


# -------------------------
# PARK ALERTS
# -------------------------

def fetch_park_alerts_page(start: int):
    """Alert fetcher now uses _nps_get."""
    params = {"limit": 100, "start": start}
    resp = _nps_get("alerts", params)
    return resp.json().get("data", [])


def ingest_park_alerts(max_pages: int = 100):
    conn = get_connection()
    cur = conn.cursor()

    insert_sql = """
      INSERT INTO PARK_ALERT (alert_id, park_id, category, title, description, issued_at, expires_at)
      VALUES (%s, %s, %s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE category=VALUES(category), title=VALUES(title),
          description=VALUES(description), issued_at=VALUES(issued_at), expires_at=VALUES(expires_at)
    """

    cur.execute("SELECT park_id, park_code FROM PARK")
    code_to_id = {code.lower(): pid for (pid, code) in cur.fetchall() if code}

    start = 0
    page = 0

    try:
        while page < max_pages:
            alerts = fetch_park_alerts_page(start)
            if not alerts:
                break

            for alert in alerts:
                alert_id = alert.get("id")
                raw_code = alert.get("parkCode") or ""
                park_code = raw_code.strip().lower()

                if not alert_id or not park_code:
                    continue

                park_id = code_to_id.get(park_code)
                if not park_id:
                    continue  # alert for park we do not ingest

                cur.execute(
                    insert_sql,
                    (
                        alert_id,
                        park_id,
                        alert.get("category"),
                        alert.get("title"),
                        alert.get("description"),
                        alert.get("lastIndexedDate"),
                        None,
                    ),
                )

            conn.commit()
            start += len(alerts)
            page += 1

        print("NPS: park alerts ingested.")
    finally:
        conn.close()

# This allows looking up full state names from codes.
def state_map():
    return {
        "AL": "Alabama","AK": "Alaska","AZ": "Arizona","AR": "Arkansas","CA": "California",
        "CO": "Colorado","CT": "Connecticut","DE": "Delaware","FL": "Florida","GA": "Georgia",
        "HI": "Hawaii","ID": "Idaho","IL": "Illinois","IN": "Indiana","IA": "Iowa","KS": "Kansas",
        "KY": "Kentucky","LA": "Louisiana","ME": "Maine","MD": "Maryland","MA": "Massachusetts",
        "MI": "Michigan","MN": "Minnesota","MS": "Mississippi","MO": "Missouri","MT": "Montana",
        "NE": "Nebraska","NV": "Nevada","NH": "New Hampshire","NJ": "New Jersey","NM": "New Mexico",
        "NY": "New York","NC": "North Carolina","ND": "North Dakota","OH": "Ohio","OK": "Oklahoma",
        "OR": "Oregon","PA": "Pennsylvania","RI": "Rhode Island","SC": "South Carolina",
        "SD": "South Dakota","TN": "Tennessee","TX": "Texas","UT": "Utah","VT": "Vermont",
        "VA": "Virginia","VI": "Virgin Islands" "WA": "Washington","WV": "West Virginia","WI": "Wisconsin","WY": "Wyoming"
    }

# -------------------------
# CAMPGROUNDS AND CAMPING AMENITIES
# -------------------------

def fetch_campgrounds(park_code: str | None = None):
    params = {"limit": 100}
    if park_code:
        params["parkCode"] = park_code

    start = 0
    while True:
        params["start"] = start
        resp = _nps_get("campgrounds", params)
        data = resp.json().get("data", [])
        if not data:
            break
        for cg in data:
            yield cg
        start += len(data)

# Helper to extract amenity names from campground record
def _extract_campground_amenity_names(cg: dict) -> set[str]:
    res = set()
    for key, value in (cg.get("amenities") or {}).items():
        if isinstance(value, str):
            v = value.strip()
            if v and v.lower() not in {"no", "none", "n/a"}:
                res.add(v)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    v = item.strip()
                    if v and v.lower() not in {"no", "none", "n/a"}:
                        res.add(v)
    return res


def ingest_campgrounds(park_code: str | None = None):
    conn = get_connection()
    cur = conn.cursor()

    # Lowercase map
    cur.execute("SELECT park_id, park_code FROM PARK WHERE park_code IS NOT NULL")
    park_by_code = {code.lower(): pid for (pid, code) in cur.fetchall() if code}

    campground_select_sql = """
        SELECT campground_id FROM CAMPGROUND
        WHERE park_id = %s AND name = %s LIMIT 1
    """
    campground_insert_sql = """
        INSERT INTO CAMPGROUND (park_id, name, description, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
    """
    campground_update_sql = """
        UPDATE CAMPGROUND
        SET description=%s, latitude=%s, longitude=%s
        WHERE campground_id=%s
    """
    link_sql = """
        INSERT IGNORE INTO CAMPGROUND_AMENITY (campground_id, amenity_id)
        VALUES (%s, %s)
    """

    try:
        for cg in fetch_campgrounds(park_code):
            cg_name = cg.get("name")
            raw_code = cg.get("parkCode")
            if not cg_name or not raw_code:
                continue

            cg_code = raw_code.strip().lower()
            park_id = park_by_code.get(cg_code)
            if not park_id:
                continue

            cg_desc = cg.get("description")
            cg_lat = float(cg["latitude"]) if cg.get("latitude") else None
            cg_lon = float(cg["longitude"]) if cg.get("longitude") else None

            cur.execute(campground_select_sql, (park_id, cg_name))
            row = cur.fetchone()
            if row:
                cg_id = row[0]
                cur.execute(campground_update_sql, (cg_desc, cg_lat, cg_lon, cg_id))
            else:
                cur.execute(
                    campground_insert_sql,
                    (park_id, cg_name, cg_desc, cg_lat, cg_lon),
                )
                cg_id = cur.lastrowid

            for name in _extract_campground_amenity_names(cg):
                a_id = _get_or_create_amenity(cur, name)
                cur.execute(link_sql, (cg_id, a_id))

        conn.commit()
        print("NPS: campgrounds ingested.")
    finally:
        conn.close()


# -------------------------
# EVENTS
# -------------------------

def fetch_events_for_park(park_code: str):
    start = 0
    limit = 50

    while True:
        params = {"parkCode": park_code, "limit": limit, "start": start}
        resp = _nps_get("events", params)
        data = resp.json().get("data", [])
        if not data:
            break
        for ev in data:
            yield ev
        start += len(data)
        time.sleep(0.2)


def _parse_event_datetimes(ev: dict):
    d1 = ev.get("dateStart") or ev.get("datestart")
    d2 = ev.get("dateEnd") or ev.get("dateend")
    t1 = ev.get("timeStart") or ev.get("timestart")
    t2 = ev.get("timeEnd") or ev.get("timeend")

    def combo(d, t): return None if not d else f"{d} {t or '00:00:00'}"
    return combo(d1, t1), combo(d2, t2)

# This extracts park IDs from event records.
def _extract_event_park_ids(ev: dict) -> list[str]:
    ids = []

    pid = ev.get("parkId") or ev.get("parkid")
    if isinstance(pid, str) and pid.strip():
        ids.append(pid.strip())

    parks = ev.get("parks") or ev.get("park") or []
    if isinstance(parks, list):
        for p in parks:
            if isinstance(p, dict):
                pid2 = p.get("parkId") or p.get("id")
                if isinstance(pid2, str) and pid2.strip():
                    ids.append(pid2.strip())

    seen = set()
    out = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out

def ingest_events():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT park_id FROM PARK")
    valid_ids = {pid.strip() for (pid,) in cur.fetchall() if pid}

    insert_sql = """
        INSERT INTO EVENT (event_id, park_id, title, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            park_id=VALUES(park_id),
            title=VALUES(title),
            start_time=VALUES(start_time),
            end_time=VALUES(end_time)
    """

    # get list of lower-case park_codes
    cur.execute("SELECT DISTINCT park_code FROM PARK WHERE park_code IS NOT NULL")
    park_codes = [code.lower().strip() for (code,) in cur.fetchall() if code]

    seen = set()

    try:
        for code in park_codes:
            print(f"[NPS] Fetching events for parkCode={code}...")
            for ev in fetch_events_for_park(code):

                eid = ev.get("id")
                if not eid or eid in seen:
                    continue
                seen.add(eid)

                title = ev.get("title") or "Untitled event"

                park_ids = _extract_event_park_ids(ev)
                park_fk = next((pid for pid in park_ids if pid in valid_ids), None)
                if not park_fk:
                    continue

                sdt, edt = _parse_event_datetimes(ev)

                cur.execute(insert_sql, (eid, park_fk, title, sdt, edt))

            time.sleep(0.5)

        conn.commit()
        print("NPS: events ingested.")
    finally:
        conn.close()

# -------------------------
# AMENITIES
# -------------------------

# Fetch places for park and yield those with amenities
def fetch_amenities_for_park(park_code: str):
    for place in fetch_places_for_park(park_code):
        amenities = place.get("amenities") or []
        if isinstance(amenities, list) and amenities:
            yield place

# Helper to get or create AMENITY row
def _get_or_create_amenity(cur, name: str) -> int:
    """Get or create AMENITY row; return amenity_id."""
    select_sql = "SELECT amenity_id FROM AMENITY WHERE name = %s LIMIT 1"
    insert_sql = "INSERT INTO AMENITY (name) VALUES (%s)"

    cur.execute(select_sql, (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(insert_sql, (name,))
    return cur.lastrowid

def ingest_park_amenities():
    """
    Ingest amenities into AMENITY and PARK_AMENITY using /places.

    AMENITY (
        amenity_id INT AUTO_INCREMENT PRIMARY KEY,
        name       VARCHAR(100) NOT NULL
    )

    PARK_AMENITY (
        park_id    CHAR(36) NOT NULL,
        amenity_id INT      NOT NULL,
        PRIMARY KEY (park_id, amenity_id)
    )
    """
    conn = get_connection()
    cur = conn.cursor()

    # Build park_code -> park_id map for all parks currently in DB
    cur.execute("SELECT park_id, park_code FROM PARK WHERE park_code IS NOT NULL")
    code_to_id: dict[str, str] = {}
    for park_id, park_code in cur.fetchall():
        if park_code:
            code_to_id[park_code.lower().strip()] = park_id

    link_sql = """
        INSERT IGNORE INTO PARK_AMENITY (park_id, amenity_id)
        VALUES (%s, %s)
    """

    seen_links: set[tuple[str, int]] = set()

    try:
        for park_code, park_id in code_to_id.items():
            print(f"[NPS] Fetching amenities via /places for parkCode={park_code}...")

            for place in fetch_amenities_for_park(park_code):
                amenities = place.get("amenities") or []
                if not isinstance(amenities, list):
                    continue

                for raw_name in amenities:
                    if not isinstance(raw_name, str):
                        continue
                    name = raw_name.strip()
                    if not name:
                        continue

                    # Create or look up amenity row
                    amenity_id = _get_or_create_amenity(cur, name)

                    key = (park_id, amenity_id)
                    if key in seen_links:
                        continue
                    seen_links.add(key)

                    cur.execute(link_sql, (park_id, amenity_id))

            # tiny pause between parks
            time.sleep(0.2)

        conn.commit()
        print("NPS: amenities ingested into AMENITY and PARK_AMENITY via /places.")
    finally:
        conn.close()
     

# -------------------------
# TRAILS
# -------------------------

# Fetch places for park
def fetch_places_for_park(park_code: str):
    start = 0
    limit = 50
    while True:
        params = {"parkCode": park_code, "limit": limit, "start": start}
        resp = _nps_get("places", params)
        data = resp.json().get("data", [])
        if not data:
            break
        for rec in data:
            yield rec
        start += len(data)
        time.sleep(0.15)

# Fetch things to do for park
def fetch_things_to_do_for_park(park_code: str):
    start = 0
    limit = 50
    while True:
        params = {"parkCode": park_code, "limit": limit, "start": start}
        resp = _nps_get("thingstodo", params)
        data = resp.json().get("data", [])
        if not data:
            break
        for rec in data:
            yield rec
        start += len(data)
        time.sleep(0.15)

# Helper to get text fields for trail analysis
def _get_text_fields(rec: dict) -> str:
    return " ".join([
        rec.get("title") or "",
        rec.get("listingDescription") or "",
        rec.get("shortDescription") or "",
        rec.get("description") or "",
    ])

# Helper to determine if record looks like a trail
def _looks_like_trail(rec: dict) -> bool:
    text = _get_text_fields(rec).lower()
    for word in ["trail", "hike", "loop", "walk", "path"]:
        if word in text:
            return True
    return False


# Helper to extract difficulty level from trail record
def _extract_difficulty(rec: dict) -> str | None:
    text = _get_text_fields(rec).lower()
    if "easy" in text:
        return "easy"
    if "moderate" in text:
        return "moderate"
    if "strenuous" in text:
        return "strenuous"
    if "difficult" in text:
        return "difficult"
    return None

# Helper to extract length in miles from trail record
def _extract_length_miles(rec: dict) -> float | None:
    text = _get_text_fields(rec).lower()
    m = re.search(r"(\d+(\.\d+)?)\s*(mile|miles|mi)\b", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def ingest_trails():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT park_id, park_code FROM PARK WHERE park_code IS NOT NULL")
    code_to_id = {code.lower(): pid for (pid, code) in cur.fetchall() if code}

    insert_sql = """
        INSERT INTO TRAIL (park_id, name, length_miles, difficulty)
        VALUES (%s, %s, %s, %s)
    """

    seen = set()

    def process(rec: dict, park_id: str):
        name = (rec.get("title") or rec.get("name") or "").strip()
        if not name:
            return
        if not _looks_like_trail(rec):
            return

        length = _extract_length_miles(rec)
        diff = _extract_difficulty(rec)

        key = (park_id, name.lower())
        if key in seen:
            return
        seen.add(key)

        cur.execute(insert_sql, (park_id, name, length, diff))

    try:
        for code, park_id in code_to_id.items():
            print(f"[NPS] Fetching trails for parkCode={code}...")

            for place in fetch_places_for_park(code):
                process(place, park_id)

            for todo in fetch_things_to_do_for_park(code):
                process(todo, park_id)

            time.sleep(0.5)

        conn.commit()
        print("NPS: trails ingested.")
    finally:
        conn.close()


# -------------------------
# Public entrypoint for ingest_all.py
# -------------------------
def ingest_nps_all():
    ingest_parks()
    ingest_campgrounds()
    ingest_park_amenities()
    ingest_trails()
    ingest_park_alerts()
    ingest_events()
