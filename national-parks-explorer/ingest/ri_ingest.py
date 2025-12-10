from requests.exceptions import HTTPError
import requests
from backend.db import get_connection
from backend.config import RIDB_API_KEY, RIDB_BASE_URL

from typing import Iterable, Dict, Any, List, Optional, Tuple
from urllib.parse import quote
from unicodedata import normalize
import logging
import time

#python -m ingest.ri_ingest

# --------------------------------------------------------------------
# Logging configuration
# --------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

HEADERS = {"apikey": RIDB_API_KEY}

# --------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------

def _fetch_paginated(
    endpoint: str,
    params: Dict[str, Any] | None = None,
    max_retries: int = 5,
    max_records: int | None = None
) -> Iterable[Dict[str, Any]]:
    if params is None:
        params = {}

    params = {**params}
    params.setdefault("limit", 50)
    params.setdefault("offset", 0)

    yielded = 0

    while True:
        retries = 0
        while retries <= max_retries:
            try:
                resp = requests.get(f"{RIDB_BASE_URL}/{endpoint}", headers=HEADERS, params=params)
                resp.raise_for_status()
                break
            except HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait_time = 2 ** retries
                    logging.warning(f"Rate limited on endpoint {endpoint} (attempt {retries+1}/{max_retries}). Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    retries += 1
                    continue
                raise
        else:
            logging.error(f"Max retries exceeded for endpoint {endpoint}. Stopping pagination.")
            break

        data = resp.json()
        records = data.get("RECDATA") or data.get("recdata") or []
        if not records:
            break

        for rec in records:
            yield rec
            yielded += 1
            if max_records is not None and yielded >= max_records:
                return

        meta = data.get("METADATA", {})
        results_meta = meta.get("RESULTS", {})
        total = results_meta.get("TOTALCOUNT")
        current = results_meta.get("CURRENTCOUNT") or len(records)
        offset = results_meta.get("OFFSET", params.get("offset", 0))

        if total is not None and offset + current >= total:
            break

        params["offset"] = offset + current
        if current == 0 or current < params["limit"]:
            break


def _fetch_facility_subresource(facility_id: str, subresource: str, params=None, max_records: int | None = None):
    safe_id = normalize("NFKC", str(facility_id)).strip()
    endpoint = f"facilities/{quote(safe_id)}/{subresource}"

    try:
        yield from _fetch_paginated(endpoint, params=params, max_records=max_records)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            logging.warning(f"Facility {facility_id} has no subresource '{subresource}' (404). Skipping.")
            return
        raise

def _safe_get(rec: Dict[str, Any], *keys: str, default=None) -> Any:
    for k in keys:
        if k in rec:
            return rec[k]
    return default

# --------------------------------------------------------------------
# Park helpers
# --------------------------------------------------------------------

def _load_parks(conn) -> List[Tuple[str, float, float]]:
    with conn.cursor() as cur:
        cur.execute("SELECT park_id, latitude, longitude FROM PARK WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        parks = [(park_id, float(lat), float(lon)) for park_id, lat, lon in cur.fetchall() if lat is not None and lon is not None]
    return parks

def _find_nearest_park(lat: Optional[float], lon: Optional[float], parks: List[Tuple[str, float, float]]) -> Optional[str]:
    if lat is None or lon is None or not parks:
        return None
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None

    best_park_id = None
    best_d2 = None
    for park_id, p_lat, p_lon in parks:
        d2 = (lat_f - p_lat) ** 2 + (lon_f - p_lon) ** 2
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best_park_id = park_id
    return best_park_id

# --------------------------------------------------------------------
# FACILITY ingest
# --------------------------------------------------------------------

def ingest_facilities(max_records=1000):
    logging.info("Starting ingestion of FACILITY table...")
    sql = """
        INSERT INTO FACILITY (facility_id, park_id, name, type)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            park_id = VALUES(park_id),
            name    = VALUES(name),
            type    = VALUES(type)
    """

    try:
        conn = get_connection()
        cursor = conn.cursor()
        parks = _load_parks(conn)
        inserted_count = 0

        facilities = _fetch_paginated("facilities", max_records=max_records)
        for fac in facilities:
            facility_id = str(fac.get("FacilityID"))
            name = _safe_get(fac, "FacilityName")
            if not name:
                logging.warning(f"Skipping facility {facility_id} because name is missing.")
                continue

            fac_type = _safe_get(fac, "FacilityTypeDescription")
            lat = _safe_get(fac, "FacilityLatitude")
            lon = _safe_get(fac, "FacilityLongitude")
            park_id = _find_nearest_park(lat, lon, parks)

            try:
                cursor.execute(sql, (facility_id, park_id, name, fac_type))
                inserted_count += 1
            except Exception as e:
                logging.error(f"Failed to insert facility {facility_id}: {e}")

        conn.commit()
        logging.info(f"FACILITY ingestion complete. Total inserted: {inserted_count}")

    except Exception as e:
        conn.rollback()
        logging.error(f"FACILITY ingestion failed, transaction rolled back: {e}")

    finally:
        cursor.close()
        conn.close()

# --------------------------------------------------------------------
# ACTIVITY + FACILITY_ACTIVITY ingest
# --------------------------------------------------------------------

def ingest_facility_activities(max_activities: int = 1000, batch_size: int = 300) -> None:
    """
    Populate ACTIVITY and FACILITY_ACTIVITY from RIDB.

    ACTIVITY (
        activity_id VARCHAR(50) PRIMARY KEY,
        name        VARCHAR(100) NOT NULL,
        description TEXT
    )

    FACILITY_ACTIVITY (
        facility_id CHAR(36) NOT NULL,
        activity_id VARCHAR(50) NOT NULL,
        PRIMARY KEY (facility_id, activity_id)
    )

    - Paginates through facilities from RIDB.
    - For each facility, fetches /facilities/{id}/activities with retry.
    - Upserts ACTIVITY rows.
    - Inserts FACILITY_ACTIVITY rows (ignoring duplicates).
    """

    conn = get_connection()
    cur = conn.cursor()

    activity_upsert_sql = """
        INSERT INTO ACTIVITY (activity_id, name, description)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name        = VALUES(name),
            description = COALESCE(ACTIVITY.description, VALUES(description))
    """

    facility_activity_upsert_sql = """
        INSERT IGNORE INTO FACILITY_ACTIVITY (facility_id, activity_id)
        VALUES (%s, %s)
    """

    offset = 0
    processed = 0

    try:
        while processed < max_activities:
            limit = min(batch_size, max_activities - processed)
            # Fetch a batch of facilities from RIDB
            url = f"{RIDB_BASE_URL}/facilities"
            params = {
                "limit": limit,
                "offset": offset,
                "apikey": RIDB_API_KEY,
            }

            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
            except requests.RequestException as e:
                logging.warning(f"Failed to fetch facilities batch at offset {offset}: {e}")
                break  # stop processing if the facilities call fails

            facilities = response.json().get("RECDATA", [])
            if not facilities:
                break  # no more data

            for facility in facilities:
                facility_id = facility.get("FacilityID")
                if not facility_id:
                    continue

                activity_url = f"{RIDB_BASE_URL}/facilities/{facility_id}/activities"
                activity_params = {"apikey": RIDB_API_KEY}

                # Retry logic for each facility's activities
                activities = []
                for attempt in range(3):
                    try:
                        activity_resp = requests.get(activity_url, params=activity_params, timeout=5)
                        if activity_resp.status_code == 404:
                            logging.warning(f"Facility {facility_id} not found. Skipping.")
                            activities = []
                            break
                        activity_resp.raise_for_status()
                        activities = activity_resp.json().get("RECDATA", [])
                        break  # success
                    except requests.RequestException as e:
                        if attempt < 2:
                            time.sleep(1)  # brief backoff then retry
                        else:
                            logging.warning(
                                f"Failed to fetch activities for facility {facility_id} "
                                f"after 3 attempts. Skipping. Error: {e}"
                            )
                            activities = []

                # Insert ACTIVITY + FACILITY_ACTIVITY
                for act in activities:
                    ridb_act_id = act.get("ActivityID")
                    name = act.get("ActivityName")
                    desc = act.get("ActivityDescription")

                    if not ridb_act_id or not name:
                        continue

                    activity_id = str(ridb_act_id)

                    try:
                        # Upsert into ACTIVITY
                        cur.execute(activity_upsert_sql, (activity_id, name, desc))
                        # Link facility to activity
                        cur.execute(facility_activity_upsert_sql, (facility_id, activity_id))
                    except Exception as e:
                        logging.warning(
                            f"Failed to insert activity {activity_id} for facility {facility_id}: {e}"
                        )
                        continue

                processed += 1

            conn.commit()
            offset += limit

        print(f"RIDB: activities + facility activities ingested for {processed} facilities.")

    finally:
        cur.close()
        conn.close()

# --------------------------------------------------------------------
# FEE
# --------------------------------------------------------------------

def ingest_fees(max_records=330, batch_size=50):
    """
    Insert fee descriptions for each facility.
    - Process facilities in batches for efficiency.
    - Retry API requests up to 3 times for transient errors.
    - Skip facilities that fail or have no fee data.
    """
    logging.info("Starting FEE ingestion...")

    conn = get_connection()
    cur = conn.cursor()

    # Get facility IDs (limit optional)
    if max_records:
        cur.execute("SELECT facility_id FROM FACILITY LIMIT %s", (max_records,))
    else:
        cur.execute("SELECT facility_id FROM FACILITY")

    facilities = cur.fetchall()
    total_inserted = 0

    insert_sql = """
        INSERT INTO FEE (facility_id, description, fee_type)
        VALUES (%s, %s, %s)
    """

    # Process in batches
    for i in range(0, len(facilities), batch_size):
        batch = facilities[i:i + batch_size]

        for (facility_id,) in batch:
            url = f"{RIDB_BASE_URL}/facilities/{facility_id}"

            # Retry logic
            for attempt in range(3):
                try:
                    r = requests.get(url, headers=HEADERS, timeout=5)
                    r.raise_for_status()
                    data = r.json()
                    break
                except requests.RequestException:
                    if attempt < 2:
                        time.sleep(1)
                    else:
                        logging.warning(f"Failed to fetch facility {facility_id} after 3 attempts. Skipping.")
                        data = {}

            # Extract fee descriptions
            use_fee = data.get("FacilityUseFeeDescription", "").strip()
            activity_fee = data.get("FacilityActivityFeeDescription", "").strip()

            # Insert fees if present
            if use_fee:
                cur.execute(insert_sql, (facility_id, use_fee, "use"))
                total_inserted += 1

            if activity_fee:
                cur.execute(insert_sql, (facility_id, activity_fee, "activity"))
                total_inserted += 1

        conn.commit()
        logging.info(f"Processed batch {i//batch_size + 1}: total inserted so far = {total_inserted}")

    cur.close()
    conn.close()
    logging.info(f"FEE ingestion complete. Total inserted: {total_inserted}")
# --------------------------------------------------------------------
# ACCESSIBILITY
# --------------------------------------------------------------------
def parse_accessibility_flags(accessibility_text: str):
    text = accessibility_text.lower()

    # Wheelchair keywords
    wheelchair_keywords = ["wheelchair", "wheel-chair", "wheel chair"]
    wheelchair_accessible = 1 if any(k in text for k in wheelchair_keywords) else 0

    # Audio keywords
    audio_keywords = ["audio", "audio description", "audio-guide", "audio guide"]
    audio_descriptions = 1 if any(k in text for k in audio_keywords) else 0

    # Tactile keywords
    tactile_keywords = ["tactile", "tactile exhibit", "touch exhibit"]
    tactile_exhibits = 1 if any(k in text for k in tactile_keywords) else 0

    return wheelchair_accessible, audio_descriptions, tactile_exhibits

def ingest_accessibility(max_number: int = 500, batch_size: int = 50):
    conn = get_connection()
    cursor = conn.cursor()

    offset = 0
    processed = 0

    while processed < max_number:
        limit = min(batch_size, max_number - processed)
        url = f"{RIDB_BASE_URL}/facilities?limit={limit}&offset={offset}&apikey={RIDB_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        facilities = response.json().get("RECDATA", [])

        if not facilities:
            break

        for facility in facilities:
            facility_id = facility["FacilityID"]
            accessibility_text = facility.get("FacilityAccessibilityText", "")

            wheelchair_accessible, audio_descriptions, tactile_exhibits = parse_accessibility_flags(accessibility_text)

            cursor.execute(
                """
                INSERT INTO ACCESSIBILITY (
                    facility_id,
                    wheelchair_accessible,
                    audio_descriptions,
                    tactile_exhibits
                ) VALUES (%s, %s, %s, %s)
                """,
                (facility_id, wheelchair_accessible, audio_descriptions, tactile_exhibits)
            )

            processed += 1

        conn.commit()
        offset += limit

    cursor.close()
    conn.close()
    print(f"Ingested {processed} facilities into ACCESSIBILITY")


# --------------------------------------------------------------------
# Master ingest
# --------------------------------------------------------------------

def ingest_ridb_all():
    ingest_facilities(max_records=15000)
    ingest_facility_activities(max_activities=1000, batch_size=300)
    ingest_fees()
    ingest_accessibility(max_number=1000, batch_size=50)

if __name__ == "__main__":
    ingest_ridb_all()


