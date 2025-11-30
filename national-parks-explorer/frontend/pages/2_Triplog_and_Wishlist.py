# Trip log
import os
import streamlit as st
from frontend.park_data import get_parks

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ---- auth guard ----
if not st.session_state.get("authenticated", False) or not st.session_state.get("user"):
    st.warning("Please log in from the main page to use the trip log.")
    st.stop()

user = st.session_state.user

# ---- simple in-memory storage for now (per session) ----
if "trip_log" not in st.session_state:
    st.session_state.trip_log = []

if "wishlist_trips" not in st.session_state:
    st.session_state.wishlist_trips = []


st.title("Trip Log & Wishlist")
st.caption(f"Logged in as {user.get('username', 'Unknown user')}")

tab_log, tab_wishlist = st.tabs(["Trip Log", "Wishlist Trips"])

# ---------------- Trip Log tab ----------------
with tab_log:
    st.subheader("Add a trip log entry")

    parks = get_parks()
    park_labels = [f"{p['name']}" for p in parks]

    log_park_name = st.selectbox("Park name", park_labels)
    log_trail_name = st.text_input("Trail (optional)", key="log_trail_name")
    log_season = st.selectbox(
        "Season visited",
        ["Spring", "Summer", "Fall", "Winter"],
        index=0,
        key="log_season",
    )
    log_rating = st.slider("Overall rating (1–5)", 1, 5, 5, key="log_rating")
    log_notes = st.text_area("Short notes about your trip", key="log_notes")

    if st.button("Save Trip Entry"):
        if not log_park_name:
            st.error("Please provide at least a park name.")
        else:
            st.session_state.trip_log.append(
                {
                    "park_name": log_park_name,
                    "trail_name": log_trail_name,
                    "season": log_season,
                    "rating": log_rating,
                    "notes": log_notes,
                }
            )
            if st.success("Trip entry saved."):
                #add in to database
                pass

    st.markdown("### Your trip log")

    if not st.session_state.trip_log:
        st.info("No trip log entries yet.")
    else:
        for i, entry in enumerate(st.session_state.trip_log, start=1):
            with st.container(border=True):
                st.markdown(f"**{i}. {entry['park_name']}**")
                if entry["trail_name"]:
                    st.caption(f"Trail: {entry['trail_name']}")
                st.write(f"Season: {entry['season']} · Rating: {entry['rating']}/5")
                if entry["notes"]:
                    st.write(entry["notes"])


# ---------------- Wishlist tab ----------------
with tab_wishlist:
    st.subheader("Add a wishlist trip")

    parks = get_parks()
    park_labels = [f"{p['name']}" for p in parks]

    wish_park_name = st.selectbox("National Park", park_labels)
    wish_season = st.selectbox(
        "Desired season",
        ["Spring", "Summer", "Fall", "Winter"],
        index=0,
        key="wish_season",
    )
    wish_notes = st.text_area("Short notes or plans", key="wish_notes")

    if st.button("Save Wishlist Trip"):
        if not wish_park_name:
            st.error("Please provide a park name.")
        else:
            st.session_state.wishlist_trips.append(
                {
                    "park_name": wish_park_name,
                    "season": wish_season,
                    "notes": wish_notes,
                }
            )
            if st.success("Wishlist trip saved"):
                pass
                # add to table

    st.markdown("### Your wishlist trips")

    if not st.session_state.wishlist_trips:
        st.info("No wishlist trips yet.")
    else:
        for i, wish in enumerate(st.session_state.wishlist_trips, start=1):
            with st.container(border=True):
                st.markdown(f"**{i}. {wish['park_name']}**")
                st.write(f"Season: {wish['season']}")
                if wish["notes"]:
                    st.write(wish["notes"])
