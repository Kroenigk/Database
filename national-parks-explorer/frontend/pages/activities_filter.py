import streamlit as st
import os
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

def get_pool():
    if "activity_pool" not in st.session_state:
        st.session_state.activity_pool = pooling.MySQLConnectionPool(
            pool_name="activity_pool",
            pool_size=3,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "parksdb"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "")
        )
    return st.session_state.activity_pool

def load_activities():
    sql = "SELECT id, name FROM activity ORDER BY name"
    conn = get_pool().get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def parks_for_activity(activity_id: int):
    sql = """
    SELECT p.park_code, p.name, p.description
    FROM park p
    JOIN park_activity pa ON pa.park_id = p.id
    WHERE pa.activity_id=%s
    ORDER BY p.name
    """
    conn = get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, [activity_id])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

st.title("Filter by Activity")
activities = load_activities()
if activities:
    mapping = {row[1]: row[0] for row in activities}
    chosen = st.selectbox("Select Activity", options=list(mapping.keys()))
    if chosen:
        parks = parks_for_activity(mapping[chosen])
        st.write(f"Parks offering {chosen}: {len(parks)}")
        for p in parks:
            with st.expander(p["name"]):
                st.write(p["description"][:300] + ("..." if len(p["description"]) > 300 else ""))
# TODO: Multi-activity intersection filter.
