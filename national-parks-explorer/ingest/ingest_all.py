from .nps_ingest import ingest_parks
from .ridb_ingest import ingest_facilities, ingest_campgrounds, ingest_amenities
from .usgs_noaa_ingest import ingest_weather_and_safety


def main():
    print("Ingesting NPS data...")
    ingest_parks()

    print("Ingesting Recreation.gov data...")
    ingest_facilities()
    ingest_campgrounds()
    ingest_amenities()

    print("Ingesting NOAA + USGS data...")
    ingest_weather_and_safety()

    print("All ingestion complete.")


if __name__ == "__main__":
    main()
