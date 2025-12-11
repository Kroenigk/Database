from flask import Flask, request, jsonify, make_response, g
from flask_cors import CORS
from passlib.hash import pbkdf2_sha256
from datetime import datetime
from functools import wraps
from datetime import date

from backend.db import get_connection
from backend.config import FLASK_SECRET_KEY

# This is the start of the Flask API
app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY

# Allow your frontend to talk to this API so we can add, read, update, delete, and filter information as needed
CORS(app, supports_credentials=True)


# --------- Helpers ---------

# Password hashing and verification
def hash_password(password: str) -> str:
    # A User's password is stored as a hash for good security
    # Not necessary for this project, but it's good practice
    return pbkdf2_sha256.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    # This will verify that the plain password matches to its respective hash
    # This will be used for verification of passwords
    return pbkdf2_sha256.verify(plain, hashed)

#--------- DB connection per request ---------
def get_db():
    if "db" not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def teardown_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def get_current_user_from_cookie():
   # Look up current user from USER_SESSION based on session_id cookie.
   # Attach user info to g.user.
    if hasattr(g, "user"):
        return g.user

    g.user = None
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    db = get_db()
    cur = db.cursor()
    # Retrieve the user's info from the matching session id by joining the User session and App user tables
    cur.execute(
        """
        SELECT s.session_id, s.user_id, u.username, u.role
        FROM USER_SESSION s
        JOIN APP_USER u ON u.user_id = s.user_id
        WHERE s.session_id = %s AND s.logout_time IS NULL
        """,
        (session_id,),
    )
    row = cur.fetchone()
    # Finds the user that it maps to and attached the info to g.user
    if row:
        sid, user_id, username, role = row
        g.user = {
            "session_id": sid,
            "user_id": user_id,
            "username": username,
            "role": role,
        }
    return g.user


#--------- Auth decorators and logging ---------
# Forces user to be logged in before the user can access whatever the decorator is attached to 
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user_from_cookie()
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper

# This will log all the attivity that a user partakes in to the activitiy log
def log_activity(session_id: int, user_id: int, action: str):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO ACTIVITY_LOG (session_id, user_id, action_time, action)
        VALUES (%s, %s, %s, %s)
        """,
        (session_id, user_id, datetime.utcnow(), action),
    )
    db.commit()


# --------- Auth routes ---------

# This endpoint will be used for a user to sign up from the frontend
# The information will be properly handled by the API and added to the backedn
@app.post("/api/auth/signup")
def signup():
    data = request.get_json(force=True)
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"error": "Missing fields"}), 400

    db = get_db()
    cur = db.cursor()

    # Check uniqueness, no duplicates are allowed
    cur.execute(
        "SELECT user_id FROM APP_USER WHERE username = %s OR email = %s",
        (username, email),
    )

    # Error if a user is found - It would be an issue if their were duplicate users
    if cur.fetchone():
        return jsonify({"error": "Username or email already in use"}), 400

    password_hash = hash_password(password)

    # Information is then passed to the database
    cur.execute(
        """
        INSERT INTO APP_USER (username, email, password_hash, role)
        VALUES (%s, %s, %s, 'user')
        """,
        (username, email, password_hash),
    )
    db.commit()

    return jsonify({"message": "User created"}), 201

# This endpoint will allow for a post request to check if there exists a user that matchs the provide info
@app.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    username_or_email = data.get("username_or_email")
    password = data.get("password")

    if not username_or_email or not password:
        return jsonify({"error": "Missing fields"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT user_id, password_hash, role
        FROM APP_USER
        WHERE username = %s OR email = %s
        """,
        (username_or_email, username_or_email),
    )
    row = cur.fetchone()

    # If no user is found, then it causes an error
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401

    user_id, password_hash, role = row

    if not verify_password(password, password_hash):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create session with given user information
    cur.execute(
        "INSERT INTO USER_SESSION (user_id, login_time) VALUES (%s, NOW())",
        (user_id,),
    )
    session_id = cur.lastrowid
    db.commit()

    resp = make_response(
        jsonify({"message": "Logged in", "user_id": user_id, "role": role})
    )
    # Session cookie - this will be used later
    resp.set_cookie(
        "session_id",
        str(session_id),
        httponly=True,
        secure=False, 
        samesite="Lax",
    )
    return resp

