# Campgrounds Page
import os
import requests
import streamlit as st

from frontend.park_data import get_parks, get_states

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# --- user auth guard ---
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

# This is the main title and caption for the Campgrounds Explorer page
st.title("🏕️ Campgrounds Explorer")
st.caption("Discover campgrounds across national parks.")

campgrounds_tab, reservations_tab = st.tabs(["Campgrounds", "Reservations"])

# ---------------- CAMPGROUNDS TAB ----------------
with campgrounds_tab:
    st.markdown("---")

    # Helper function to extract park_id from a park dictionary
    def _get_park_id(park: dict):
        return park.get("park_id")

    def _render_campground_table(campground_data: list[dict]) -> None:
        """Render campground info in a table instead of cards."""
        if not campground_data:
            st.info("No campgrounds found.")
            return

        st.subheader("Campground Results")
        st.table(campground_data)  # use st.dataframe(...) if you want sortable columns

    def render_campground_list() -> None:
        """Render all campgrounds across all parks."""
        st.header("All Campgrounds")

        parks = get_parks()
        if not parks:
            st.info("No parks found.")
            return

        user = st.session_state.get("user")
        if not user or "session_id" not in user:
            st.error("No user session found. Please log in again.")
            return

        session_id = str(user["session_id"])
        campground_data: list[dict] = []

        for park in parks:
            park_id = park.get("park_id")
            if not park_id:
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
                st.warning(
                    f"Backend returned {resp.status_code} for campgrounds in park {park['name']}."
                )
                continue

            data = resp.json()
            campgrounds = data.get("campgrounds", [])

            for cg in campgrounds:
                campground_data.append(
                    {
                        "Park Name": park["name"],
                        "Campground Name": cg.get("name", "Unknown"),
                        "Latitude": cg.get("latitude"),
                        "Longitude": cg.get("longitude"),
                        "Description": cg.get("description"),
                    }
                )

        _render_campground_table(campground_data)

    def campground_by_state(state_code: str) -> None:
        """Render campgrounds filtered by state code."""
        st.header(f"Campgrounds in {state_code}")

        parks = get_parks(state_code=state_code)
        if not parks:
            st.info("No parks found for this state.")
            return

        user = st.session_state.get("user")
        if not user or "session_id" not in user:
            st.error("No user session found. Please log in again.")
            return

        session_id = str(user["session_id"])
        campground_data: list[dict] = []

        for park in parks:
            park_id = _get_park_id(park)
            if not park_id:
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
                st.warning(
                    f"Backend returned {resp.status_code} for campgrounds in park {park['name']}."
                )
                continue

            data = resp.json()
            campgrounds = data.get("campgrounds", [])

            for cg in campgrounds:
                campground_data.append(
                    {
                        "Park Name": park["name"],
                        "Campground Name": cg.get("name", "Unknown"),
                        "Latitude": cg.get("latitude"),
                        "Longitude": cg.get("longitude"),
                        "Description": cg.get("description"),
                    }
                )

        _render_campground_table(campground_data)

    def campground_by_park(park_id: str) -> None:
        """Render campgrounds for a specific park_id."""
        st.header(f"Campgrounds in Park ID: {park_id}")

        user = st.session_state.get("user")
        if not user or "session_id" not in user:
            st.error("No user session found. Please log in again.")
            return

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

        campground_data: list[dict] = []
        for cg in campgrounds:
            campground_data.append(
                {
                    "Campground Name": cg.get("name", "Unknown"),
                    "Latitude": cg.get("latitude"),
                    "Longitude": cg.get("longitude"),
                    "Description": cg.get("description"),
                }
            )

        _render_campground_table(campground_data)

    # ---- Filter UI (inside the Campgrounds tab) ----
    filter_mode = st.selectbox(
        "Filter campgrounds by:",
        ["All", "State", "Park Name"],
    )

    if filter_mode == "All":
        render_campground_list()

    elif filter_mode == "State":
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
        if not parks:
            st.info("No parks found.")
        else:
            park_names = [f"{p['name']} ({p['states']})" for p in parks]
            park_choice = st.sidebar.selectbox("Park", ["(none)"] + park_names, index=0)

            park_id = None
            if park_choice != "(none)":
                idx = park_names.index(park_choice)
                park_id = _get_park_id(parks[idx])

            if park_id:
                campground_by_park(park_id)

# ---------------- RESERVATIONS TAB ----------------
with reservations_tab:
    st.markdown("---")
    st.info("Current Reservations")

    def delete_reservation(reservation_id: int) -> bool:
        """Delete a reservation by reservation_id."""
        user = st.session_state.get("user")
        if not user:
            st.error("You must be logged in.")
            return False

        session_id = str(user["session_id"])
        try:
            resp = requests.delete(
                f"{API_BASE}/api/campgrounds/reservations/{reservation_id}",
                cookies={"session_id": session_id},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            st.error(f"Error contacting backend: {e}")
            return False

    def render_reservations() -> None:
        """Render current user's reservations."""
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

        for idx, res in enumerate(reservations):
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.write(f"**Campground:** {res['campground_name']}")
                    st.write(f"**Park:** {res['park_name']}")
                    st.write(f"**Dates:** {res['start_date']} to {res['end_date']}")
                    st.write(f"**Status:** {res['status']}")
                
                with col2:
                    if st.button("🗑️ Cancel", key=f"delete_res_{idx}"):
                        if delete_reservation(res['reservation_id']):
                            st.success("Reservation cancelled!")
                            st.rerun()
                        else:
                            st.error("Failed to cancel reservation")

    def make_reservation() -> None:
        """Allow user to make a new campground reservation."""
        st.header("Make a Reservation")

        user = st.session_state.get("user")
        if not user:
            st.error("You must be logged in.")
            return

        session_id = str(user["session_id"])

        campgrounds: list[dict] = []
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

        campground_names = [
            f"{cg['name']} (Park ID: {cg['park_id']})" for cg in campgrounds
        ]
        campground_choice = st.selectbox(
            "Select Campground",
            ["(none)"] + campground_names,
            index=0,
        )

        if campground_choice == "(none)":
            st.info("Please select a campground.")
            return

        idx = campground_names.index(campground_choice)
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

            if resp.status_code not in (200, 201):
                try:
                    data = resp.json()
                    st.error(data.get("error", "Failed to make reservation."))
                except Exception:
                    st.error("Failed to make reservation.")
            else:
                st.success("Reservation made successfully!")
                st.toast("Reservation submitted ✅")
                st.rerun()

    # Main UI for reservations tab
    render_reservations()
    st.markdown("---")
    make_reservation()
