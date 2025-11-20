import requests
from datetime import date, timedelta

from backend.db import get_connection
from backend.config import ( NOAA_API_TOKEN, NOAA_BASE_URL, USGS_BASE_URL)

NOAA_HEADERS = {"token": NOAA_API_TOKEN}

# ---------------------------------------------------------
# NOAA: stations + daily weather
# ---------------------------------------------------------

def get_nearest_station(lat, lon):
    """Return nearest GHCND station id for a park, or None if NOAA is unhappy."""
    params = {
        "datasetid": "GHCND",
        "limit": 1,
        "sortfield": "distance",
        "sortorder": "asc",
        "latitude": lat,
        "longitude": lon,
    }

    try:
        resp = requests.get(
            f"{NOAA_BASE_URL}/stations",
            headers=NOAA_HEADERS,
            params=params,
            timeout=10,
        )
    except Exception as e:
        print(f"[NOAA] stations request failed (network): {e}")
        return None

    if resp.status_code == 429:
        print("[NOAA] stations rate limit (429) – skipping this park.")
        return None
    if resp.status_code >= 400:
        print("[NOAA] stations error:", resp.status_code, resp.text[:200])
        return None

    data = resp.json()
    results = data.get("results", [])
    if not results:
        print(f"[NOAA] no stations found near {lat}, {lon}")
        return None

    return results[0]["id"]  # e.g. "GHCND:USW00013874"


def fetch_daily_weather(station_id, start_date, end_date):
    """Return list of daily weather records or [] if NOAA fails."""
    params = {
        "datasetid": "GHCND",
        "stationid": station_id,
        "startdate": start_date,
        "enddate": end_date,
        "limit": 1000,
        "units": "metric",
    }

    try:
        resp = requests.get(
            f"{NOAA_BASE_URL}/data",
            headers=NOAA_HEADERS,
            params=params,
            timeout=10,
        )
    except Exception as e:
        print(f"[NOAA] data request failed (network): {e}")
        return []

    if resp.status_code == 429:
        print("[NOAA] data rate limit (429) – skipping this station.")
        return []
    if resp.status_code >= 400:
        print("[NOAA] data error:", resp.status_code, resp.text[:200])
        return []

    return resp.json().get("results", [])


