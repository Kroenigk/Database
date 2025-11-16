import streamlit as st
from mysql.connector import pooling
import os
from dotenv import load_dotenv

load_dotenv()

def get_pool():
    if "search_pool" not in st.session_state:
        st.session_state.search_pool = pooling.MySQLConnectionPool(
            pool_name="search_pool",
            pool_size=3,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "parksdb"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "")
        )
    return st.session_state.search_pool

def search_parks(term: str):
    sql = """
    SELECT park_code, name, designation, description
    FROM park
    WHERE name LIKE %s OR description LIKE %s
    ORDER BY name
    LIMIT 50
    """
    conn = get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    like = f"%{term}%"
    cur.execute(sql, [like, like])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

st.title("Search Parks")
query = st.text_input("Search term", value="")
if query:
    results = search_parks(query)
    st.write(f"Found: {len(results)}")
    for row in results:
        with st.expander(row["name"]):
            st.write("Designation:", row.get("designation") or "N/A")
            st.write(row["description"][:300] + ("..." if len(row["description"]) > 300 else ""))
# TODO: Add fuzzy search, highlight matches.
