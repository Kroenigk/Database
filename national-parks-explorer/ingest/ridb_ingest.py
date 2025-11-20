
from requests.exceptions import HTTPError
import requests
from typing import Iterable, Dict, Any, List, Optional, Tuple

from backend.db import get_connection
from backend.config import ( RIDB_API_KEY, RIDB_BASE_URL )

HEADERS = {"apikey": RIDB_API_KEY}


# --------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------

def _fetch_paginated(endpoint: str, params: Dict[str, Any] | None = None) -> Iterable[Dict[str, Any]]:
    """
    Generator that walks through RIDB's paginated endpoints.
    Yields individual records from RECDATA.

    - If the endpoint is NOT paginated (no METADATA key), we do a single request.
    - If it IS paginated, we use METADATA.RESULTS.{TOTALCOUNT, CURRENTCOUNT, OFFSET}
      to know when to stop, instead of blindly bumping offset forever.
    """
    if params is None:
        params = {}

    # Start with a reasonable default
    params = {**params}
    if "limit" not in params:
        params["limit"] = 50
    if "offset" not in params:
        params["offset"] = 0

    while True:
        try:
            resp = requests.get(f"{RIDB_BASE_URL}/{endpoint}", headers=HEADERS, params=params)
            resp.raise_for_status()
        except HTTPError as e:
            # Stop on rate limiting instead of hammering the API
            if resp is not None and resp.status_code == 429:
                break
            raise

        data = resp.json()
        records = data.get("RECDATA", []) or data.get("recdata", [])
        if not records:
            break

        # Yield current page
        for rec in records:
            yield rec

        # If there is no METADATA, treat this as a single-shot endpoint
        meta = data.get("METADATA")
        if not meta:
            break

        results_meta = meta.get("RESULTS", {})
        total = results_meta.get("TOTALCOUNT")
        current = results_meta.get("CURRENTCOUNT") or len(records)
        offset = results_meta.get("OFFSET", params.get("offset", 0))

        # If we've reached or passed the total, we're done
        if total is not None and offset + current >= total:
            break

        # Otherwise, advance offset and continue
        params["offset"] = offset + current

        # Safety guard: if the API lies and keeps giving same offset/current,
        # break to avoid infinite loop.
        if current == 0 or current < params["limit"]:
            break


def _fetch_facility_subresource(
    facility_id: str,
    subresource: str,
    params: Dict[str, Any] | None = None,
) -> Iterable[Dict[str, Any]]:
    """
    Convenience wrapper for:
        /facilities/{facilityId}/{subresource}
    where subresource is 'activities', 'permitentrances', 'attributes', 'campsites', etc.
    """
    endpoint = f"facilities/{facility_id}/{subresource}"
    yield from _fetch_paginated(endpoint, params=params)


def _safe_get(rec: Dict[str, Any], *keys: str) -> Any:
    """Try multiple keys for the same semantic field."""
    for k in keys:
        if k in rec:
            return rec[k]
    return None


# --------------------------------------------------------------------
# Park mapping helpers (lat/lon nearest-neighbor)
# --------------------------------------------------------------------

