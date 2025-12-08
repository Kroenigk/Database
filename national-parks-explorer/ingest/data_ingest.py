from typing import Dict, List
import random
from backend.db import get_connection


PARK_TAGS: Dict[str, List[str]] = {
    "acad": ["coastal", "mountains", "islands", "hiking", "wildlife", "lighthouses"],
    "npsa": ["tropical", "rainforest", "islands", "coral_reef", "beaches", "backcountry"],
    "arch": ["desert", "rock_formations", "arches", "scenic_drives", "photography"],
    "badl": ["prairie", "fossils", "badlands", "scenic_drives", "wildlife"],
    "bibe": ["desert", "mountains", "rio_grande", "backpacking", "dark_sky"],
    "bisc": ["coral_reef", "snorkeling", "boating", "diving", "tropical"],
    "blca": ["canyons", "cliffs", "rivers", "dark_sky", "scenic_drives"],
    "brca": ["hoodoos", "desert", "stargazing", "scenic_drives", "hiking"],
    "cany": ["canyons", "desert", "backpacking", "rivers", "scenic_overlooks"],
    "care": ["wetlands", "nature", "wildlife", "forests", "birdwatching"],
    "cave": ["caves", "limestone", "underground", "geology", "touring"],
    "chis": ["islands", "coastal", "marine_life", "kayaking", "snorkeling"],
    "cong": ["swamp", "forest", "kayaking", "biodiversity", "boardwalk"],
    "crla": ["lake", "caldera", "volcanic", "hiking", "scenic_overlooks"],
    "cuva": ["rivers", "waterfalls", "forests", "hiking", "geology"],
    "deva": ["desert", "salt_flats", "sand_dunes", "heat", "dark_sky"],
    "dena": ["mountains", "alaska", "wildlife", "backcountry", "glaciers"],
    "drto": ["coral_reef", "snorkeling", "historic_fort", "islands", "boating"],
    "ever": ["everglades", "wetlands", "wildlife", "alligators", "airboat_tours"],
    "gaar": ["alaska", "wilderness", "mountains", "rivers", "backcountry"],
    "jeff": ["historical", "architecture", "riverfront"],
    "glac": ["glaciers", "mountains", "lakes", "wildlife", "scenic_drives"],
    "glba": ["glaciers", "alaska", "fjords", "boating", "whale_watching"],
    "grca": ["canyon", "desert", "hiking", "scenic_overlooks", "geology"],
    "grte": ["mountains", "lakes", "wildlife", "climbing", "scenic_drives"],
    "grba": ["caves", "mountains", "dark_sky", "bristlecone_pines"],
    "grsa": ["sand_dunes", "desert", "mountains", "stargazing", "hiking"],
    "grsm": ["forests", "mountains", "historic_sites", "waterfalls", "wildlife"],
    "gumo": ["mountains", "desert", "backpacking", "limestone", "wilderness"],
    "hale": ["volcano", "summit", "sunrise", "stargazing", "hiking"],
    "havo": ["volcano", "lava", "rainforest", "geology", "craters"],
    "hosp": ["hot_springs", "historic_sites", "bathhouses", "forests"],
    "indu": ["lakeshore", "dunes", "beaches", "forests", "birdwatching"],
    "isro": ["island", "wolves_and_moose", "wilderness", "boating", "forests"],
    "jotr": ["desert", "rock_climbing", "wildflowers", "stargazing", "boulders"],
    "katm": ["brown_bears", "volcano", "alaska", "rivers", "wilderness"],
    "kefj": ["glaciers", "fjords", "alaska", "mountains", "wildlife"],
    "kova": ["rivers", "mountains", "alaska", "wilderness", "backpacking"],
    "lacl": ["lakes", "rivers", "alaska", "canoeing", "forests"],
    "lavo": ["volcanic", "geothermal", "mountains", "lakes", "meadows"],
    "maca": ["caves", "underground", "limestone", "hiking"],
    "meve": ["cliff_dwellings", "archaeology", "history", "desert"],
    "mora": ["mountains", "glaciers", "wildflowers", "hiking", "forests"],
    "neri": ["rivers", "cliffs", "whitewater", "bridges", "forests"],
    "noca": ["mountains", "glaciers", "rivers", "wilderness", "alpine"],
    "olym": ["rainforest", "coast", "mountains", "wildlife", "tidepools"],
    "pefo": ["petrified_wood", "desert", "badlands", "fossils"],
    "pinn": ["rock_formations", "caves", "condors", "hiking", "climbing"],
    "redw": ["redwoods", "forests", "coast", "wildlife", "hiking"],
    "romo": ["mountains", "tundra", "wildlife", "scenic_drives", "alpine"],
    "sagu": ["cactus", "desert", "wildflowers", "hiking", "scenic_views"],
    "seki": ["giant_sequoias", "mountains", "canyons", "forests"],
    "shen": ["mountains", "forests", "skyline_drive", "wildlife"],
    "thro": ["badlands", "prairie", "wildlife", "scenic_drives"],
    "viis": ["islands", "coral_reef", "tropical", "snorkeling", "beaches"],
    "voya": ["lakes", "canoeing", "forests", "boating", "fishing"],
    "whsa": ["sand_dunes", "desert", "white_sands", "sunset_views"],
    "wica": ["caves", "underground", "forests", "hiking"],
    "wrst": ["glaciers", "alaska", "mountains", "wilderness", "volcano"],
    "yell": ["geothermal", "wildlife", "geysers", "canyons", "waterfalls"],
    "yose": ["mountains", "waterfalls", "climbing", "meadows", "giant_sequoias"],
    "zion": ["canyons", "desert", "hiking", "slot_canyons", "scenic_overlooks"],
}


