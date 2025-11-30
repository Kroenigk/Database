# Main explorer (parks, filters, cards)
import streamlit as st
from park_data import (
    get_states,
    get_parks,
    get_park_detail,
    get_basic_counts,
)

# --- user auth guard ---
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

# --------- UI components ---------

def render_sidebar():
    st.sidebar.title("National Parks Explorer")
    st.sidebar.write("Filter parks by state and name to get started.")

    states = get_states()
    state_options = ["ALL"] + [f"{s['code']} - {s['name']}" for s in states]
    state_choice = st.sidebar.selectbox("State", state_options, index=0)

    state_code = "ALL" if state_choice == "ALL" else state_choice.split(" - ")[0]
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


def add_to_favorites(park_id: str):
    st.success(f"[placeholder] Added park {park_id} to favorites.")


def make_reservation(park_id: str):
    st.info(f"[placeholder] Reservation flow for park {park_id}.")


def make_park_tag(park_id: str):
    st.info(f"[placeholder] Tag flow for park {park_id}.")


def render_park_detail(park_id: str):
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


# --------- Page entry ---------
st.set_page_config(page_title="National Parks Explorer", layout="wide")

search, state_code = render_sidebar()
selected_park_id = render_park_list(search, state_code)

if selected_park_id:
    st.markdown("---")
    render_park_detail(selected_park_id)
else:
    st.markdown("### Select a park from the dropdown to view details.")
