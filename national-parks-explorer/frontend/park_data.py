import os
import sys
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from backend.db import get_connection

def query_one(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchone()
    finally:
        conn.close()

def query_all(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur.fetchall()
    finally:
        conn.close()

@st.cache_data(show_spinner=False)
def get_states():
    rows = query_all(
        "SELECT state_code, name FROM STATE ORDER BY state_code"
    )
    return [{"code": c, "name": n} for (c, n) in rows]


@st.cache_data(show_spinner=True)
def get_parks(search: str | None = None, state_code: str | None = None):
    params = []
    where_clauses = []

    if search:
        where_clauses.append("p.name LIKE %s")
        params.append(f"%{search}%")

    if state_code and state_code != "ALL":
        where_clauses.append("ps.state_code = %s")
        params.append(state_code)

    where_sql = " AND ".join(where_clauses)
    if where_sql:
        where_sql = "WHERE " + where_sql

    sql = f"""
        SELECT
            p.park_id,
            p.name,
            p.designation,
            GROUP_CONCAT(DISTINCT ps.state_code ORDER BY ps.state_code SEPARATOR ', ') AS states
        FROM PARK p
        LEFT JOIN PARK_STATE ps ON p.park_id = ps.park_id
        {where_sql}
        GROUP BY p.park_id, p.name, p.designation
        ORDER BY p.name
        LIMIT 200
    """
    rows = query_all(sql, params)
    parks = []
    for park_id, name, designation, states in rows:
        parks.append(
            {
                "park_id": park_id,
                "name": name,
                "designation": designation,
                "states": states or "",
            }
        )
    return parks


@st.cache_data(show_spinner=True)
def get_park_detail(park_id: str):
    # Basic park info
    park_row = query_one(
        """
        SELECT name, designation, description, latitude, longitude
        FROM PARK
        WHERE park_id = %s
        """,
        (park_id,),
    )

    if not park_row:
        return None

    name, designation, description, lat, lon = park_row

    # Images
    images = query_all(
        """
        SELECT url, alt_text, credit
        FROM IMAGE
        WHERE park_id = %s
        LIMIT 6
        """,
        (park_id,),
    )

    # Activities
    activities = query_all(
        """
        SELECT a.name
        FROM PARK_ACTIVITY pa
        JOIN ACTIVITY a ON pa.activity_id = a.activity_id
        WHERE pa.park_id = %s
        ORDER BY a.name
        """,
        (park_id,),
    )

    # Amenities
    amenities = query_all(
        """
        SELECT m.name
        FROM PARK_AMENITY pa
        JOIN AMENITY m ON pa.amenity_id = m.amenity_id
        WHERE pa.park_id = %s
        ORDER BY m.name
        """,
        (park_id,),
    )

    # Campgrounds
    campgrounds = query_all(
        """
        SELECT campground_id, name, description, latitude, longitude
        FROM CAMPGROUND
        WHERE park_id = %s
        ORDER BY name
        """,
        (park_id,),
    )

    # Trails
    trails = query_all(
        """
        SELECT trail_id, name, length_miles, difficulty
        FROM TRAIL
        WHERE park_id = %s
        ORDER BY name
        """,
        (park_id,),
    )

    # Alerts
    alerts = query_all(
        """
        SELECT category, title, description, issued_at
        FROM PARK_ALERT
        WHERE park_id = %s
        ORDER BY issued_at DESC
        LIMIT 5
        """,
        (park_id,),
    )

    return {
        "name": name,
        "designation": designation,
        "description": description,
        "lat": lat,
        "lon": lon,
        "images": images,
        "activities": [a[0] for a in activities],
        "amenities": [a[0] for a in amenities],
        "campgrounds": campgrounds,
        "trails": trails,
        "alerts": alerts,
    }


@st.cache_data(show_spinner=False)
def get_basic_counts():
    sqls = {
        "parks": "SELECT COUNT(*) FROM PARK",
        "campgrounds": "SELECT COUNT(*) FROM CAMPGROUND",
        "trails": "SELECT COUNT(*) FROM TRAIL",
        "facilities": "SELECT COUNT(*) FROM FACILITY",
        "alerts": "SELECT COUNT(*) FROM PARK_ALERT",
    }
    counts = {}
    for key, sql in sqls.items():
        row = query_one(sql)
        counts[key] = row[0] if row else 0
    return counts


