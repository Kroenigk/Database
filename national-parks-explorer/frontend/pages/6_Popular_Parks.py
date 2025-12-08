# popular parks and tags page
import streamlit as st
from frontend.park_details import render_park_details
import os
import requests
from frontend.park_data import (
    get_parks,
    get_tags,
)

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# --- user auth guard ---
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

st.title("Explore Parks by Popularity and Tags")
st.caption("Discover the most popular parks and explore them by tags.")

popularity_tab, tags_tab = st.tabs(["Popularity", "Tags"])

# ---------------- Popularity Tab ----------------
with popularity_tab:
    st.header("Most Popular Parks")

    popular_parks = []
    error_message = None

    try:
        resp = requests.get(
            f"{API_BASE}/api/parks/popular",
            cookies={"session_id": st.session_state.get("session_id")},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            popular_parks = data.get("parks", [])
        else:
            error_message = f"API error: {resp.status_code}"
    except requests.RequestException as exc:
        error_message = f"Request failed: {exc}"

    if error_message:
        st.error(error_message)
    elif not popular_parks:
        st.info("No popularity data available yet.")
    else:
        for park in popular_parks:
            with st.container():
                st.subheader(park["name"])

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("⭐ Favorites", park["favorites_count"])
                col2.metric("👣 Visits", park["visit_count"])
                col3.metric("📝 Reviews", park["review_count"])
                col4.metric(
                    "⭐ Avg Rating",
                    f"{park['avg_rating']:.2f}"
                    if park["avg_rating"] is not None
                    else "N/A",
                )

                if st.button("View Park Details", key=f"view_{park['park_id']}"):
                    st.session_state["selected_park_id"] = park["park_id"]
                    render_park_details(park["park_id"])

# ---------------- Tags Tab ----------------
with tags_tab:
    st.header("Explore Parks by Tags")

    tags = get_tags()  # still using your helper to get the list of labels

    if not tags:
        st.info("No tags found in the database.")
    else:
        selected_tag = st.selectbox("Select a Tag", tags)

        tagged_parks = []
        error_message = None

        if selected_tag:
            try:
                resp = requests.get(
                    f"{API_BASE}/api/parks",
                    params={"tag": selected_tag},
                    cookies={"session_id": st.session_state.get("session_id")},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tagged_parks = data.get("parks", [])
                else:
                    error_message = f"API error: {resp.status_code}"
            except requests.RequestException as exc:
                error_message = f"Request failed: {exc}"

        if error_message:
            st.error(error_message)
        elif not tagged_parks:
            st.warning(f"No parks found with tag '{selected_tag}'.")
        else:
            st.subheader(f"Parks tagged with '{selected_tag}':")
            for park in tagged_parks:
                st.write(f"• {park.get('name', 'Unknown park')}")
