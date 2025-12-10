from .nps_ingest import ingest_nps_all
from .ri_ingest import ingest_ridb_all
from .usgs_noaa_ingest import ingest_weather_and_safety
from .data_ingest import ingest_tags
from .data_ingest import ingest_dummy_popularity

# ---------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------
def main():
    print("Ingesting NPS data...")
    ingest_nps_all()

    print("Ingesting Recreation.gov data...")
    ingest_ridb_all()

    print("Ingesting NOAA + USGS data...")
    ingest_weather_and_safety()

    print("Ingesting tags...")
    ingest_tags()

    print("Ingesting dummy popularity data...")
    ingest_dummy_popularity()

    print("All ingestion complete.")

if __name__ == "__main__":
    main()
