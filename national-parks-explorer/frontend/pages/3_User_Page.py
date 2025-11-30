# frontend/pages/3_user_page.py

import os
import requests
import streamlit as st

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

def remove_from_favorites(park_id: str):
    user = st.session_state.get("user")
    if not user:
        st.error("You must be logged in to remove favorites.")
        return

    session_id = str(user["session_id"])  # <-- cast to str

    try:
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
    st.subheader("Profile")
    st.write(f"**User ID:** {user.get('user_id')}")
    st.write(f"**Username:** {user.get('username')}")
    st.write(f"**Role:** {user.get('role', 'user')}")
    st.write(f"**Session ID:** `{session_id}`")

    st.markdown("---")
    if st.button("Log out"):
        # inform Flask backend too
        try:
            requests.post(
                f"{API_BASE}/api/auth/logout",
                cookies={"session_id": session_id},
                timeout=5,
            )
        except Exception:
            pass

        st.session_state.authenticated = False
        st.session_state.user = None
        st.success("Logged out. Go back to the main page to log in again.")
        st.stop()

# ---------------- Favorites tab ----------------
with tab_favorites:
    st.subheader("Favorite Parks")

    if not session_id:
        st.error("No session_id available; please log in again.")
    else:
        # GET /api/parks/favorites
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
                        st.markdown(f"**{fav['name']}**")
                        st.caption(f"{fav['designation']} · ID: {fav['park_id']}")
                        if st.button("Remove from Favorites", key=f"remove_fav_{fav['park_id']}"):
                            remove_from_favorites(fav['park_id'])
                            st.success(f"Removed {fav['name']} from favorites.")
                            st.rerun()

# ---------------- Reviews tab ----------------
with tab_reviews:
    st.subheader("My Reviews")
    st.info(
        "This section will list your park and trail reviews once backend "
        "endpoints for per-user reviews are in place."
    )