# This will allow a user to log out, ending the user session, thus the session will need an update to reflect the end of the session
@app.post("/api/auth/logout")
def logout():
    # Cookie info used to find the specific session that we must modify
    session_id = request.cookies.get("session_id")
    if session_id:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            UPDATE USER_SESSION
            SET logout_time = NOW()
            WHERE session_id = %s AND logout_time IS NULL
            """,
            (session_id,),
        )
        db.commit()

    resp = make_response(jsonify({"message": "Logged out"}))
    resp.delete_cookie("session_id")
    return resp

# This will return the currect user attacjed to the cookie if they exist
@app.get("/api/auth/me")
def get_me():
    user = get_current_user_from_cookie()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user})


# --------- user features ---------

# ----- Favorite Parks Routes -----

# This will add a park to a users favorites
@app.post("/api/parks/<park_id>/favorite")
@login_required
def favorite_park(park_id):
    user = g.user
    db = get_db()
    cur = db.cursor()

    # Insert favorite
    cur.execute(
        """
        INSERT IGNORE INTO FAVORITE_PARK (user_id, park_id)
        VALUES (%s, %s)
        """,
        (user["user_id"], park_id),
    )
    db.commit()

    log_activity(user["session_id"], user["user_id"], f"FAVORITE_PARK park_id={park_id}")

    return jsonify({"message": "Park favorited"})

# This will remove a park from a user's favorites
@app.delete("/api/parks/<park_id>/favorite")
@login_required
def unfavorite_park(park_id):
    user = g.user
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "DELETE FROM FAVORITE_PARK WHERE user_id = %s AND park_id = %s",
        (user["user_id"], park_id),
    )
    db.commit()

    log_activity(user["session_id"], user["user_id"], f"UNFAVORITE_PARK park_id={park_id}")

    return jsonify({"message": "Park unfavorited"})

# This will return all of the parks that a user has favorited
@app.get("/api/parks/favorites")
@login_required
def list_favorites():
    user = g.user
    db = get_db()
    cur = db.cursor()

    cur.execute(
        """
        SELECT p.park_id, p.name, p.designation
        FROM FAVORITE_PARK f
        JOIN PARK p ON p.park_id = f.park_id
        WHERE f.user_id = %s
        """,
        (user["user_id"],),
    )
    rows = cur.fetchall()

    favorites = [
        {"park_id": park_id, "name": name, "designation": designation}
        for (park_id, name, designation) in rows
    ]
    return jsonify({"favorites": favorites})

# ----- Reviews Routes -----

# This will create a review for a specific park
@app.post("/api/parks/<park_id>/reviews")
@login_required
def create_park_review(park_id):
    user = g.user
    data = request.get_json(force=True) or {}

    rating = data.get("rating")
    review_text = data.get("review_text", "").strip()

    # Validate rating so the only valid values are allowed
    try:
        rating_int = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "Rating must be an integer between 1 and 5"}), 400

    if not (1 <= rating_int <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    if not review_text:
        return jsonify({"error": "Review text cannot be empty."}), 400

    db = get_db()
    cur = db.cursor()

    cur.execute(
        """
        INSERT INTO PARK_REVIEW (user_id, park_id, rating, review_text, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (user["user_id"], park_id, rating_int, review_text),
    )
    db.commit()

    log_activity(
        user["session_id"],
        user["user_id"],
        f"CREATE_PARK_REVIEW park_id={park_id}",
    )

    return jsonify({"message": "Review created"}), 201