def _load_parks(conn) -> List[Tuple[str, float, float]]:
    """
    Load all parks with non-null coordinates.

    Returns list of (park_id, lat, lon).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT park_id, latitude, longitude "
        "FROM PARK WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    parks: List[Tuple[str, float, float]] = []
    for park_id, lat, lon in cur.fetchall():
        if lat is None or lon is None:
            continue
        parks.append((park_id, float(lat), float(lon)))
    return parks


def _find_nearest_park(
    lat: Optional[float],
    lon: Optional[float],
    parks: List[Tuple[str, float, float]],
) -> Optional[str]:
    """
    Find nearest park by Euclidean distance in lat/lon degrees.
    Returns park_id or None if lat/lon missing or no parks.
    """
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
# FACILITY
# --------------------------------------------------------------------

def ingest_facilities():
    """
    Ingest RIDB facilities into FACILITY.

    FACILITY (
        facility_id CHAR(36) PRIMARY KEY,
        park_id     CHAR(36),
        name        VARCHAR(255) NOT NULL,
        type        VARCHAR(50)
    )
    """
    conn = get_connection()
    cur = conn.cursor()

    parks = _load_parks(conn)

    sql = """
        INSERT INTO FACILITY (facility_id, park_id, name, type)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            park_id = VALUES(park_id),
            name    = VALUES(name),
            type    = VALUES(type)
    """

    try:
        for fac in _fetch_paginated("facilities"):
            facility_id = str(fac["FacilityID"])
            name = fac.get("FacilityName")
            fac_type = fac.get("FacilityTypeDescription")
            lat = fac.get("FacilityLatitude")
            lon = fac.get("FacilityLongitude")

            park_id = _find_nearest_park(lat, lon, parks)

            cur.execute(sql, (facility_id, park_id, name, fac_type))

        conn.commit()
        print("RIDB: facilities ingested.")
    finally:
        conn.close()


# --------------------------------------------------------------------
# AMENITY helpers
# --------------------------------------------------------------------

def _get_or_create_amenity(cur, name: str) -> int:
    """
    Get amenity_id for given name, inserting if needed.
    """
    cur.execute("SELECT amenity_id FROM AMENITY WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("INSERT INTO AMENITY (name) VALUES (%s)", (name,))
    return cur.lastrowid


# --------------------------------------------------------------------
# ACTIVITY + FACILITY_ACTIVITY
# --------------------------------------------------------------------

def ingest_facility_activities():
    """
    Populate ACTIVITY and FACILITY_ACTIVITY from
    /facilities/{facilityId}/activities.

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
    """
    conn = get_connection()
    cur = conn.cursor()

    # Load facilities so we don't hit RIDB for unknown ones.
    cur.execute("SELECT facility_id FROM FACILITY")
    facility_ids = [row[0] for row in cur.fetchall()]

    activity_upsert_sql = """
        INSERT INTO ACTIVITY (activity_id, name, description)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name        = VALUES(name),
            description = COALESCE(ACTIVITY.description, VALUES(description))
    """

    facility_activity_upsert_sql = """
        INSERT INTO FACILITY_ACTIVITY (facility_id, activity_id)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE activity_id = VALUES(activity_id)
    """

    try:
        for facility_id in facility_ids:
            for act in _fetch_facility_subresource(str(facility_id), "activities"):
                ridb_act_id = _safe_get(act, "ActivityID", "activity_id")
                name = _safe_get(act, "ActivityName", "activity_name")
                desc = _safe_get(act, "ActivityDescription", "activity_description")

                if not ridb_act_id or not name:
                    continue

                # Store RIDB ActivityID as string
                activity_id = str(ridb_act_id)

                cur.execute(activity_upsert_sql, (activity_id, name, desc))
                cur.execute(facility_activity_upsert_sql, (facility_id, activity_id))

        conn.commit()
        print("RIDB: activities + facility activities ingested.")
    finally:
        conn.close()


# --------------------------------------------------------------------
# FEE
# --------------------------------------------------------------------

def ingest_fees():
    """
    Populate FEE table from PermitEntrances/Zones.

    FEE (
        fee_id      INT AUTO_INCREMENT PRIMARY KEY,
        facility_id CHAR(36) NOT NULL,
        description VARCHAR(255),
        amount      DECIMAL(10,2)
    )

    Since RIDB doesn't have a simple numeric fee field everywhere,
    this ingest:
      - Creates a human-readable description using permit/zone names.
      - Leaves amount NULL (you can enhance later if you parse fee amounts).
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT facility_id FROM FACILITY")
    facility_ids = [row[0] for row in cur.fetchall()]

    insert_fee_sql = """
        INSERT INTO FEE (facility_id, description, amount)
        VALUES (%s, %s, %s)
    """

    try:
        for facility_id in facility_ids:
            # Clean existing rows for idempotent ingest
            cur.execute("DELETE FROM FEE WHERE facility_id = %s", (facility_id,))

            for pe in _fetch_facility_subresource(str(facility_id), "permitentrances"):
                permit_name = _safe_get(pe, "PermitEntranceName", "permit_entrance_name")
                permit_desc = _safe_get(pe, "PermitEntranceDescription", "permit_entrance_description")

                base_desc_parts = []
                if permit_name:
                    base_desc_parts.append(str(permit_name))
                if permit_desc:
                    base_desc_parts.append(str(permit_desc))

                base_desc = " - ".join(base_desc_parts) if base_desc_parts else "Permit entrance"

                # Insert base fee row (no specific zone)
                cur.execute(insert_fee_sql, (facility_id, base_desc[:255], None))

                permit_id = _safe_get(pe, "PermitEntranceID", "permit_entrance_id")
                if not permit_id:
                    continue

                # Zones under this permit entrance
                zones_resp = requests.get(
                    f"{RIDB_BASE_URL}/permitentrances/{permit_id}/zones",
                    headers=HEADERS,
                    params={"limit": 50, "offset": 0},
                )
                zones_resp.raise_for_status()
                zones_data = zones_resp.json()
                zones = zones_data.get("RECDATA", []) or zones_data.get("zones", [])

                for zone in zones:
                    zone_name = _safe_get(zone, "ZoneName", "zone_name")
                    zone_desc = _safe_get(zone, "ZoneDescription", "zone_description")

                    desc_parts = []
                    if permit_name:
                        desc_parts.append(str(permit_name))
                    if zone_name:
                        desc_parts.append(f"Zone: {zone_name}")
                    if zone_desc:
                        desc_parts.append(str(zone_desc))

                    desc = " - ".join(desc_parts) if desc_parts else base_desc
                    cur.execute(insert_fee_sql, (facility_id, desc[:255], None))

        conn.commit()
        print("RIDB: fees ingested.")
    finally:
        conn.close()


