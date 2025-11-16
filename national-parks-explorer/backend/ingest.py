"""
Ingestion script for National Parks Explorer.

Fetches parks and activities from the NPS API, derives states list, and inserts into MySQL.
Run:
    python backend/ingest.py --limit 50
"""
import os
import argparse
import requests
from dotenv import load_dotenv
from typing import Dict, List, Set
from .db import execute, fetch_one, executemany

load_dotenv()

BASE_URL = "https://developer.nps.gov/api/v1"

def get_api_key() -> str:
    key = os.getenv("NPS_API_KEY")
    if not key:
        raise ValueError("NPS_API_KEY not set in environment.")
    return key

def fetch_parks(limit: int | None = None) -> List[Dict]:
    """
    Fetch parks from NPS API. Pagination logic simplified by optional limit.
    """
    api_key = get_api_key()
    params = {"api_key": api_key, "limit": 500}
    url = f"{BASE_URL}/parks"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    parks = data.get("data", [])
    if limit:
        parks = parks[:limit]
    return parks

def fetch_activities() -> List[Dict]:
    api_key = get_api_key()
    url = f"{BASE_URL}/activities"
    resp = requests.get(url, params={"api_key": api_key}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])

def ensure_state(code: str, name: str = ""):
    """
    Insert state if not present.
    """
    code = code.strip().upper()
    if not code:
        return
    row = fetch_one("SELECT id FROM state WHERE code=%s", [code])
    if row:
        return
    execute("INSERT INTO state(code, name) VALUES (%s, %s)", [code, name or code])

def ensure_activity(activity: Dict):
    """
    Insert activity if not present.
    """
    name = activity.get("name", "").strip()
    act_id = activity.get("id")
    if not name:
        return
    row = fetch_one("SELECT id FROM activity WHERE name=%s", [name])
    if row:
        return
    execute("INSERT INTO activity(activity_code, name) VALUES (%s, %s)", [act_id, name])

def insert_park(park: Dict):
    """
    Insert park if not present; update minimal fields if exists.
    """
    code = park.get("parkCode")
    name = park.get("fullName")
    desc = park.get("description")
    designation = park.get("designation")
    url = park.get("url")
    lat = park.get("latitude")
    lon = park.get("longitude")
    phone = (park.get("contacts", {}).get("phoneNumbers", [{}])[0].get("phoneNumber")
             if park.get("contacts") else None)
    email = (park.get("contacts", {}).get("emailAddresses", [{}])[0].get("emailAddress")
             if park.get("contacts") else None)
    states_raw = park.get("states", "")

    existing = fetch_one("SELECT id FROM park WHERE park_code=%s", [code])
    if existing:
        execute("""
            UPDATE park SET name=%s, designation=%s, description=%s, url=%s, latitude=%s,
                   longitude=%s, phone=%s, email=%s, states_raw=%s
            WHERE park_code=%s
        """, [name, designation, desc, url, lat, lon, phone, email, states_raw, code])
        return existing["id"]

    execute("""
        INSERT INTO park(park_code, name, designation, description, url, latitude, longitude, phone, email, states_raw)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, [code, name, designation, desc, url, lat, lon, phone, email, states_raw])
    row = fetch_one("SELECT id FROM park WHERE park_code=%s", [code])
    return row["id"]

def link_park_states(park_id: int, states: List[str]):
    pairs = []
    for code in states:
        st_row = fetch_one("SELECT id FROM state WHERE code=%s", [code])
        if st_row:
            pairs.append((park_id, st_row["id"]))
    if pairs:
        executemany("""
            INSERT IGNORE INTO park_state(park_id, state_id) VALUES (%s,%s)
        """, pairs)

def link_park_activities(park_id: int, activities: List[Dict]):
    pairs = []
    for act in activities:
        name = act.get("name", "").strip()
        act_row = fetch_one("SELECT id FROM activity WHERE name=%s", [name])
        if act_row:
            pairs.append((park_id, act_row["id"]))
    if pairs:
        executemany("""
            INSERT IGNORE INTO park_activity(park_id, activity_id) VALUES (%s,%s)
        """, pairs)

def ingest(limit: int | None = None):
    print("Fetching activities...")
    activities = fetch_activities()
    for act in activities:
        ensure_activity(act)
    print(f"Activities processed: {len(activities)}")

    print("Fetching parks...")
    parks = fetch_parks(limit=limit)
    print(f"Parks fetched: {len(parks)}")

    all_state_codes: Set[str] = set()
    for park in parks:
        states_field = park.get("states", "")
        for s in states_field.split(","):
            if s.strip():
                all_state_codes.add(s.strip().upper())

    for code in sorted(all_state_codes):
        ensure_state(code)

    for park in parks:
        pid = insert_park(park)
        state_codes = [s.strip().upper() for s in park.get("states", "").split(",") if s.strip()]
        link_park_states(pid, state_codes)
        link_park_activities(pid, park.get("activities", []))
    print("Ingestion complete.")

def example_manual_insert():
    """
    Example manual insert statement (for documentation/testing).
    """
    execute("INSERT INTO state(code, name) VALUES (%s,%s)", ["XX", "Example State"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of parks ingested.")
    args = parser.parse_args()
    ingest(limit=args.limit)

if __name__ == "__main__":
    main()
