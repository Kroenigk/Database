# Trails Page
import os
import streamlit as st
from frontend.park_data import get_parks
import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# --- user auth guard ---
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

# --------- UI components ---------
# Page title and description with tabs rendering below
st.title("🏞️ Trails Explorer")
st.caption("Explore trails in national parks across the country.")
st.markdown("---")
trail_tab, trail_review_tab = st.tabs(["Trail Explorer", "Trail Reviews"])

# ---------------- Trail Explorer helpers ----------------
def render_trail_list():
    # Simply lists all trails across all parks
    st.header("All Trails")
    parks = get_parks()

    # Get user session info for API calls
    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found.")
        return

    trail_data = []
    for park in parks:
        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/{park['park_id']}/trails",
                cookies={"session_id": session_id},
                timeout=5,
            )
        #exception handling
        except Exception as e:
            st.error(f"Error contacting backend for park {park['name']}: {e}")
            continue

        #process response if successful
        if resp.status_code == 200:
            trails = resp.json().get("trails", [])
            continue
            for trail in trails:
                trail_data.append({
                    "Park Name": park["name"],
                    "Trail Name": trail["name"],
                    "Length (miles)": trail["length_miles"],
                    "Difficulty": trail["difficulty"],
                })

    if not trail_data:
        st.info("No trails found.")
        return

    # Display the collected trail data in a table
    st.table(trail_data)

# ---------------- Trail Explorer filters ----------------
# This will filter trails based on state, park, difficulty, length range

# Filter trails by state
def trail_by_state(state_code: str):
    st.header(f"Trails in {state_code}")

    # Get parks in the specified state so we can fetch their trails
    parks = get_parks(state_code=state_code)

    # Get user session info for API calls
    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found for this state.")
        return

    trail_data = []
    # Fetch trails for each park in the state
    for park in parks:
        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/{park['park_id']}/trails",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend for park {park['name']}: {e}")
            continue

        # If response is successful, process the trails
        if resp.status_code == 200:
            trails = resp.json().get("trails", [])
            for trail in trails:
                trail_data.append({
                    "Park Name": park["name"],
                    "Trail Name": trail["name"],
                    "Length (miles)": trail["length_miles"],
                    "Difficulty": trail["difficulty"],
                })

    if not trail_data:
        st.info("No trails found for this state.")
        return

    # Display the collected trail data in a table
    st.table(trail_data)

# Filter trails by park ID
def trail_by_park(park_id: int):
    st.header(f"Trails in Park ID: {park_id}")

    # Get user session info for API calls
    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    # Fetch trails for the specified park
    try:
        resp = requests.get(
            f"{API_BASE}/api/parks/{park_id}/trails",
            cookies={"session_id": session_id},
            timeout=5,
        )
    #exception handling
    except Exception as e:
        st.error(f"Error contacting backend: {e}")
        return

    if resp.status_code != 200:
        st.info("No trails found for this park.")
        return

    #process response
    trails = resp.json().get("trails", [])
    if not trails:
        st.info("No trails found for this park.")
        return

    trail_data = []
    for trail in trails:
        trail_data.append({
            "Trail Name": trail["name"],
            "Length (miles)": trail["length_miles"],
            "Difficulty": trail["difficulty"],
        })

    # Display the collected trail data in a table
    st.table(trail_data)

# Filter trails by difficulty
def trail_by_difficulty(difficulty: str):
    st.header(f"Trails with Difficulty: {difficulty}")
    parks = get_parks()

    # Get user session info for API calls
    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found.")
        return

    # Fetch trails for each park with the specified difficulty
    trail_data = []
    for park in parks:
        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/{park['park_id']}/trails?difficulty={difficulty}",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend for park {park['name']}: {e}")
            continue

        # If response is successful, process the trails
        if resp.status_code == 200:
            trails = resp.json().get("trails", [])
            for trail in trails:
                trail_data.append({
                    "Park Name": park["name"],
                    "Trail Name": trail["name"],
                    "Length (miles)": trail["length_miles"],
                    "Difficulty": trail["difficulty"],
                })

    if not trail_data:
        st.info("No trails found with this difficulty.")
        return

    # Display the collected trail data in a table
    st.table(trail_data)

# Filter trails by length range in miles
def trail_by_length(min_length: float, max_length: float):
    st.header(f"Trails with Length between {min_length} miles and {max_length} miles")
    parks = get_parks()

    # Get user session info for API calls
    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found.")
        return

    # Fetch trails for each park within the specified length range
    trail_data = []
    for park in parks:
        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/{park['park_id']}/trails"
                f"?min_length={min_length}&max_length={max_length}",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend for park {park['name']}: {e}")
            continue

        # If response is successful, process the trails
        if resp.status_code == 200:
            trails = resp.json().get("trails", [])
            for trail in trails:
                trail_data.append({
                    "Park Name": park["name"],
                    "Trail Name": trail["name"],
                    "Length (miles)": trail["length_miles"],
                    "Difficulty": trail["difficulty"],
                })

    if not trail_data:
        st.info("No trails found within this length range.")
        return

    # Display the collected trail data in a table
    st.table(trail_data)

    


