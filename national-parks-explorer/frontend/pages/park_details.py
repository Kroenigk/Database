import streamlit as st
import os
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

def get_pool():
    if "detail_pool" not in st.session_state:
        st.session_state.detail_pool = pooling.MySQLConnectionPool(
            pool_name="detail_pool",
            pool_size=3,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "parksdb"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "")
        )
    return st.session_state.detail_pool

def list_parks():
    sql = "SELECT park_code, name FROM park ORDER BY name"
    conn = get_pool().get_connection()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_details(code: str):
    sql = """
    SELECT p.*, GROUP_CONCAT(DISTINCT a.name ORDER BY a.name SEPARATOR ', ') AS activities
    FROM park p
    LEFT JOIN park_activity pa ON pa.park_id = p.id
    LEFT JOIN activity a ON a.id = pa.activity_id
    WHERE park_code=%s
    GROUP BY p.id
    """
    conn = get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, [code])
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

st.title("Park Details")
parks = list_parks()
choices = {name: code for code, name in parks}
selected = st.selectbox("Select Park", options=list(choices.keys()))
if selected:
    code = choices[selected]
    detail = get_details(code)
    if detail:
        st.subheader(detail["name"])
        st.write("Designation:", detail.get("designation") or "N/A")
        st.write("Activities:", detail.get("activities") or "None")
        st.write(detail.get("description"))
# TODO: Show campgrounds, amenities, map display.