# --------------------------------------------------------------------
# ACCESSIBILITY
# --------------------------------------------------------------------

def ingest_accessibility_info():
    """
    Populate ACCESSIBILITY table from facility attributes.

    ACCESSIBILITY (
        accessibility_id      INT AUTO_INCREMENT PRIMARY KEY,
        facility_id           CHAR(36) NOT NULL,
        wheelchair_accessible TINYINT(1) NOT NULL DEFAULT 0,
        audio_descriptions    TINYINT(1) NOT NULL DEFAULT 0,
        tactile_exhibits      TINYINT(1) NOT NULL DEFAULT 0
    )

    Heuristics:
      - "wheelchair" or "accessible" attributes -> wheelchair_accessible
      - "audio" / "assistive listening" -> audio_descriptions
      - "tactile" / "braille" -> tactile_exhibits
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT facility_id FROM FACILITY")
    facility_ids = [row[0] for row in cur.fetchall()]

    insert_sql = """
        INSERT INTO ACCESSIBILITY (
            facility_id,
            wheelchair_accessible,
            audio_descriptions,
            tactile_exhibits
        )
        VALUES (%s, %s, %s, %s)
    """

    update_sql = """
        UPDATE ACCESSIBILITY
        SET wheelchair_accessible = %s,
            audio_descriptions    = %s,
            tactile_exhibits      = %s
        WHERE facility_id = %s
    """

    try:
        for facility_id in facility_ids:
            wheelchair = 0
            audio = 0
            tactile = 0

            for attr in _fetch_facility_subresource(str(facility_id), "attributes"):
                name = str(_safe_get(attr, "AttributeName", "attribute_name") or "").lower()
                value = str(_safe_get(attr, "AttributeValue", "attribute_value") or "").lower()

                if not name and not value:
                    continue

                # Simple truthiness check
                def _is_true(val: str) -> bool:
                    return val in ("yes", "y", "true", "1")

                if "wheelchair" in name or ("accessible" in name and _is_true(value)):
                    if _is_true(value) or "yes" in name:
                        wheelchair = 1

                if "audio" in name or "assistive listening" in name:
                    if _is_true(value) or "yes" in name:
                        audio = 1

                if "tactile" in name or "braille" in name:
                    if _is_true(value) or "yes" in name:
                        tactile = 1

            # Upsert per facility_id (manually since PK is accessibility_id)
            cur.execute("SELECT accessibility_id FROM ACCESSIBILITY WHERE facility_id = %s", (facility_id,))
            row = cur.fetchone()
            if row:
                cur.execute(update_sql, (wheelchair, audio, tactile, facility_id))
            else:
                cur.execute(insert_sql, (facility_id, wheelchair, audio, tactile))

        conn.commit()
        print("RIDB: accessibility info ingested.")
    finally:
        conn.close()


# --------------------------------------------------------------------
# Entry point for ingest_all
# --------------------------------------------------------------------

def ingest_ridb_all():
    """
    Convenience wrapper used by ingest_all.py
    (Call order chosen to satisfy foreign keys where relevant.)
    """
    ingest_facilities()
    ingest_facility_activities()
    ingest_fees()
    ingest_accessibility_info()
