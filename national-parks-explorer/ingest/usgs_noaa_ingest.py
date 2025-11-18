import requests
from datetime import date, timedelta

from .db import get_connection
from .config import NOAA_API_TOKEN, NOAA_BASE_URL, USGS_BASE_URL

NOAA_HEADERS = {"token": NOAA_API_TOKEN}


def get_nearest_station(lat, lon):
    """Use NOAA stations endpoint to find nearest GHCND station to a park."""
    params = {
        "datasetid": "GHCND",
        "datatypeid": "TMIN",
        "limit": 1,
        "sortfield": "distance",
        "sortorder": "asc",
        "latitude": lat,
        "longitude": lon,
    }
    r = requests.get(f"{NOAA_BASE_URL}/stations", headers=NOAA_HEADERS, params=params)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None
    return results[0]["id"]


def fetch_daily_weather(station_id, start_date, end_date):
    """Fetch daily TMAX, TMIN, PRCP from GHCND."""
    params = {
        "datasetid": "GHCND",
        "stationid": station_id,
        "startdate": start_date,
        "enddate": end_date,
        "limit": 1000,
        "units": "metric",
    }
    r = requests.get(f"{NOAA_BASE_URL}/data", headers=NOAA_HEADERS, params=params)
    r.raise_for_status()
    return r.json().get("results", [])


def update_weather_for_parks(days_back: int = 30):
    """Populate/refresh WEATHER table for the last N days using NOAA."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT park_id, latitude, longitude FROM PARK")
    parks = cur.fetchall()

    weather_sql = """
      INSERT INTO WEATHER (park_id, record_date, temp_high, temp_low, precip_mm)
      VALUES (%s, %s, %s, %s, %s)
      ON DUPLICATE KEY UPDATE
        temp_high = VALUES(temp_high),
        temp_low = VALUES(temp_low),
        precip_mm = VALUES(precip_mm)
    """

    today = date.today()
    start = today - timedelta(days=days_back)

    for park_id, lat, lon in parks:
        if lat is None or lon is None:
            continue

        station_id = get_nearest_station(lat, lon)
        if not station_id:
            continue

        records = fetch_daily_weather(
            station_id,
            start.isoformat(),
            today.isoformat()
        )

        daily = {}  # date -> {TMAX, TMIN, PRCP}
        for rec in records:
            dt = rec["date"][:10]
            dtype = rec["datatype"]
            val = rec["value"]
            if dt not in daily:
                daily[dt] = {"TMAX": None, "TMIN": None, "PRCP": None}
            daily[dt][dtype] = val

        for dt, vals in daily.items():
            cur.execute(
                weather_sql,
                (
                    park_id,
                    dt,
                    vals["TMAX"],
                    vals["TMIN"],
                    vals["PRCP"],
                )
            )

    conn.commit()
    conn.close()


def fetch_earthquakes_near(lat, lon, radius_km=200, days_back: int = 30):
    """Use USGS to get earthquakes near a park."""
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
    r = requests.get(USGS_BASE_URL, params=params)
    r.raise_for_status()
    return r.json().get("features", [])


def compute_earthquake_risk(quakes):
    """Very simple risk metric based on count & max magnitude."""
    if not quakes:
        return 0

    mags = [
        (q["properties"].get("mag") or 0)
        for q in quakes
        if q.get("properties")
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
    """Optional: derive a weather risk based on recent WEATHER rows."""
    # very naive example: lots of rain or big temp swings -> higher risk
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


def update_safety_scores():
    """Populate SAFETY using both USGS (earthquakes) and WEATHER (recent)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT park_id, latitude, longitude FROM PARK")
    parks = cur.fetchall()

    safety_sql = """
      INSERT INTO SAFETY (park_id, safety_score, earthquake_risk_level, weather_risk_level, last_updated)
      VALUES (%s, %s, %s, %s, NOW())
      ON DUPLICATE KEY UPDATE
        safety_score = VALUES(safety_score),
        earthquake_risk_level = VALUES(earthquake_risk_level),
        weather_risk_level = VALUES(weather_risk_level),
        last_updated = VALUES(last_updated)
    """

    for park_id, lat, lon in parks:
        if lat is None or lon is None:
            continue

        quakes = fetch_earthquakes_near(lat, lon)
        eq_risk = compute_earthquake_risk(quakes)
        weather_risk = compute_weather_risk_for_park(cur, park_id)

        # simple combined score: 5 minus normalized risk
        safety_score = max(0, 5 - (eq_risk * 0.6 + weather_risk * 0.4))

        cur.execute(
            safety_sql,
            (park_id, safety_score, eq_risk, weather_risk),
        )

    conn.commit()
    conn.close()


def ingest_weather_and_safety():
    """Public entrypoint: run both NOAA + USGS parts in order."""
    print("Updating WEATHER from NOAA...")
    update_weather_for_parks()

    print("Updating SAFETY from NOAA + USGS...")
    update_safety_scores()
