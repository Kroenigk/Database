import os
import streamlit as st
import requests

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

# This is where the backend is running with all the necessary info
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# If login/signup is successful, it should redirect the user to this page
EXPLORE_PAGE = "pages/1_Explore_Parks.py"

st.set_page_config(page_title="National Parks Explorer", layout="wide")

# -------------------------------------------------------------------
# Session init
# -------------------------------------------------------------------

# The default is that there is no user and the session is not authenicated
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None


# -------------------------------------------------------------------
# Helper functions to call the Flask API
# -------------------------------------------------------------------

def login_via_api(email: str, password: str) -> dict:
    try:
        # Takes the given email and passwords to send to the Flash API 
        # It then looks at the APP_USER table to see if there exists a user that matches
        resp = requests.post(
            f"{API_BASE}/api/auth/login",
            # Note that it is checking for a user than matches the username or email AND password
            json={"username_or_email": email, "password": password},
            timeout=5,
        )
    except Exception as e:
        return {"error": f"Could not reach auth server: {e}"}

    # Try to parse JSON even on error
    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code != 200:
        return {"error": data.get("error", "Login failed")}

    # Grab the session_id cookie set by Flask
    # This will be used for the user session
    session_id = resp.cookies.get("session_id")
    if not session_id:
        return {"error": "No session_id cookie returned from backend."}

    try:
        # Given the credientials, it tries to get the full user info
        me_resp = requests.get(
            f"{API_BASE}/api/auth/me",
            cookies={"session_id": session_id},
            timeout=5,
        )
        me_data = me_resp.json()
        user_obj = me_data.get("user")
    except Exception as e:
        user_obj = None

    user_id = data.get("user_id")
    role = data.get("role")

    if user_obj:
        return {
            "user_id": user_obj["user_id"],
            "username": user_obj["username"],
            "role": user_obj.get("role", role),
            "session_id": user_obj["session_id"],
        }

    # Otherwise, we at least have user_id and role
    return {
        "user_id": user_id,
        "username": email, 
        "role": role,
        "session_id": session_id,
    }


def signup_via_api(username: str, email: str, password: str) -> dict:
    try:
        # This will create a new user in APP_USER with the provided information 
        resp = requests.post(
            f"{API_BASE}/api/auth/signup",
            json={"username": username, "email": email, "password": password},
            timeout=5,
        )
    except Exception as e:
        return {"error": f"Could not reach auth server: {e}"}

    try:
        data = resp.json()
    except Exception:
        data = {}

    if resp.status_code != 201:
        return {"error": data.get("error", "Sign up failed")}

    return {"success": True}


# -------------------------------------------------------------------
# UI
# -------------------------------------------------------------------

st.title("National Parks Explorer")
st.write("Log in or sign up to explore parks, save favorites, and log trips.")

# The User must either log in or sign up before they have access to the rest of the app
tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

# ---------------- Login tab ----------------
with tab_login:
    # The user must provide the necessary information to login
    login_email = st.text_input("Email or username", key="login_email")
    login_password = st.text_input(
        "Password", type="password", key="login_password"
    )

    # Once this button is clicked, it will send the info to the API to check
    if st.button("Log in"):
        if not login_email or not login_password:
            st.error("Please enter both email and password.")
        else:
            result = login_via_api(login_email, login_password)
            if result.get("error"):
                st.error(result["error"])
            else:
                # Once logged in, the user is authenicated and user information is attached to the session state
                st.session_state.authenticated = True
                st.session_state.user = result
                st.success("Logged in!")

                # Try to redirect to the Explore page
                try:
                    st.switch_page(EXPLORE_PAGE)
                except Exception:
                    st.info("Open **Explore Parks** from the sidebar.")

# ---------------- Sign-up tab ----------------
with tab_signup:
    # Much like before, it will prompt the user to enter in the necessary information to sign up
    signup_username = st.text_input("Username", key="signup_username")
    signup_email = st.text_input("Email", key="signup_email")
    signup_password = st.text_input(
        "Password", type="password", key="signup_password"
    )

    if st.button("Sign up"):
        if not signup_username or not signup_email or not signup_password:
            st.error("Please fill out all fields.")
        else:
            # Provided info is sent to the API to add the user to the database
            result = signup_via_api(signup_username, signup_email, signup_password)

            # Error handling
            if result.get("error"):
                st.error(result["error"])
            else:
                st.success("Account created! Logging you in…")

                # Auto log in using the same credentials
                login_result = login_via_api(signup_email, signup_password)
                if login_result.get("error"):
                    st.warning(
                        "Account created, but automatic login failed. "
                        "Please try logging in manually."
                    )
                else:
                    # Once user is created and logged in, the session is now authenicated and the user info attached
                    st.session_state.authenticated = True
                    st.session_state.user = login_result
                    st.success("Logged in!")

                    # Tries to redirect to the park explorer page
                    try:
                        st.switch_page(EXPLORE_PAGE)
                    except Exception:
                        st.info("Open **Explore Parks** from the sidebar.")