# ---------------- Trail Explorer tab ----------------
# This will render the trail explorer with filtering options
with trail_tab:
    st.subheader("Trail Explorer")

    # Filter mode selection
    filter_mode = st.selectbox(
        "Filter trails by:",
        ["All", "State", "Park ID", "Difficulty", "Length range"],
    )

    # If all filter mode is selected, render the full trail list
    if filter_mode == "All":
        render_trail_list()

    # If state filter mode is selected, get state code input and render trails by state
    elif filter_mode == "State":
        state_code = st.text_input("State code (e.g. CA, OH, UT)").upper().strip()
        if state_code:
            trail_by_state(state_code)

    # If park ID filter mode is selected, get park selection and render trails by park
    elif filter_mode == "Park ID":
        # Get parks for the dropdown
        parks = get_parks()
        park_names = [f"{p['name']} - ID: {p['park_id']}" for p in parks]
        park_choice = st.selectbox(
            "Select a park",
            ["(none)"] + park_names,
            index=0,
        )
        # Map back to park ID if a park is selected
        if park_choice != "(none)":
            idx = park_names.index(park_choice)
            park_id = parks[idx]["park_id"]
        if park_id:
            trail_by_park(park_id)

    # If difficulty filter mode is selected, get difficulty input and render trails by difficulty
    elif filter_mode == "Difficulty":
        difficulty = st.selectbox("Difficulty", ["easy", "moderate", "strenuous", "hard"])
        trail_by_difficulty(difficulty)

    # If length range filter mode is selected, get min/max length inputs and render trails by length
    elif filter_mode == "Length range":
        min_len = st.number_input("Min length (miles)", min_value=0.0, value=0.0)
        max_len = st.number_input("Max length (miles)", min_value=0.0, value=10.0)
        if max_len >= min_len:
            trail_by_length(min_len, max_len)
        else:
            st.error("Max length must be greater than or equal to min length.")


# ---------------- Trail Reviews tab ----------------
# This is for the users to view their trail reviews and submit own
with trail_review_tab:
    st.header("Trail Reviews")

    # Function to render user's trail reviews and allow submitting new ones
    def render_trail_reviews():
        st.subheader("My Trail Reviews")

        # --- Require login & get session_id ---
        user = st.session_state.get("user")
        if not user:
            st.warning("You must be logged in to create and view reviews.")
            st.stop()

        session_id = str(user["session_id"])

        # Build a list of all trails (name, id) for the dropdown
        trails = []
        parks = get_parks()
        for park in parks:
            try:
                resp = requests.get(
                    f"{API_BASE}/api/parks/{park['park_id']}/trails",
                    cookies={"session_id": session_id},
                    timeout=5,
                )
            #exception handling
            except Exception as e:
                st.error(f"Error contacting backend for park {park['name']}: {e}")
                continue

            #process response
            if resp.status_code == 200:
                park_trails = resp.json().get("trails", [])
                for trail in park_trails:
                    trails.append((trail["name"], trail["trail_id"]))

        if not trails:
            st.info("No trails available for reviews.")
            return

        # Dropdown to select a trail to review
        trail_names = [t[0] for t in trails]
        selected_trail_name = st.selectbox(
            "Select a trail to view / review",
            ["(none)"] + trail_names,
        )
        if selected_trail_name == "(none)":
            return

        selected_trail_id = trails[trail_names.index(selected_trail_name)][1]

        # Submit a review - this can be moved to its own function if needed
        st.subheader("Submit a Review")
        rating = st.slider("Rating (1–5)", 1, 5, 3)
        review_text = st.text_area("Write your review here")

        if st.button("Submit Review"):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/trails/{selected_trail_id}/reviews",
                    cookies={"session_id": session_id},
                    json={"rating": rating, "review_text": review_text},
                    timeout=5,
                )
                data = resp.json()
                if resp.status_code != 201:
                    st.error(data.get("error", "Failed to submit review"))
                else:
                    st.success("Review submitted successfully!")
            except Exception as e:
                st.error(f"Error contacting backend: {e}")

        # Display existing reviews
        st.subheader("Existing Reviews")
        try:
            resp = requests.get(
                f"{API_BASE}/api/trails/reviews",
                cookies={"session_id": session_id},
                timeout=5,
            )
            if resp.status_code != 200:
                st.info("No reviews found.")
                return

            reviews = resp.json().get("reviews", [])
            if not reviews:
                st.info("No reviews found.")
                return

            # Display each review
            for review in reviews:
                st.write(f"**Rating:** {review['rating']} / 5")
                st.write(f"**Review:** {review['review_text']}")
                st.write(f"**Date:** {review['created_at']}")
                st.markdown("---")
        except Exception as e:
            st.error(f"Error contacting backend: {e}")

    # Call the function to render trail reviews
    render_trail_reviews()