# This will return all of the reviews attached to a specific user
@app.get("/api/users/me/reviews")
@login_required
def list_user_reviews():
    user = g.user
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT r.review_id,
               r.rating,
               r.review_text,
               r.created_at,
               r.park_id,
               p.name AS park_name
        FROM PARK_REVIEW r
        JOIN PARK p ON p.park_id = r.park_id
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
        """,
        (user["user_id"],),
    )
    rows = cur.fetchall()

    reviews = []
    for review_id, rating, text, created_at, park_id, park_name in rows:
        reviews.append(
            {
                "review_id": review_id,
                "park_id": park_id,
                "park_name": park_name,
                "rating": rating,
                "review_text": text,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )

    return jsonify({"reviews": reviews})

# ----- Trip Log  Routes ----
@app.get("/api/triplog")
@login_required
def list_triplog():
    # This will get all of the trip log entries attached to a user_id
    user = g.user
    db = get_db()
    cur = db.cursor()
    # Query trip log info joined with park name
    cur.execute(
        """
        SELECT t.trip_id, t.user_id, t.park_id, t.start_date, t.end_date, t.notes, p.name
        FROM TRIP_LOG t
        JOIN PARK p ON p.park_id = t.park_id
        WHERE t.user_id = %s
        ORDER BY t.trip_id DESC
        """,
        (user["user_id"],),
    )

    rows = cur.fetchall()

    triplog = []
    for trip_id, user_id, park_id, start_date, end_date, notes, park_name in rows:
        triplog.append(
            {
                "trip_id": trip_id,
                "user_id": user_id,
                "park_id": park_id,
                "park_name": park_name,
                "start_date": start_date,
                "end_date": end_date,
                "notes": notes,
            }
        )

    return jsonify({"triplog": triplog})


@app.post("/api/triplog")
@login_required
def create_triplog():
    # This will create a new trip log entry
    user = g.user
    data = request.get_json(force=True)
    park_id = data.get("park_id")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    notes = data.get("notes")

    # Ensure required fields are present
    if not park_id or not start_date or not end_date:
        return jsonify({"error": "park_id, start_date, and end_date are required"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO TRIP_LOG (user_id, park_id, start_date, end_date, notes)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user["user_id"], park_id, start_date, end_date, notes),
    )
    db.commit()
    trip_id = cur.lastrowid

    log_activity(
        user["session_id"],
        user["user_id"],
        f"CREATE_TRIPLOG id={trip_id}",
    )

    return jsonify(
        {
            "triplog": {
                "trip_id": trip_id,
                "user_id": user["user_id"],
                "park_id": park_id,
                "start_date": start_date,
                "end_date": end_date,
                "notes": notes,
            }
        }
    ), 201

# This will update a specific trip log entry so that the user can modify their trip log
@app.put("/api/triplog/<int:trip_id>")
@login_required
def update_triplog(trip_id):
    # This will update a specific trip log entry
    user = g.user
    data = request.get_json(force=True)

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    notes = data.get("notes")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        UPDATE TRIP_LOG
        SET start_date = %s, end_date = %s, notes = %s
        WHERE trip_id = %s AND user_id = %s
        """,
        (start_date, end_date, notes, trip_id, user["user_id"]),
    )
    db.commit()

    log_activity(
        user["session_id"],
        user["user_id"],
        f"UPDATE_TRIPLOG trip_id={trip_id}",
    )

    return jsonify(
        {
            "message": "Triplog updated",
            "triplog": {
                "trip_id": trip_id,
                "start_date": start_date,
                "end_date": end_date,
                "notes": notes,
            },
        }
    )

