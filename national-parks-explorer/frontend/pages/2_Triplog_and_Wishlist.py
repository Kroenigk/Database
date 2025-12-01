# Trip log
import os
import streamlit as st
from frontend.park_data import get_parks
from backend.db import get_connection
from datetime import date

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

    # Park selection - this will allow the user to have a limited selection and the necessary info will be at hand
    parks = get_parks()
    park_labels_log = [f"{p['name']} ({p['park_id']})" for p in parks]

    # The selectbox has its own key as there are multiple selectboxes in use, so they each need their own unique identifier
    selected_label_log = st.selectbox(
        "National Park",
        park_labels_log,
        key="triplog_park_select",
    )

    # Extracting necessary info for later
    idx = park_labels_log.index(selected_label_log)
    selected_park = parks[idx]
    log_park_name = selected_park["name"]
    log_park_id = selected_park["park_id"]

    log_start_date = st.date_input("Planned Travel Start Date", value=date.today(),)
    log_end_date = st.date_input("Planned Travel End Date", value=date.today(),)
    log_notes = st.text_area("Short notes about your trip", key="log_notes")

    # If this button is pushed by the user, it will save the trip entry in memory and to the database with the necessary foreign keys
    if st.button("Save Trip Entry"):
        # The user must atleast have a park name and the dates must make sense
        if not log_park_name:
            st.error("Please provide at least a park name.")
        elif log_end_date < log_start_date:
            st.error("End date cannot be before start date.")
        else:
            # Save to DB
            try:
                user = st.session_state.get("user")
                if not user:
                    st.error("You must be logged in to save a trip log.")
                else:
                    user_id = user["user_id"]

                    con = get_connection()
                    cur = con.cursor()
                    cur.execute(
                        """
                        INSERT INTO TRIP_LOG (user_id, park_id, start_date, end_date, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (user_id, log_park_id, log_start_date, log_end_date, log_notes),
                    )
                    con.commit()
                    trip_id = cur.lastrowid 

                    st.success("Trip log saved.")

                    # In-memory log for this session
                    st.session_state.trip_log.append(
                        {
                            "trip_id": trip_id,
                            "park_name": log_park_name,
                            "start_date": log_start_date,
                            "end_date": log_end_date,
                            "notes": log_notes,
                        }
                    )
            # Exception handling
            except Exception as e:
                st.error(f"Failed to save trip log: {e}")
            finally:
                try:
                    con.close()
                except NameError:
                    pass

    st.markdown("### Your trip log")

    if not st.session_state.trip_log:
        st.info("No trip log entries yet.")
    else:
        user = st.session_state.get("user")
        user_id = user["user_id"] if user else None

        # each trip log has its own container for its entry, so it can be updated by the user later if necessary
        for i, entry in enumerate(st.session_state.trip_log, start=1):
            with st.container(border=True):
                # Displays trip log data
                st.markdown(f"**{i}. {entry['park_name']}**")
                st.write(f"{entry['start_date']} → {entry['end_date']}")

                # Editable notes field for later revision
                new_notes = st.text_area(
                    "Edit notes",
                    value=entry.get("notes", "") or "",
                    key=f"edit_notes_{entry['trip_id']}",
                )

                # If an edit is made and this button is pushed, it will update the entry in the database
                if st.button(
                    "Save changes",
                    key=f"save_trip_{entry['trip_id']}",
                ):
                    if not user_id:
                        st.error("You must be logged in to update trip logs.")
                    else:
                        try:
                            con = get_connection()
                            cur = con.cursor()
                            cur.execute(
                                """
                                UPDATE TRIP_LOG
                                SET notes = %s
                                WHERE trip_id = %s AND user_id = %s
                                """,
                                (new_notes, entry["trip_id"], user_id),
                            )
                            con.commit()
                            st.success("Trip log updated.")

                            # Update local copy too
                            entry["notes"] = new_notes
                            # Reloads the page so the changes are reflected
                            st.rerun()

                        # Error handling
                        except Exception as e:
                            st.error(f"Failed to update trip log: {e}")
                        finally:
                            try:
                                con.close()
                            except NameError:
                                pass

# ---------------- Wishlist tab ----------------
with tab_wishlist:
    st.subheader("Add a wishlist trip")

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

    # If this button is pressed, it will save the current Wishlist trip to the session memory and the database
    if st.button("Save Wishlist Trip"):
        # Must provide a name
        if not wish_park_name:
            st.error("Please provide a park name.")
        else:
            # Wishlist trip saved to DB
            try:
                user = st.session_state.get("user")
                if not user:
                    st.error("You must be logged in to save wishlist trips.")
                else:
                    user_id = user["user_id"]

                    con = get_connection()
                    cur = con.cursor()
                    cur.execute(
                        """
                        INSERT INTO WISHLIST_TRIP (user_id, park_id, target_season, notes)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (user_id, wish_park_id, wish_season, wish_notes),
                    )
                    con.commit()
                    wishlist_id = cur.lastrowid

                    st.success("Wishlist trip saved.")

                    # Keep an in-memory copy for this session
                    st.session_state.wishlist_trips.append(
                        {
                            "wishlist_id": wishlist_id,
                            "park_id": wish_park_id,
                            "park_name": wish_park_name,
                            "target_season": wish_season,
                            "notes": wish_notes,
                        }
                    )
            # Exception handling
            except Exception as e:
                st.error(f"Failed to save wishlist trip: {e}")
            finally:
                try:
                    con.close()
                except NameError:
                    pass

    st.markdown("### Your wishlist trips")

    # If there are no wishlist trips for the user, then the default will be displayed
    if not st.session_state.wishlist_trips:
        st.info("No wishlist trips yet.")
    else:
        user = st.session_state.get("user")
        user_id = user["user_id"] if user else None

        # Each Wishlist trip is saved in its own container for later edits and display
        for i, wish in enumerate(st.session_state.wishlist_trips, start=1):
            with st.container(border=True):
                st.markdown(f"**{i}. {wish['park_name']}**")

                # Editable season - this allows the user to modify previosly made Wishlist trips
                new_season = st.selectbox(
                    "Season",
                    ["Spring", "Summer", "Fall", "Winter"],
                    index=["Spring", "Summer", "Fall", "Winter"].index(
                        wish.get("target_season", "Spring")
                    ),
                    #As each entry for wishlist trips is associated to a entry in the array, we can call its index to access it
                    key=f"edit_wish_season_{wish['wishlist_id']}",
                )

                # Editable notes
                new_notes = st.text_area(
                    "Notes",
                    value=wish.get("notes", "") or "",
                    key=f"edit_wish_notes_{wish['wishlist_id']}",
                )

                # This button will save any changes the user made to the entry and update it in the database
                if st.button(
                    "Save changes",
                    key=f"save_wish_{wish['wishlist_id']}",
                ):
                    if not user_id:
                        st.error("You must be logged in to update wishlist trips.")
                    else:
                        try:
                            con = get_connection()
                            cur = con.cursor()
                            cur.execute(
                                """
                                UPDATE WISHLIST_TRIP
                                SET target_season = %s, notes = %s
                                WHERE wishlist_id = %s AND user_id = %s
                                """,
                                (
                                    new_season,
                                    new_notes,
                                    wish["wishlist_id"],
                                    user_id,
                                ),
                            )
                            con.commit()
                            st.success("Wishlist trip updated.")

                            # Update local copy too
                            wish["target_season"] = new_season
                            wish["notes"] = new_notes
                            st.rerun()
                        # Exception handling
                        except Exception as e:
                            st.error(f"Failed to update wishlist trip: {e}")
                        finally:
                            try:
                                con.close()
                            except NameError:
                                pass
