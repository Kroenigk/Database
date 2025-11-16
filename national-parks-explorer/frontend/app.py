"""
Streamlit main application entry point.
Run: streamlit run frontend/app.py
"""
import streamlit as st
import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import pooling

load_dotenv()

st.set_page_config(page_title="National Parks Explorer", layout="wide")

def get_pool():
    if "db_pool" not in st.session_state:
        st.session_state.db_pool = pooling.MySQLConnectionPool(
            pool_name="frontend_pool",
            pool_size=3,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "parksdb"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "")
        )
    return st.session_state.db_pool

def get_connection():
    return get_pool().get_connection()

def load_states():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT code FROM state ORDER BY code")
    data = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return data

def fetch_parks_by_state(state_code: str):
    sql = """
    SELECT p.park_code, p.name, p.description, p.designation
    FROM park p
    JOIN park_state ps ON ps.park_id = p.id
    JOIN state s ON s.id = ps.state_id
    WHERE s.code=%s
    ORDER BY p.name
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, [state_code])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def fetch_park_details(park_code: str):
    sql = """
    SELECT p.*, GROUP_CONCAT(DISTINCT a.name ORDER BY a.name SEPARATOR ', ') AS activities
    FROM park p
    LEFT JOIN park_activity pa ON pa.park_id = p.id
    LEFT JOIN activity a ON a.id = pa.activity_id
    WHERE p.park_code=%s
    GROUP BY p.id
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, [park_code])
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

st.title("National Parks Explorer")
st.write("Explore U.S. National Parks data ingested from the NPS API.")

states = load_states()
chosen_state = st.selectbox("Filter by State", options=states)

if chosen_state:
    parks = fetch_parks_by_state(chosen_state)
    st.subheader(f"Parks in {chosen_state}")
    for park in parks:
        with st.expander(park["name"]):
            st.write(f"Designation: {park.get('designation') or 'N/A'}")
            st.write(park["description"][:300] + ("..." if len(park["description"]) > 300 else ""))
            detail_btn = st.button("View Details", key=f"detail_{park['park_code']}")
            if detail_btn:
                detail = fetch_park_details(park["park_code"])
                st.write("Activities:", detail.get("activities") or "None")
                st.write("Full Description:")
                st.write(detail.get("description"))

st.sidebar.success("Use page menu for additional views.")
st.sidebar.write("Login & filtering available on other pages.")

# TODO: Add global search, favorites integration, caching.
