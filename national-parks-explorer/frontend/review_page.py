import streamlit as st
import requests
from backend.db import get_connection

st.title("Review Page")

tab_park, tab_trail = st.tabs(["Park Reviews", "Trail Reviews"])

# ------------------ Park Reviews ------------------
with tab_park:
    st.header("Review a Park")

    # Select park
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT park_id, name FROM PARK ORDER BY name")
    parks = cur.fetchall()
    conn.close()

    park_options = {name: park_id for park_id, name in parks}
    selected_park_name = st.selectbox("Select a Park", list(park_options.keys()))
    selected_park_id = park_options[selected_park_name]

    rating = st.slider("Rating", 1, 5, 3, key="park_rating")
    review_text = st.text_area("Review Text", key="park_review")

    if st.button("Submit Park Review"):
        session_id = st.session_state.get("session_id")  # must be set at login
        if not session_id:
            st.error("You must be logged in to submit a review.")
        else:
            response = requests.post(
                f"http://localhost:8000/api/parks/{selected_park_id}/reviews",
                json={"rating": rating, "review_text": review_text},
                cookies={"session_id": session_id},
            )
            if response.status_code == 201:
                st.success("Park review submitted!")
            else:
                st.error(f"Error: {response.json().get('error')}")

# ------------------ Trail Reviews ------------------
with tab_trail:
    st.header("Review a Trail")

    # Select trail
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT trail_id, name FROM TRAIL ORDER BY name")
    trails = cur.fetchall()
    conn.close()

    trail_options = {name: trail_id for trail_id, name in trails}
    selected_trail_name = st.selectbox("Select a Trail", list(trail_options.keys()))
    selected_trail_id = trail_options[selected_trail_name]

    rating = st.slider("Rating", 1, 5, 3, key="trail_rating")
    review_text = st.text_area("Review Text", key="trail_review")

    if st.button("Submit Trail Review"):
        session_id = st.session_state.get("session_id")
        if not session_id:
            st.error("You must be logged in to submit a review.")
        else:
            response = requests.post(
                f"http://localhost:8000/api/trails/{selected_trail_id}/reviews",
                json={"rating": rating, "review_text": review_text},
                cookies={"session_id": session_id},
            )
            if response.status_code == 201:
                st.success("Trail review submitted!")
            else:
                st.error(f"Error: {response.json().get('error')}")
