# Trip log
import os
import streamlit as st
from frontend.park_data import get_parks
from backend.db import get_connection
from datetime import date
import requests

# This is where the backend runs, so we can make API request to it instead of directly interacting with the database
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ---- auth guard ----
# Makes sure that the user is logged in, aka they have to go through the signup page first
if not st.session_state.get("authenticated", False) or not st.session_state.get("user"):
    st.warning("Please log in from the main page to use the trip log.")
    st.stop()

user = st.session_state.user

# simple in-memory storage for the current session
if "trip_log" not in st.session_state:
    st.session_state.trip_log = []

if "wishlist_trips" not in st.session_state:
    st.session_state.wishlist_trips = []


st.title("Trip Log & Wishlist")
st.caption(f"Logged in as {user.get('username', 'Unknown user')}")

# This page has two tabs, each with their own purpose
tab_log, tab_wishlist = st.tabs(["Trip Log", "Wishlist Trips"])

# ---------------- Trip Log tab ----------------
with tab_log:
    st.subheader("Add a trip log entry")

    user = st.session_state.get("user")
    if not user:
        st.warning("Please log in to manage your trip log.")
        st.stop()

    session_id = str(user["session_id"])

    # Park selection - limited to parks in the DB
    parks = get_parks()
    park_labels_log = [f"{p['name']} ({p['park_id']})" for p in parks]

    selected_label_log = st.selectbox(
        "National Park",
        park_labels_log,
        key="triplog_park_select",
    )

    # Map label back to park dict
    idx = park_labels_log.index(selected_label_log)
    selected_park = parks[idx]
    log_park_name = selected_park["name"]
    log_park_id = selected_park["park_id"]

    # Dates + notes
    log_start_date = st.date_input(
        "Planned Travel Start Date",
        value=date.today(),
    )
    log_end_date = st.date_input(
        "Planned Travel End Date",
        value=date.today(),
    )
    log_notes = st.text_area("Short notes about your trip", key="log_notes")

    # Once this button is pressed it will create a new trip log connect to the user
    if st.button("Save Trip Entry"):
        if not log_park_name:
            st.error("Please provide at least a park name.")
        elif log_end_date < log_start_date:
            st.error("End date cannot be before start date.")
        else:
            try:
                # Give the user information, the app will then use the API to pass the information to the database
                # to create a new trip log with the necessary information
                resp = requests.post(
                    f"{API_BASE}/api/triplog",
                    json={
                        "park_id": log_park_id,
                        "start_date": log_start_date.isoformat(),
                        "end_date": log_end_date.isoformat(),
                        "notes": log_notes,
                    },
                    cookies={"session_id": session_id},
                    timeout=5,
                )
                data = resp.json()
                # If the request fails, it will thrown an error
                if resp.status_code != 201:
                    st.error(data.get("error", "Failed to save trip log."))
                else:
                    st.success("Trip log saved.")
                    st.rerun()
            # Exception handling
            except Exception as e:
                st.error(f"Failed to save trip log: {e}")

    st.markdown("### Your trip log")

    # ---- Load trip log via API ----
    try:
        # This will request the database for all of the trip logs attached to a user to be displayed
        list_resp = requests.get(
            f"{API_BASE}/api/triplog",
            cookies={"session_id": session_id},
            timeout=5,
        )
        list_data = list_resp.json()
    # Exception handling
    except Exception as e:
        list_data = {"error": str(e)}

    # If the data cannot be retrieved, then an error will be thrown
    if list_data.get("error"):
        st.error(f"Could not load trip log: {list_data['error']}")
    else:
        # If there are no trip logs yet, the default will be shwon
        triplog = list_data.get("triplog", [])
        if not triplog:
            st.info("No trip log entries yet.")
        else:
            # small helper to turn string -> date
            def parse_date_safe(s: str | None) -> date:
                if not s:
                    return date.today()
                try:
                    # handle "2024-12-01" or "2024-12-01T00:00:00"
                    return date.fromisoformat(str(s)[:10])
                except Exception:
                    return date.today()

            # For each entry in triplog will have its own container - this will be helpful if the user updates the information
            for i, entry in enumerate(triplog, start=1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {entry['park_name']}**")

                    current_start = parse_date_safe(entry.get("start_date"))
                    current_end = parse_date_safe(entry.get("end_date"))

                    # Retrieves the updated information
                    new_start = st.date_input(
                        "Start date",
                        value=current_start,
                        key=f"trip_start_{entry['trip_id']}",
                    )
                    new_end = st.date_input(
                        "End date",
                        value=current_end,
                        key=f"trip_end_{entry['trip_id']}",
                    )

                    new_notes = st.text_area(
                        "Notes",
                        value=entry.get("notes", "") or "",
                        key=f"trip_notes_{entry['trip_id']}",
                    )

                    # If the button is clicked, then it will send a put request to update the information in the database
                    if st.button(
                        "Save changes",
                        key=f"save_trip_{entry['trip_id']}",
                    ):
                        # Error handling to make sure the dates make sense
                        if new_end < new_start:
                            st.error("End date cannot be before start date.")
                        else:
                            try:
                                # This will sent a put request to UPDATE the information in the db
                                resp = requests.put(
                                    f"{API_BASE}/api/triplog/{entry['trip_id']}",
                                    json={
                                        "start_date": new_start.isoformat(),
                                        "end_date": new_end.isoformat(),
                                        "notes": new_notes,
                                    },
                                    cookies={"session_id": session_id},
                                    timeout=5,
                                )
                                data = resp.json()
                                # If it fails to update, an error will be thrown for debugging
                                if resp.status_code != 200:
                                    st.error(
                                        data.get(
                                            "error",
                                            "Failed to update trip log.",
                                        )
                                    )
                                else:
                                    st.success("Trip log updated.")
                                    # If it is a success, then the page will reload to show the updated info
                                    st.rerun()
                            # Exception handling
                            except Exception as e:
                                st.error(f"Error updating trip log: {e}")

# ---------------- Wishlist tab ----------------
with tab_wishlist:
    st.subheader("Add a wishlist trip")

    user = st.session_state.get("user")
    if not user:
        st.warning("Please log in to manage your wishlist.")
        st.stop()

    session_id = str(user["session_id"])

    # Load parks and build labels - keeping user choice within available parks
    parks = get_parks()
    park_labels_wish = [f"{p['name']} ({p['park_id']})" for p in parks]

    selected_label_wish = st.selectbox(
        "National Park",
        park_labels_wish,
        key="wishlist_park_select",
    )

    # Extracting necessary info from user choice
    idx = park_labels_wish.index(selected_label_wish)
    selected_park = parks[idx]
    wish_park_name = selected_park["name"]
    wish_park_id = selected_park["park_id"]

    wish_season = st.selectbox(
        "Desired season",
        ["Spring", "Summer", "Fall", "Winter"],
        index=0,
        key="wish_season",
    )
    # Given its own key to prevent run time errors of key duplication
    wish_notes = st.text_area("Short notes or plans", key="wish_notes")

    # If this button is pressed, it will save the current Wishlist trip to the database
    if st.button("Save Wishlist Trip"):
        # Must provide a name
        if not wish_park_name:
            st.error("Please provide a park name.")
        else:
            # Wishlist trip saved to DB through API
            try:
                resp = requests.post(
                    f"{API_BASE}/api/wishlist",
                    json={
                        "park_id": wish_park_id,
                        "target_season": wish_season,
                        "notes": wish_notes,
                    },
                    cookies={"session_id": session_id},
                    timeout=5,
                )
                data = resp.json()
                if resp.status_code != 201:
                    st.error(data.get("error", "Failed to save wishlist trip."))
                else:
                    st.success("Wishlist trip saved.")
                    # reload list below
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to save wishlist trip: {e}")

    st.markdown("### Your wishlist trips")

    # ---- Load wishlist via API ----
    try:
        # Tries to get all of the wishlist trips attached to a user
        list_resp = requests.get(
            f"{API_BASE}/api/wishlist",
            cookies={"session_id": session_id},
            timeout=5,
        )
        list_data = list_resp.json()
    # Exception Handling
    except Exception as e:
        list_data = {"error": str(e)}

    if list_data.get("error"):
        st.error(f"Could not load wishlist: {list_data['error']}")
    else:
        wishlist = list_data.get("wishlist", [])
        if not wishlist:
            # If there are no wishlist trips for the user, then the default will be displayed
            st.info("No wishlist trips yet.")
        else:
            seasons = ["Spring", "Summer", "Fall", "Winter"]

            for i, wish in enumerate(wishlist, start=1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {wish['park_name']}**")

                    # Editable season selectbox
                    current_season = wish.get("target_season", "Spring")
                    if current_season not in seasons:
                        current_season = "Spring"

                    new_season = st.selectbox(
                        "Season",
                        seasons,
                        index=seasons.index(current_season),
                        key=f"edit_wish_season_{wish['wishlist_id']}",
                    )

                    # Editable notes
                    new_notes = st.text_area(
                        "Notes",
                        value=wish.get("notes", "") or "",
                        key=f"edit_wish_notes_{wish['wishlist_id']}",
                    )

                    if st.button(
                        "Save changes",
                        key=f"save_wish_{wish['wishlist_id']}",
                    ):
                        try:
                            resp = requests.put(
                                f"{API_BASE}/api/wishlist/{wish['wishlist_id']}",
                                json={
                                    "target_season": new_season,
                                    "notes": new_notes,
                                },
                                cookies={"session_id": session_id},
                                timeout=5,
                            )

                            data = resp.json()

                            if resp.status_code != 200:
                                st.error(
                                    data.get(
                                        "error", "Failed to update wishlist trip"
                                    )
                                )
                            else:
                                st.success("Wishlist trip updated.")
                                st.rerun()

                        except Exception as e:
                            st.error(f"Error updating wishlist trip: {e}")
