# Campgrounds Page
import os
import streamlit as st
from frontend.park_data import get_parks, get_states
import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# --- user auth guard ---
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

st.title("🏕️ Campgrounds Explorer")
st.caption("Discover campgrounds across national parks.")

campgrounds_tab, reservations_tab = st.tabs(["Campgrounds", "Reservations"])

# ---------------- CAMPGROUNDS TAB ----------------
with campgrounds_tab:
    st.markdown("---")

    def _get_park_id(park: dict):
        return park.get("park_id")

    def _render_campground_cards(campground_data):
        # Renders campground info cards from a list of campground data
        if not campground_data:
            st.info("No campgrounds found.")
            return

        for cg in campground_data:
            st.write(f"**Park Name:** {cg.get('Park Name', 'N/A')}")
            st.write(f"**Campground Name:** {cg['Campground Name']}")
            st.write(f"**Latitude:** {cg.get('Latitude', 'N/A')}")
            st.write(f"**Longitude:** {cg.get('Longitude', 'N/A')}")
            st.write(f"**Description:** {cg.get('Description', 'N/A')}")
            st.markdown("---")

    def render_campground_list():
        st.header("All Campgrounds")
        parks = get_parks()

        user = st.session_state.get("user")
        session_id = str(user["session_id"])

        if not parks:
            st.info("No parks found.")
            return

        campground_data = []
        for park in parks:
            park_id = park["park_id"]
            if park_id is None:
                continue

            try:
                resp = requests.get(
                    f"{API_BASE}/api/parks/{park_id}/campgrounds",
                    cookies={"session_id": session_id},
                    timeout=5,
                )
            except Exception as e:
                st.error(f"Error contacting backend for park {park['name']}: {e}")
                continue

            if resp.status_code != 200:
                continue

            data = resp.json()
            campgrounds = data.get("campgrounds", [])
            for cg in campgrounds:
                campground_data.append({
                    "Park Name": park["name"],
                    "Campground Name": cg["name"],
                    "Latitude": cg["latitude"],
                    "Longitude": cg["longitude"],
                    "Description": cg["description"],
                })

        _render_campground_cards(campground_data)

    def campground_by_state(state_code: str):
        st.header(f"Campgrounds in {state_code}")
        parks = get_parks(state_code=state_code)

        user = st.session_state.get("user")
        session_id = str(user["session_id"])

        if not parks:
            st.info("No parks found for this state.")
            return

        campground_data = []
        for park in parks:
            park_id = _get_park_id(park)
            if park_id is None:
                continue

            try:
                resp = requests.get(
                    f"{API_BASE}/api/parks/{park_id}/campgrounds",
                    cookies={"session_id": session_id},
                    timeout=5,
                )
            except Exception as e:
                st.error(f"Error contacting backend for park {park['name']}: {e}")
                continue

            if resp.status_code != 200:
                continue

            data = resp.json()
            campgrounds = data.get("campgrounds", [])
            for cg in campgrounds:
                campground_data.append({
                    "Park Name": park["name"],
                    "Campground Name": cg["name"],
                    "Latitude": cg["latitude"],
                    "Longitude": cg["longitude"],
                    "Description": cg["description"],
                })

        _render_campground_cards(campground_data)

    def campground_by_park(park_id: int):
        st.header(f"Campgrounds in Park ID: {park_id}")

        user = st.session_state.get("user")
        session_id = str(user["session_id"])

        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/{park_id}/campgrounds",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend: {e}")
            return

        if resp.status_code != 200:
            st.info("No campgrounds found for this park.")
            return

        data = resp.json()
        campgrounds = data.get("campgrounds", [])
        if not campgrounds:
            st.info("No campgrounds found for this park.")
            return

        campground_data = []
        for cg in campgrounds:
            campground_data.append({
                "Campground Name": cg["name"],
                "Latitude": cg["latitude"],
                "Longitude": cg["longitude"],
                "Description": cg["description"],
            })

        _render_campground_cards(campground_data)

    # ---- Filter UI (inside the Campgrounds tab) ----
    filter_mode = st.selectbox(
        "Filter campgrounds by:",
        ["All", "State", "Park Name"],
    )

    if filter_mode == "All":
        render_campground_list()

    elif filter_mode == "State":
        # This gets all the states available and creates a drop down for the user to select from
        states = get_states()
        state_options = ["ALL"] + [f"{s['code']} - {s['name']}" for s in states]
        state_choice = st.sidebar.selectbox("State", state_options, index=0)

        state_code = None if state_choice == "ALL" else state_choice.split(" - ")[0]

        if state_code is None:
            render_campground_list()
        else:
            campground_by_state(state_code)

    elif filter_mode == "Park Name":
        parks = get_parks()
        park_names = [f"{p['name']} ({p['states']})" for p in parks]
        park_choice = st.sidebar.selectbox("Park", ["(none)"] + park_names, index=0)

        park_id = None
        if park_choice != "(none)":
            idx = park_names.index(park_choice)
            park_id = _get_park_id(parks[idx])

        if park_id:
            campground_by_park(int(park_id))

# ---------------- RESERVATIONS TAB ----------------
with reservations_tab:
    st.markdown("---")
    st.info("Current Reservations")

    def render_reservations():
        user = st.session_state.get("user")
        if not user:
            st.error("You must be logged in.")
            return

        session_id = str(user["session_id"])
        try:
            resp = requests.get(
                f"{API_BASE}/api/campgrounds/reservations",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend: {e}")
            return

        if resp.status_code != 200:
            st.info("Could not load reservations.")
            return

        reservations = resp.json().get("reservations", [])
        if not reservations:
            st.info("You have no reservations.")
            return

        for res in reservations:
            st.write(f"**Campground Name:** {res['campground_name']}")
            st.write(f"**Park Name:** {res['park_name']}")
            st.write(f"**Start Date:** {res['start_date']}")
            st.write(f"**End Date:** {res['end_date']}")
            st.write(f"**Status:** {res['status']}")
            st.markdown("---")

    def make_reservation():
        st.header("Make a Reservation")
        user = st.session_state.get("user")
        if not user:
            st.error("You must be logged in.")
            return

        session_id = str(user["session_id"])

    
        campgrounds = []      
        # Fetch all campgrounds for selection
        try:
            resp = requests.get(
                f"{API_BASE}/api/campgrounds",
                cookies={"session_id": session_id},
                timeout=5,
            )
            if resp.status_code == 200:
                campgrounds = resp.json().get("campgrounds", [])
        except Exception as e:
            st.error(f"Error contacting backend: {e}")
            return
        
        campground_names = [f"{cg['name']} (Park ID: {cg['park_id']})" for cg in campgrounds]
        campground_name = st.selectbox("Select Campground", ["(none)"] + campground_names, index=0)
        if campground_name == "(none)":
            st.info("Please select a campground.")
            return
        idx = campground_names.index(campground_name)
        campground_id = campgrounds[idx]["campground_id"]
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")

        if st.button("Submit Reservation"):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/campgrounds/reservations",
                    cookies={"session_id": session_id},
                    json={
                        "campground_id": campground_id,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "status": "PENDING",
                    },
                    timeout=5,
                )
            except Exception as e:
                st.error(f"Error contacting backend: {e}")
                return

            # assume backend returns 201 on success; adjust if needed
            if resp.status_code not in (200, 201):
                data = resp.json()
                st.error(data.get("error", "Failed to make reservation."))
            else:
                st.success("Reservation made successfully!")
                # quick popup notification
                st.toast("Reservation submitted ✅")

    # Main UI for reservations tab
    render_reservations()
    st.markdown("---")
    make_reservation()