def ingest_tags():
    # Insert global tags into TAG and connect them to parks via PARK_TAG.
    conn = get_connection()
    cur = conn.cursor()

    # 1. Collect all unique labels from PARK_TAGS.
    all_labels = {label for tags in PARK_TAGS.values() for label in tags}

    # 2. Load any existing tags so we don't duplicate them.
    label_to_id: Dict[str, int] = {}
    cur.execute("SELECT tag_id, label FROM TAG")
    for tag_id, label in cur.fetchall():
        if label in all_labels:
            label_to_id[label] = tag_id

    # Insert any missing labels into TAG.
    for label in sorted(all_labels):
        if label not in label_to_id:
            cur.execute("INSERT INTO TAG (label) VALUES (%s)", (label,))
            label_to_id[label] = cur.lastrowid

    # Map park_code -> park_id from PARK.
    cur.execute("SELECT park_id, park_code FROM PARK")
    code_to_id: Dict[str, str] = {park_code: park_id for park_id, park_code in cur.fetchall()}

    # Link parks and tags in PARK_TAG.
    for park_code, tags in PARK_TAGS.items():
        park_id = code_to_id.get(park_code)
        if not park_id:
            print(f"WARNING: No PARK row found for code '{park_code}', skipping.")
            continue

        for label in tags:
            tag_id = label_to_id[label]
            cur.execute(
                """
                INSERT IGNORE INTO PARK_TAG (park_id, tag_id)
                VALUES (%s, %s)
                """,
                (park_id, tag_id),
            )

    conn.commit()
    print("Tag + park linkage ingestion complete.")

def ingest_dummy_popularity():
    # Fill PARK_POPULARITY with dummy stats for all parks.
    # If a row already exists, it will be updated.
    
    conn = get_connection()
    cur = conn.cursor()

    # Fetch all park_ids so the data aligns with real parks
    cur.execute("SELECT park_id, park_code, name FROM PARK")
    parks = cur.fetchall()

    for park_id, park_code, name in parks:
        favorites = random.randint(10, 500)         # number of times favorited
        visits = random.randint(1000, 50000)        # visitor count
        reviews = random.randint(5, 500)            # number of reviews
        avg_rating = round(random.uniform(2.5, 4.98), 2)

        cur.execute(
            """
            INSERT INTO PARK_POPULARITY (
                park_id,
                favorites_count,
                visit_count,
                review_count,
                avg_rating,
                last_updated
            )
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                favorites_count = VALUES(favorites_count),
                visit_count     = VALUES(visit_count),
                review_count    = VALUES(review_count),
                avg_rating      = VALUES(avg_rating),
                last_updated    = NOW()
            """,
            (park_id, favorites, visits, reviews, avg_rating),
        )

    conn.commit()
    print("Dummy PARK_POPULARITY data loaded.")



def main() -> None:
    ingest_tags()
    ingest_dummy_popularity()


if __name__ == "__main__":
    main()