# ----- Wishlist Routes -------
@app.post("/api/wishlist")
@login_required
def create_wishlist_trip():
    # This will get all of the information needed to create a wishlist trip entry
    user = g.user
    data = request.get_json(force=True)
    park_id = data.get("park_id")
    target_season = data.get("target_season")
    notes = data.get("notes")

    # This makes sure that all info is there
    if not park_id or not target_season:
        return jsonify({"error": "park_id and target_season are required"}), 400

    db = get_db()
    cur = db.cursor()
    # This will add the info to the database
    cur.execute(
        """
        INSERT INTO WISHLIST_TRIP (user_id, park_id, target_season, notes)
        VALUES (%s, %s, %s, %s)
        """,
        (user["user_id"], park_id, target_season, notes),
    )
    # This will save the info
    db.commit()
    wishlist_id = cur.lastrowid

    # This statement will log the activity to the activity log
    log_activity(
        user["session_id"],
        user["user_id"],
        f"CREATE_WISHLIST_TRIP id={wishlist_id}",
    )

    return jsonify(
        {
            "wishlist": {
                "wishlist_id": wishlist_id,
                "user_id": user["user_id"],
                "park_id": park_id,
                "target_season": target_season,
                "notes": notes,
            }
        }
    ), 201


@app.get("/api/wishlist")
@login_required
def list_wishlist_trips():
    # This will get all of the wishlist trips attached to a user_id
    user = g.user
    db = get_db()
    cur = db.cursor()
    # This queries the infomation from the database and retrieves all necessary info through joins
    cur.execute(
        """
        SELECT w.wishlist_id, w.user_id, w.park_id, w.target_season, w.notes, p.name
        FROM WISHLIST_TRIP w
        JOIN PARK p ON p.park_id = w.park_id
        WHERE w.user_id = %s
        ORDER BY w.wishlist_id DESC
        """,
        (user["user_id"],),
    )

    rows = cur.fetchall()

    # All of the information that is attached to our query will be place in wishlist to be displayd
    wishlist = []
    for wishlist_id, user_id, park_id, target_season, notes, park_name in rows:
        wishlist.append(
            {
                "wishlist_id": wishlist_id,
                "user_id": user_id,
                "park_id": park_id,
                "park_name": park_name,
                "target_season": target_season,
                "notes": notes,
            }
        )

    return jsonify({"wishlist": wishlist})

# This will update a specific wishlist trip entry so that the user can modify their trip log
@app.put("/api/wishlist/<int:wishlist_id>")
@login_required
def update_wishlist_trip(wishlist_id):
    # This will find a specific wishlist trip entry to be updated with the passed data
    user = g.user
    data = request.get_json(force=True)

    target_season = data.get("target_season")
    notes = data.get("notes")

    if not target_season:
        return jsonify({"error": "target_season is required"}), 400

    db = get_db()
    cur = db.cursor()
    # This statement will update the entry with the new information
    cur.execute(
        """
        UPDATE WISHLIST_TRIP
        SET target_season = %s, notes = %s
        WHERE wishlist_id = %s AND user_id = %s
        """,
        (target_season, notes, wishlist_id, user["user_id"]),
    )
    db.commit()

    # Log activity to activity log
    log_activity(
        user["session_id"],
        user["user_id"],
        f"UPDATE_WISHLIST_TRIP wishlist_id={wishlist_id}",
    )

    return jsonify(
        {
            "message": "Wishlist trip updated",
            "wishlist": {
                "wishlist_id": wishlist_id,
                "target_season": target_season,
                "notes": notes,
            },
        }
    )
