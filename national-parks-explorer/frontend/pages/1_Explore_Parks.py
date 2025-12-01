# Main explorer (parks, filters, cards)
import streamlit as st
from park_data import (
    get_states,
    get_parks,
    get_park_detail,
    get_basic_counts,
)
from backend.db import get_connection
import requests
import os

# We will make API calls to our backend that is running at this URL.
# This way we can update the database without directly interacting with it in places
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# --- user auth guard ---
# The user must be logged in to access this page
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

# --------- UI components ---------
# The sidebar allows the user to filter by park name and by state in the main park explorer window
def render_sidebar():
    st.sidebar.title("National Parks Explorer")
    st.sidebar.write("Filter parks by state and name to get started.")

    # This gets all the states available and creates a drop down for the user to select from
    states = get_states()
    state_options = ["ALL"] + [f"{s['code']} - {s['name']}" for s in states]
    state_choice = st.sidebar.selectbox("State", state_options, index=0)

    state_code = "ALL" if state_choice == "ALL" else state_choice.split(" - ")[0]

    # The user can also search for a national park by name if it is known
    search = st.sidebar.text_input("Search by park name")

    st.sidebar.markdown("---")

    # This displays the basic counts of the info that is avaliable
    counts = get_basic_counts()
    st.sidebar.metric("Parks", counts.get("parks", 0))
    st.sidebar.metric("Campgrounds", counts.get("campgrounds", 0))
    st.sidebar.metric("Trails", counts.get("trails", 0))
    st.sidebar.metric("Alerts", counts.get("alerts", 0))

    return search, state_code


def render_park_list(search, state_code):
    # This builds a table of all the parks that are found and displays some of their info for the user 
    # based on the user's previously placed filters such as state and park name
    st.header("Parks")
    parks = get_parks(search=search, state_code=state_code)

    if not parks:
        st.info("No parks found for this filter.")
        return None

    # Parks that match will be displayed in the table
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

    # This is a drop down that allows a user to select a particular park for more information
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

# This function allows a user to add a park to their favorites through an API call to the backend
def add_to_favorites(park_id: str):
    user = st.session_state.get("user")
    if not user:
        st.error("You must be logged in.")
        return

    # This action is logged to the API
    session_id = str(user["session_id"]) 

    try:
        # It tries to post the information to the database through a POST request that will be reflected to the database
        resp = requests.post(
            f"{API_BASE}/api/parks/{park_id}/favorite",
            cookies={"session_id": session_id},
            timeout=5,
        )
        data = resp.json()
        if resp.status_code != 200:
            st.error(data.get("error", "Failed to favorite park."))
        else:
            st.success("Added to favorites!")
    # Exception handling
    except Exception as e:
        st.error(f"Error contacting backend: {e}")

def make_reservation(park_id: str):
    st.info(f"[placeholder] Reservation flow for park {park_id}.")


def make_park_tag(park_id: str):
    st.info(f"[placeholder] Tag flow for park {park_id}.")


# This function will display all the information of a given park on the main Park Explorer page
def render_park_detail(park_id: str):
    # These buttons allow the user to add a park to their favorites, add a park tag, and make a reservation to the park
    col1Button, col2Button, col3Button = st.columns([3,1,1])
    with col1Button:
        if st.button("Add to Favorites"):
            add_to_favorites(park_id)
    with col2Button:
        if st.button("Make a Reservation"):
            make_reservation(park_id)
    with col3Button:
        if st.button("Add Park Tag"):
            add_park_tag(park_id)

    # This gets all of the necessary info related to the park so it can be displayed later
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

    # Campgrounds - this is in a table format
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

    # Trails - this is in a table format
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

    # Alerts - this has a expanded if the user desires more information
    st.subheader("Current Alerts")
    if detail["alerts"]:
        for category, title, desc, issued_at in detail["alerts"]:
            with st.expander(f"{category or 'Alert'}: {title}"):
                if issued_at:
                    st.caption(f"Issued at: {issued_at}")
                st.write(desc or "No description provided.")
    else:
        st.write("No current alerts for this park.")


# --------- Page entry ---------
st.set_page_config(page_title="National Parks Explorer", layout="wide")

search, state_code = render_sidebar()
selected_park_id = render_park_list(search, state_code)

if selected_park_id:
    st.markdown("---")
    render_park_detail(selected_park_id)
else:
    st.markdown("### Select a park from the dropdown to view details.")
