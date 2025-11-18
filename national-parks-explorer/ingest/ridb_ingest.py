"""
RIDB (Recreation.gov) ingestion.

Responsible for loading:
- FACILITY
- CAMPGROUND
- AMENITY
- CAMPGROUND_AMENITY
- FEE
- FACILITY_ACTIVITY
- ACCESSIBILITY
"""

import requests
from typing import Iterable, Dict, Any

from .config import RIDB_API_KEY, RIDB_BASE_URL
from .db import get_connection


HEADERS = {"apikey": RIDB_API_KEY}


# --------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------

def _fetch_paginated(endpoint: str, params: Dict[str, Any] | None = None) -> Iterable[Dict[str, Any]]:
    """
    Generator that walks through RIDB's paginated endpoints.
    Yields individual records from RECDATA.
    """
    if params is None:
        params = {}

    # RIDB uses limit/offset pagination
    params = {**params, "limit": 50, "offset": 0}

    while True:
        resp = requests.get(f"{RIDB_BASE_URL}/{endpoint}", headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()

        records = data.get("RECDATA", [])
        if not records:
            break

        for rec in records:
            yield rec

        params["offset"] += len(records)


# --------------------------------------------------------------------
# Facilities
# --------------------------------------------------------------------

def ingest_facilities():
    """
    Ingest facilities into FACILITY.

    FACILITY (
        facility_id CHAR(36) PK,
        park_id     CHAR(36) NULL,
        name        VARCHAR(255),
        type        VARCHAR(50)
    )
    """
    conn = get_connection()
    cur = conn.cursor()

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
            facility_id = fac["FacilityID"]
            name = fac.get("FacilityName")
            fac_type = fac.get("FacilityTypeDescription")

            # TODO: map this facility to a PARK if you want
            # e.g., by location or manual mapping; for now keep it NULL
            park_id = None

            cur.execute(sql, (facility_id, park_id, name, fac_type))

        conn.commit()
        print("RIDB: facilities ingested.")
    finally:
        conn.close()


# --------------------------------------------------------------------
# Campgrounds
# --------------------------------------------------------------------

def ingest_campgrounds():
    """
    Ingest campgrounds into CAMPGROUND and CAMPGROUND_AMENITY.

    CAMPGROUND (
        campground_id INT PK,
        park_id       CHAR(36),
        name          VARCHAR(150),
        description   TEXT,
        latitude      DECIMAL,
        longitude     DECIMAL
    )

    CAMPGROUND_AMENITY (
        campground_id INT FK,
        amenity_id    INT FK
    )
    """
    conn = get_connection()
    cur = conn.cursor()

    campground_sql = """
        INSERT INTO CAMPGROUND (campground_id, park_id, name, description, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            park_id     = VALUES(park_id),
            name        = VALUES(name),
            description = VALUES(description),
            latitude    = VALUES(latitude),
            longitude   = VALUES(longitude)
    """

    # Optional: if you want to populate AMENITY & CAMPGROUND_AMENITY here:
    amenity_sql = """
        INSERT INTO AMENITY (name)
        VALUES (%s)
        ON DUPLICATE KEY UPDATE name = VALUES(name)
    """
    link_sql = """
        INSERT IGNORE INTO CAMPGROUND_AMENITY (campground_id, amenity_id)
        VALUES (%s, %s)
    """

    try:
        # RIDB "facilities" of type "Campground" is one common approach
        for fac in _fetch_paginated("facilities", params={"facilitytype": "Campground"}):
            campground_id = fac["FacilityID"]
            name = fac.get("FacilityName")
            desc = fac.get("FacilityDescription")
            lat = fac.get("FacilityLatitude")
            lon = fac.get("FacilityLongitude")

            # TODO: map to NPS PARK if desired (by state + coordinates)
            park_id = None

            cur.execute(
                campground_sql,
                (campground_id, park_id, name, desc, lat, lon),
            )

            # TODO: parse amenities if present; RIDB often uses
            # fac.get("ACTIVITY") or "AMENITY" arrays depending on endpoint shape.
            # Example skeleton:
            #
            # amenities = fac.get("ACTIVITY", [])
            # for am in amenities:
            #     label = am.get("ActivityName")
            #     if not label:
            #         continue
            #     cur.execute(amenity_sql, (label,))
            #     amenity_id = cur.lastrowid  # or SELECT by name if needed
            #     cur.execute(link_sql, (campground_id, amenity_id))

        conn.commit()
        print("RIDB: campgrounds ingested.")
    finally:
        conn.close()


# --------------------------------------------------------------------
# Amenities only (optional helper)
# --------------------------------------------------------------------

def ingest_amenities():
    """
    If you decide to pull a dedicated amenity list (or normalize them separately),
    implement it here.

    For now, this function can be a no-op or log a message.
    """
    print("RIDB: ingest_amenities() not yet implemented.")


# --------------------------------------------------------------------
# Entry point for ingest_all
# --------------------------------------------------------------------

def ingest_ridb_all():
    """
    Convenience wrapper used by ingest_all.py
    """
    ingest_facilities()
    # ingest_campgrounds()
    # ingest_amenities()