# ----- Campgrounds Page --------
# This will list all of the campgrounds in the database
@app.get("/api/campgrounds")
@login_required
def list_all_campgrounds():
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT campground_id, park_id, name, latitude, longitude, description
        FROM CAMPGROUND
        """
    )
    rows = cur.fetchall()

    campgrounds = []
    for campground_id, park_id, name, latitude, longitude, description in rows:
        campgrounds.append(
            {
                "campground_id": campground_id,
                "park_id": park_id,
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "description": description,
            }
        )
    # Added to activity log
    user = g.user
    log_activity(
        user["session_id"],
        user["user_id"],
        f"LIST_ALL_CAMPGROUNDS",
    )

    return jsonify({"campgrounds": campgrounds})

# This gets all of the campgrounds for a specific park
@app.get("/api/parks/<park_id>/campgrounds")
@login_required
def list_campgrounds(park_id):
    user = g.user
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT campground_id, name, latitude, longitude, description
        FROM CAMPGROUND
        WHERE park_id = %s
        """,
        (park_id,),
    )
    rows = cur.fetchall()

    campgrounds = []
    for campground_id, name, latitude, longitude, description in rows:
        campgrounds.append(
            {
                "campground_id": campground_id,
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "description": description,
            }
        )
    # Log activity to activity log
    log_activity(
        user["session_id"],
        user["user_id"],
        f"LIST_CAMPGROUNDS park_id={park_id}",
    )

    return jsonify({"campgrounds": campgrounds})

# This will list all of the campground reservations for a specific user
@app.get("/api/campgrounds/reservations")
@login_required
def list_campground_reservations():
    user = g.user
    user_id = user["user_id"]

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT r.reservation_id,
               r.start_date,
               r.end_date,
               r.status,
               c.name AS campground_name,
               p.name AS park_name
        FROM RESERVATION r
        JOIN CAMPGROUND c ON c.campground_id = r.campground_id
        JOIN PARK p ON p.park_id = c.park_id
        WHERE r.user_id = %s
        ORDER BY r.start_date DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()

    reservations = []
    for (
        reservation_id,
        start_date,
        end_date,
        status,
        campground_name,
        park_name,
    ) in rows:
        reservations.append(
            {
                "reservation_id": reservation_id,
                "campground_name": campground_name,
                "park_name": park_name,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "status": status,
            }
        )

    # Log to activity log
    log_activity(
        user["session_id"],
        user["user_id"],
        f"LIST_CAMP_RESERVATIONS user_id={user_id}",
    )

    return jsonify({"reservations": reservations})

# This will create a new campground reservation for a user
@app.post("/api/campgrounds/reservations")
@login_required
def create_campground_reservation():
    user = g.user
    user_id = user["user_id"]

    data = request.get_json(force=True) or {}
    campground_id = data.get("campground_id")
    start_date_str = data.get("start_date")
    end_date_str = data.get("end_date")
    status = data.get("status", "PENDING")

    # Data validation
    if not campground_id or not start_date_str or not end_date_str:
        return jsonify({"error": "campground_id, start_date, and end_date are required."}), 400

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    if end_date < start_date:
        return jsonify({"error": "end_date must be on or after start_date."}), 400

    db = get_db()
    cur = db.cursor()

    # Insert reservation in the database
    cur.execute(
        """
        INSERT INTO RESERVATION (user_id, campground_id, start_date, end_date, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, campground_id, start_date, end_date, status),
    )
    db.commit()

    # Grab the reservation ID of the newly created reservation so we can log it
    reservation_id = cur.lastrowid

    # Activity log
    log_activity(
        user["session_id"],
        user_id,
        f"CREATE_RESERVATION reservation_id={reservation_id} campground_id={campground_id}",
    )

    return ( jsonify({"message": "Reservation created"}), 201, )

# Delete a campground reservation
@app.delete("/api/campgrounds/reservations/<int:reservation_id>")
@login_required
def delete_campground_reservation(reservation_id):
    user = g.user
    db = get_db()
    cur = db.cursor()
    
    # Verify the reservation belongs to the user
    cur.execute(
        "SELECT user_id FROM RESERVATION WHERE reservation_id = %s",
        (reservation_id,)
    )
    result = cur.fetchone()
    
    if not result or result[0] != user["user_id"]:
        return jsonify({"error": "Reservation not found or unauthorized"}), 404
    
    cur.execute("DELETE FROM RESERVATION WHERE reservation_id = %s", (reservation_id,))
    db.commit()
    
    log_activity(
        user["session_id"],
        user["user_id"],
        f"DELETE_RESERVATION reservation_id={reservation_id}",
    )
    
    return jsonify({"message": "Reservation cancelled"}), 200

# ----- Trails Page --------
# This will list all of the trails for a specific park
@app.get("/api/parks/<park_id>/trails")
@login_required
def list_trails(park_id):
    user = g.user
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT trail_id, name, length_miles, difficulty
        FROM TRAIL
        WHERE park_id = %s
        """,
        (park_id,),
    )
    rows = cur.fetchall()

    # All of the information that is attached to our query will be place in trails to be displayed
    trails = []
    for trail_id, name, length_miles, difficulty in rows:
        trails.append(
            {
                "trail_id": trail_id,
                "name": name,
                "length_miles": length_miles,
                "difficulty": difficulty,
            }
        )
    # Log activity to activity log
    log_activity(
        user["session_id"],
        user["user_id"],
        f"LIST_TRAILS park_id={park_id}",
    )

    # wrapped so frontend uses response.json()["trails"]
    return jsonify({"trails": trails})

