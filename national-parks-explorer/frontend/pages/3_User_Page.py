import os
import requests
import streamlit as st
from frontend.park_data import get_parks

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ---- auth guard ----
if not st.session_state.get("authenticated", False) or not st.session_state.get("user"):
    st.warning("Please log in from the main page to view your user page.")
    st.stop()

user = st.session_state.user
session_id = str(user.get("session_id", ""))

st.title("👤 User Page")
st.caption(f"Logged in as {user.get('username', 'Unknown user')}")

tab_profile, tab_favorites, tab_reviews = st.tabs(
    ["Profile", "Favorite Parks", "My Reviews"]
)

# ------ Removes a Park from a Users favorites ---------
def remove_from_favorites(park_id: str):
    # uses the streamlit session state to get the current user's information
    user = st.session_state.get("user")
    if not user:
        st.error("You must be logged in to remove favorites.")
        return

    #Gets the session_id that is attached to the user session
    session_id = str(user["session_id"])

    try:
        #uses the flask API to delete the park from the user's favorities and attached the action to a session id
        resp = requests.delete(
            f"{API_BASE}/api/parks/{park_id}/favorite",
            cookies={"session_id": session_id},
            timeout=5,
        )
        data = resp.json()
        if resp.status_code != 200:
            st.error(data.get("error", "Failed to remove favorite"))
        else:
            st.success(f"Removed park {park_id} from favorites")
    except Exception as e:
        st.error(f"Error contacting backend: {e}")

# ---------------- Profile tab ----------------
with tab_profile:
    # This displays the user's basic information
    st.subheader("Profile")
    st.write(f"**User ID:** {user.get('user_id')}")
    st.write(f"**Username:** {user.get('username')}")
    st.write(f"**Role:** {user.get('role', 'user')}")
    st.write(f"**Session ID:** `{session_id}`")

    st.markdown("---")
    if st.button("Log out"):
        # inform Flask backend too that the user has logged out
        try:
            requests.post(
                f"{API_BASE}/api/auth/logout",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception:
            pass

        # Since the user has logged out, the session is no longer authenicated and there is no user
        st.session_state.authenticated = False
        st.session_state.user = None
        st.success("Logged out. Go back to the main page to log in again.")
        st.stop()

# ---------------- Favorites tab ----------------
with tab_favorites:
    # This displays the users favorite parks and their ids
    st.subheader("Favorite Parks")

    if not session_id:
        st.error("No session_id available; please log in again.")
    else:
        # GET /api/parks/favorites to access user favorite information so we don't ahve to directly take the the database
        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/favorites",
                cookies={"session_id": session_id},
                timeout=5,
            )
            data = resp.json()
        except Exception as e:
            data = {"error": str(e)}

        if data.get("error"):
            st.error(f"Could not load favorites: {data['error']}")
        else:
            favorites = data.get("favorites", [])
            if not favorites:
                st.info("You have no favorite parks yet.")
            else:
                for fav in favorites:
                    with st.container(border=True):
                        # Displays the park in its own container
                        st.markdown(f"**{fav['name']}**")
                        st.caption(f"{fav['designation']} · ID: {fav['park_id']}")
                        # A User can remove a park from their favorites by clicking a button
                        if st.button("Remove from Favorites", key=f"remove_fav_{fav['park_id']}"):
                            remove_from_favorites(fav['park_id'])
                            st.success(f"Removed {fav['name']} from favorites.")
                            st.rerun()

# ---------------- Reviews tab ----------------
with tab_reviews:
    # This section allows a user to view and submit reviews for parks
    st.subheader("My Reviews")

    # --- Require login ---
    user = st.session_state.get("user")
    if not user:
        st.warning("You must be logged in to view or submit reviews.")
        st.stop()

    session_id = str(user.get("session_id", ""))

    # Function to load and display user reviews
    def load_user_reviews():
        #Fetches current user's reviews from the backend and renders them.
        try:
            resp = requests.get(
                f"{API_BASE}/api/users/me/reviews",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend: {e}")
            return

        if resp.status_code != 200:
            st.info("Could not load your reviews.")
            return

        data = resp.json()
        # All of the reviews that are attached to the user will be placed in reviews to be displayed
        reviews = data.get("reviews", [])

        if not reviews:
            st.info("You haven't submitted any reviews yet.")
            return

        # Displays each review in its own section so that it is easy to read and functionality for updating can be implemented later
        for r in reviews:
            # adjust keys based on your backend shape
            st.write(f"**Park:** {r.get('park_name', 'Unknown park')}")
            st.write(f"**Rating:** {r['rating']} / 5")
            st.write(f"**Review:** {r['review_text']}")
            if r.get("created_at"):
                st.write(f"**Date:** {r['created_at']}")
            st.markdown("---")

    # Function to create and submit a new review
    def make_review():
        st.subheader("Write a New Review")

        # --- Require login & get session_id ---
        user = st.session_state.get("user")
        if not user:
            st.warning("Please log in to write a review.")
            return
        session_id = str(user["session_id"])

        # --- Get parks ---
        parks = get_parks()
        if not parks:
            st.info("No parks available to review.")
            return
        # Build labels and add a "(none)" option
        park_names = ["(none)"] + [f"{p['name']} ({p['park_id']})" for p in parks]

        # This is a drop down that allows a user to select a particular park to review
        choice = st.selectbox(
            "Select a National Park to Review",
            park_names,
            key="review_park_select",
        )

        # If no park is selected, inform the user to select one - this is the default option
        if choice == "(none)":
            st.info("Please select a park to review.")
            return

        # Map back from label to the chosen park
        idx = park_names.index(choice) - 1 
        selected_park = parks[idx]
        review_park_name = selected_park["name"]
        review_park_id = selected_park["park_id"]
        st.write(f"Reviewing: **{review_park_name}**")

        # --- Review inputs ---
        rating = st.slider("Rating (1–5)", 1, 5, 3)
        review_text = st.text_area("Review Text")

        # --- Submit review by calling API ---
        if st.button("Submit Review"):
            if not review_text.strip():
                st.error("Review text cannot be empty.")
                return
        try:
            resp = requests.post(
                f"{API_BASE}/api/parks/{review_park_id}/reviews",
                json={
                    "rating": rating,
                    "review_text": review_text,
                },
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception as e:
            st.error(f"Error contacting backend: {e}")
            return

        # Handle response
        try:
            data = resp.json()
        except Exception:
            st.error("Backend returned a non-JSON response.")
            return

        if resp.status_code != 201:
            st.error(data.get("error", "Failed to submit review."))
        else:
            st.success("Review submitted successfully!")
            st.toast("Review submitted ✅")
            load_user_reviews()

    # Render both sections
    load_user_reviews()
    st.markdown("---")
    make_review()
