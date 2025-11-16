import streamlit as st
from backend.auth import authenticate, start_session, end_session
from backend.db import fetch_one

st.title("User Login")

token = st.session_state.get("session_token")
user = None
if token:
    user = fetch_one("""
        SELECT u.id, u.username
        FROM user_session s
        JOIN app_user u ON u.id = s.user_id
        WHERE s.session_token=%s AND s.is_active=1
    """, [token])

if user:
    st.success(f"Logged in as {user['username']}")
    if st.button("Logout"):
        end_session(token)
        st.session_state["session_token"] = None
        st.experimental_rerun()
else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user_id = authenticate(username, password)
        if user_id:
            st.session_state["session_token"] = start_session(user_id)
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")