# This will create a new review for a specific trail
@app.post("/api/trails/<int:trail_id>/reviews")
@login_required
def add_trail_review(trail_id):
    user = g.user
    data = request.get_json(force=True)

    rating = data.get("rating")
    review_text = data.get("review_text")

    if rating is None or not (1 <= int(rating) <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO TRAIL_REVIEW (trail_id, user_id, rating, review_text, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (trail_id, user["user_id"], int(rating), review_text),
    )
    db.commit()

    log_activity(
        user["session_id"],
        user["user_id"],
        f"CREATE_TRAIL_REVIEW trail_id={trail_id}",
    )

    return ( jsonify({"message": "Trail review created"}), 201, )

# This will return all of the reviews attached to a specific user to be displayed on the frontend
@app.get("/api/trails/reviews")
@login_required
def list_trail_reviews():
    user = g.user
    user_id = user["user_id"]

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT r.review_id,
               r.rating,
               r.review_text,
               r.trail_id,
               r.created_at
        FROM TRAIL_REVIEW r
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()

    # This will place all of the retrieved info into reviews to be displayed
    reviews = []
    for review_id, rating, review_text, trail_id, created_at in rows:
        reviews.append(
            {
                "review_id": review_id,
                "trail_id": trail_id,
                "user_id": user_id,
                "rating": rating,
                "review_text": review_text,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )
    # Log to activity log
    log_activity(
        user["session_id"],
        user["user_id"],
        f"LIST_TRAIL_REVIEWS user_id={user_id}",
    )

    return jsonify({"reviews": reviews})

# ----- Tags endpoint --------
# This will list all of the parks, with optional filtering by tag
@app.get("/api/parks")
@login_required
def list_parks():
    #Returns parks that have the specified tag.
    #If no tag is provided, returns all parks.

    tag_label = request.args.get("tag")

    db = get_db()
    cur = db.cursor()

    # If no tag -> return all parks
    if not tag_label:
        cur.execute(
            """
            SELECT park_id, name
            FROM PARK
            ORDER BY name
            """
        )
        rows = cur.fetchall()

        parks = [{"park_id": r[0], "name": r[1]} for r in rows]
        return jsonify({"parks": parks})

    # If tag provided -> join TAG + PARK_TAG + PARK
    cur.execute(
        """
        SELECT p.park_id, p.name
        FROM PARK p
        JOIN PARK_TAG pt ON p.park_id = pt.park_id
        JOIN TAG t       ON pt.tag_id = t.tag_id
        WHERE t.label = %s
        ORDER BY p.name
        """,
        (tag_label,),
    )
    rows = cur.fetchall()

    # All of the information that is attached to our query will be place in parks to be displayed
    parks = [{"park_id": r[0], "name": r[1]} for r in rows]

    # Activity log
    user = g.user
    log_activity(
        user["session_id"],
        user["user_id"],
        f"VIEW_PARKS_BY_TAG {tag_label}",
    )

    return jsonify({"parks": parks})

# ----- Popularity endpoint --------
# This will list all of the parks ordered by popularity, which is currently filled with dummy data as we do not have enough users to generate real popularity data
@app.get("/api/parks/popular")
@login_required
def list_popular_parks():
    #Return parks ordered by popularity.
    db = get_db()
    cur = db.cursor()

    sql = """
        SELECT
            p.park_id,
            p.name,
            pp.favorites_count,
            pp.visit_count,
            pp.review_count,
            pp.avg_rating
        FROM PARK p
        JOIN PARK_POPULARITY pp ON p.park_id = pp.park_id
        ORDER BY pp.favorites_count DESC, p.name ASC
    """

    cur.execute(sql)
    rows = cur.fetchall()

    # All of the information that is attached to our query will be place in parks to be displayed
    parks = [
        {
            "park_id": row[0],
            "name": row[1],
            "favorites_count": row[2],
            "visit_count": row[3],
            "review_count": row[4],
            "avg_rating": row[5],
        }
        for row in rows
    ]

    # Activity log
    user = g.user
    log_activity(
        user["session_id"],
        user["user_id"],
        "VIEW_POPULAR_PARKS",
    )

    return jsonify({"parks": parks})    

# --------- Trail reviews ---------
# This will create a new review for a specific trail
@app.post("/api/trails/<trail_id>/reviews")
@login_required
def create_trail_review(trail_id):
    user = g.user
    data = request.get_json(force=True)
    rating = data.get("rating")
    review_text = data.get("review_text")

    # Validate review data
    if rating is None or not (1 <= int(rating) <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO TRAIL_REVIEW (user_id, trail_id, rating, review_text, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (user["user_id"], trail_id, int(rating), review_text),
    )
    db.commit()

    log_activity(user["session_id"], user["user_id"], f"CREATE_TRAIL_REVIEW trail_id={trail_id}")
    return jsonify({"message": "Trail review created"}), 201

# This will return all of the park reviews attached to a specific user
@app.get("/api/parks/reviews")
@login_required
def list_park_reviews():
    user = g.user
    user_id = user["user_id"]
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT r.review_id,
               r.rating,
               r.review_text,
               r.park_id,
               r.created_at,
               p.name as park_name
        FROM PARK_REVIEW r
        LEFT JOIN PARK p ON r.park_id = p.park_id
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
        """,
        (user_id,),
    )
    rows = cur.fetchall()
    
    reviews = []
    for review_id, rating, review_text, park_id, created_at, park_name in rows:
        reviews.append(
            {
                "review_id": review_id,
                "park_id": park_id,
                "park_name": park_name,
                "user_id": user_id,
                "rating": rating,
                "review_text": review_text,
                "created_at": created_at.isoformat() if created_at else None,
            }
        )
    
    log_activity(
        user["session_id"],
        user["user_id"],
        f"LIST_PARK_REVIEWS user_id={user_id}",
    )
    
    return jsonify({"reviews": reviews})

@app.delete("/api/parks/reviews/<int:review_id>")
@login_required
def delete_park_review(review_id):
    user = g.user
    db = get_db()
    cur = db.cursor()
    
    # Verify the review belongs to the user
    cur.execute(
        "SELECT user_id FROM PARK_REVIEW WHERE review_id = %s",
        (review_id,)
    )
    result = cur.fetchone()
    
    if not result or result[0] != user["user_id"]:
        return jsonify({"error": "Review not found or unauthorized"}), 404
    
    cur.execute("DELETE FROM PARK_REVIEW WHERE review_id = %s", (review_id,))
    db.commit()
    
    log_activity(
        user["session_id"],
        user["user_id"],
        f"DELETE_PARK_REVIEW review_id={review_id}",
    )
    
    return jsonify({"message": "Park review deleted"}), 200

if __name__ == "__main__":
    # For local dev
    app.run(debug=True, port=8000)