def update_weather_for_parks(days_back: int = 7, max_parks: int = 5):
    """
    Insert basic WEATHER data for a small number of parks.
    Keeps it simple and resilient: skips parks when NOAA is grumpy.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Limit to a few parks so we don't hammer NOAA
    cur.execute("SELECT park_id, latitude, longitude FROM PARK LIMIT %s", (max_parks,))
    parks = cur.fetchall()

    weather_sql = """
      INSERT INTO WEATHER (park_id, record_date, temp_high, temp_low, precip_mm)
      VALUES (%s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        temp_high = VALUES(temp_high),
        temp_low  = VALUES(temp_low),
        precip_mm = VALUES(precip_mm)
    """

    today = date.today()
    start = today - timedelta(days=days_back)

    for park_id, lat, lon in parks:
        if lat is None or lon is None:
            print(f"[NOAA] park {park_id} has no coordinates, skipping.")
            continue

        print(f"[NOAA] Processing park {park_id} ({lat}, {lon})...")
        station_id = get_nearest_station(lat, lon)
        if not station_id:
            print(f"[NOAA] No station for park {park_id}, skipping.")
            continue

        records = fetch_daily_weather(
            station_id,
            start.isoformat(),
            today.isoformat(),
        )
        if not records:
            print(f"[NOAA] No weather records for park {park_id}, skipping.")
            continue

        daily = {}
        for rec in records:
            dt = rec.get("date", "")[:10]
            dtype = rec.get("datatype")
            val = rec.get("value")
            if not dt or dtype not in ("TMAX", "TMIN", "PRCP"):
                continue

            if dt not in daily:
                daily[dt] = {"TMAX": None, "TMIN": None, "PRCP": None}
            daily[dt][dtype] = val

        for dt, vals in daily.items():
            cur.execute(
                weather_sql,
                (park_id, dt, vals["TMAX"], vals["TMIN"], vals["PRCP"]),
            )

    conn.commit()
    conn.close()
    print("[NOAA] WEATHER ingest complete.")


# ---------------------------------------------------------
# USGS: earthquakes + safety scoring (kept simple)
# ---------------------------------------------------------

def fetch_earthquakes_near(lat, lon, radius_km=200, days_back: int = 30):
    """Use USGS to get earthquakes near a park. Returns [] on error."""
    end = date.today()
    start = end - timedelta(days=days_back)
    params = {
        "format": "geojson",
        "latitude": lat,
        "longitude": lon,
        "maxradiuskm": radius_km,
        "starttime": start.isoformat(),
        "endtime": end.isoformat(),
    }

    try:
        resp = requests.get(USGS_BASE_URL, params=params, timeout=10)
    except Exception as e:
        print(f"[USGS] request failed (network): {e}")
        return []

    if resp.status_code >= 400:
        print("[USGS] error:", resp.status_code, resp.text[:200])
        return []

    return resp.json().get("features", [])


def compute_earthquake_risk(quakes):
    """Very simple risk metric based on count & max magnitude."""
    if not quakes:
        return 0

    mags = [
        (q.get("properties", {}).get("mag") or 0)
        for q in quakes
    ]
    max_mag = max(mags) if mags else 0
    count = len(mags)

    if max_mag >= 6 or count > 20:
        return 5
    if max_mag >= 5:
        return 4
    if max_mag >= 4:
        return 3
    if count > 0:
        return 2
    return 1


def compute_weather_risk_for_park(cur, park_id):
    """Naive weather risk based on recent WEATHER data (precip + temp range)."""
    cur.execute(
        """
        SELECT AVG(precip_mm), MAX(temp_high) - MIN(temp_low)
        FROM WEATHER
        WHERE park_id = %s
          AND record_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """,
        (park_id,),
    )
    row = cur.fetchone()
    if not row:
        return 0

    avg_precip, temp_range = row
    avg_precip = avg_precip or 0
    temp_range = temp_range or 0

    score = 0
    if avg_precip > 10:
        score += 2
    if temp_range > 25:
        score += 2
    return min(score, 5)


def update_safety_scores(max_parks: int = 20):
    """
    Populate SAFETY using both USGS (earthquakes) and WEATHER (recent).
    Kept simple and resilient: skips parks on error.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT park_id, latitude, longitude FROM PARK LIMIT %s", (max_parks,))
    parks = cur.fetchall()

    safety_sql = """
      INSERT INTO SAFETY (park_id, safety_score, earthquake_risk_level, weather_risk_level, last_updated)
      VALUES (%s, %s, %s, %s, NOW())
      ON DUPLICATE KEY UPDATE
        safety_score          = VALUES(safety_score),
        earthquake_risk_level = VALUES(earthquake_risk_level),
        weather_risk_level    = VALUES(weather_risk_level),
        last_updated          = VALUES(last_updated)
    """

    for park_id, lat, lon in parks:
        if lat is None or lon is None:
            continue

        quakes = fetch_earthquakes_near(lat, lon)
        eq_risk = compute_earthquake_risk(quakes)
        weather_risk = compute_weather_risk_for_park(cur, park_id)

        # simple combined score: 5 minus weighted risks
        safety_score = max(0, 5 - (eq_risk * 0.6 + weather_risk * 0.4))

        cur.execute(
            safety_sql,
            (park_id, safety_score, eq_risk, weather_risk),
        )

    conn.commit()
    conn.close()
    print("[SAFETY] safety scores updated.")


# ---------------------------------------------------------
# Public entrypoint for ingest_all.py
# ---------------------------------------------------------

def ingest_weather_and_safety():
    """
    Entry point called from ingest_all.py.
    Kept simple for now; you can expand later.
    """
    print("Updating WEATHER from NOAA...")
    update_weather_for_parks()

    print("Updating SAFETY from NOAA + USGS...")
    update_safety_scores()
