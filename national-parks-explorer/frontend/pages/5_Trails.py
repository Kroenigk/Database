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
st.title("🏞️ Trails Explorer")
st.caption("Explore trails in national parks across the country.")
st.markdown("---")
trail_tab, trail_review_tab = st.tabs(["Trail Explorer", "Trail Reviews"])

# ---------------- Trail Explorer helpers ----------------
def render_trail_list():
    # Simply lists all trails across all parks
    st.header("All Trails")
    parks = get_parks()

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
        except Exception as e:
            st.error(f"Error contacting backend for park {park['name']}: {e}")
            continue

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

    st.table(trail_data)


def trail_by_state(state_code: str):
    st.header(f"Trails in {state_code}")
    parks = get_parks(state_code=state_code)

    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found for this state.")
        return

    trail_data = []
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

    st.table(trail_data)


def trail_by_park(park_id: int):
    st.header(f"Trails in Park ID: {park_id}")

    user = st.session_state.get("user")
    session_id = str(user["session_id"])
    try:
        resp = requests.get(
            f"{API_BASE}/api/parks/{park_id}/trails",
            cookies={"session_id": session_id},
            timeout=5,
        )
    except Exception as e:
        st.error(f"Error contacting backend: {e}")
        return

    if resp.status_code != 200:
        st.info("No trails found for this park.")
        return

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

    st.table(trail_data)


def trail_by_difficulty(difficulty: str):
    st.header(f"Trails with Difficulty: {difficulty}")
    parks = get_parks()

    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found.")
        return

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

    st.table(trail_data)


def trail_by_length(min_length: float, max_length: float):
    st.header(f"Trails with Length between {min_length} miles and {max_length} miles")
    parks = get_parks()

    user = st.session_state.get("user")
    session_id = str(user["session_id"])

    if not parks:
        st.info("No parks found.")
        return

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

    st.table(trail_data)


# ---------------- Trail Explorer tab ----------------
with trail_tab:
    st.subheader("Trail Explorer")

    filter_mode = st.selectbox(
        "Filter trails by:",
        ["All", "State", "Park ID", "Difficulty", "Length range"],
    )

    if filter_mode == "All":
        render_trail_list()

    elif filter_mode == "State":
        state_code = st.text_input("State code (e.g. CA, OH, UT)").upper().strip()
        if state_code:
            trail_by_state(state_code)

    elif filter_mode == "Park ID":
        parks = get_parks()
        park_names = [f"{p['name']} - ID: {p['park_id']}" for p in parks]
        park_choice = st.selectbox(
            "Select a park",
            ["(none)"] + park_names,
            index=0,
        )
        if park_choice != "(none)":
            idx = park_names.index(park_choice)
            park_id = parks[idx]["park_id"]
        if park_id:
            trail_by_park(park_id)

    elif filter_mode == "Difficulty":
        difficulty = st.selectbox("Difficulty", ["easy", "moderate", "strenuous", "hard"])
        trail_by_difficulty(difficulty)

    elif filter_mode == "Length range":
        min_len = st.number_input("Min length (miles)", min_value=0.0, value=0.0)
        max_len = st.number_input("Max length (miles)", min_value=0.0, value=10.0)
        if max_len >= min_len:
            trail_by_length(min_len, max_len)
        else:
            st.error("Max length must be greater than or equal to min length.")


# ---------------- Trail Reviews tab ----------------
with trail_review_tab:
    st.header("Trail Reviews")

    def render_trail_reviews():
        st.subheader("My Trail Reviews")

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
            except Exception as e:
                st.error(f"Error contacting backend for park {park['name']}: {e}")
                continue

            if resp.status_code == 200:
                park_trails = resp.json().get("trails", [])
                for trail in park_trails:
                    trails.append((trail["name"], trail["trail_id"]))

        if not trails:
            st.info("No trails available for reviews.")
            return

        trail_names = [t[0] for t in trails]
        selected_trail_name = st.selectbox(
            "Select a trail to view / review",
            ["(none)"] + trail_names,
        )
        if selected_trail_name == "(none)":
            return

        selected_trail_id = trails[trail_names.index(selected_trail_name)][1]

        # Submit a review
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

            for review in reviews:
                st.write(f"**Rating:** {review['rating']} / 5")
                st.write(f"**Review:** {review['review_text']}")
                st.write(f"**Date:** {review['created_at']}")
                st.markdown("---")
        except Exception as e:
            st.error(f"Error contacting backend: {e}")

    render_trail_reviews()
