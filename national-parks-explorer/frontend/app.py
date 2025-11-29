import os
import sys

# Make project root importable so "backend" works
ROOT = os.path.dirname(os.path.dirname(__file__))  # national-parks-explorer/
if ROOT not in sys.path:
    sys.path.append(ROOT)

import streamlit as st
from backend.db import get_connection

def query_one(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return row
    finally:
        conn.close()


def query_all(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()


# -----------------------------------------------------
# Data access functions
# -----------------------------------------------------

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


# -----------------------------------------------------
# UI components
# -----------------------------------------------------

def render_sidebar():
    st.sidebar.title("National Parks Explorer")
    st.sidebar.write("Filter parks by state and name to get started.")

    states = get_states()
    state_options = ["ALL"] + [f"{s['code']} - {s['name']}" for s in states]
    state_choice = st.sidebar.selectbox("State", state_options, index=0)

    if state_choice == "ALL":
        state_code = "ALL"
    else:
        state_code = state_choice.split(" - ")[0]

    search = st.sidebar.text_input("Search by park name")

    st.sidebar.markdown("---")
    counts = get_basic_counts()
    st.sidebar.metric("Parks", counts.get("parks", 0))
    st.sidebar.metric("Campgrounds", counts.get("campgrounds", 0))
    st.sidebar.metric("Trails", counts.get("trails", 0))
    st.sidebar.metric("Alerts", counts.get("alerts", 0))

    return search, state_code


def render_park_list(search, state_code):
    st.header("Parks")

    parks = get_parks(search=search, state_code=state_code)

    if not parks:
        st.info("No parks found for this filter.")
        return None

    # Show a simple table
    st.write(f"Found {len(parks)} park(s).")
    st.dataframe(
        [
            {
                "Name": p["name"],
                "Designation": p["designation"],
                "States": p["states"],
                "ID": p["park_id"],
            }
            for p in parks
        ],
        hide_index=True,
    )

    # Selection
    park_names = [f"{p['name']} ({p['states']})" for p in parks]
    choice = st.selectbox(
        "Select a park to view details",
        ["(none)"] + park_names,
        index=0,
    )
    if choice == "(none)":
        return None

    idx = park_names.index(choice)
    return parks[idx]["park_id"]


def render_park_detail(park_id: str):
    detail = get_park_detail(park_id)
    if not detail:
        st.error("Park not found.")
        return

    st.header(detail["name"])
    if detail["designation"]:
        st.caption(detail["designation"])

    col1, col2 = st.columns([2, 1])
    with col1:
        if detail["description"]:
            st.write(detail["description"])
    with col2:
        st.subheader("Location")
        st.write(f"Latitude: {detail['lat']}")
        st.write(f"Longitude: {detail['lon']}")

    # Images
    if detail["images"]:
        st.subheader("Images")
        urls = [row[0] for row in detail["images"] if row[0]]
        if urls:
            st.image(urls, use_column_width=True)

    # Activities & amenities
    cols = st.columns(2)
    with cols[0]:
        st.subheader("Activities")
        if detail["activities"]:
            st.write(", ".join(detail["activities"]))
        else:
            st.write("No activities listed.")

    with cols[1]:
        st.subheader("Amenities")
        if detail["amenities"]:
            st.write(", ".join(detail["amenities"]))
        else:
            st.write("No amenities listed.")

    # Campgrounds
    st.subheader("Campgrounds")
    if detail["campgrounds"]:
        cg_rows = []
        for cg_id, name, desc, lat, lon in detail["campgrounds"]:
            cg_rows.append(
                {
                    "Name": name,
                    "Description": (desc[:120] + "…") if desc and len(desc) > 120 else desc,
                    "Lat": lat,
                    "Lon": lon,
                    "ID": cg_id,
                }
            )
        st.dataframe(cg_rows, hide_index=True)
    else:
        st.write("No campgrounds found for this park.")

    # Trails
    st.subheader("Trails")
    if detail["trails"]:
        trail_rows = []
        for trail_id, name, length, diff in detail["trails"]:
            trail_rows.append(
                {
                    "Name": name,
                    "Length (miles)": length,
                    "Difficulty": diff,
                    "ID": trail_id,
                }
            )
        st.dataframe(trail_rows, hide_index=True)
    else:
        st.write("No trails found for this park.")

    # Alerts
    st.subheader("Current Alerts")
    if detail["alerts"]:
        for category, title, desc, issued_at in detail["alerts"]:
            with st.expander(f"{category or 'Alert'}: {title}"):
                if issued_at:
                    st.caption(f"Issued at: {issued_at}")
                st.write(desc or "No description provided.")
    else:
        st.write("No current alerts for this park.")

# -----------------------------------------------------
# Main app should include the following features:
# - Sidebar with state filter and search box
# - Park list with selection box
# - Park detail view with images, activities, amenities, campgrounds, trails, alerts
# - User functions (login, demo user)
# - User favorites 
# - Ability to add comments/reviews
# - User can favorite parks and view their favorites
# -----------------------------------------------------


# -----------------------------------------------------
# Main app entrypoint
# -----------------------------------------------------

def main():
    st.set_page_config(page_title="National Parks Explorer", layout="wide")

    search, state_code = render_sidebar()

    selected_park_id = render_park_list(search, state_code)

    if selected_park_id:
        st.markdown("---")
        render_park_detail(selected_park_id)
    else:
        st.markdown("### Select a park from the dropdown to view details.")


if __name__ == "__main__":
    main()
