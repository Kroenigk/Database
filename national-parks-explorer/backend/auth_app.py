from flask import Flask, request, jsonify, make_response, g
from flask_cors import CORS
from passlib.hash import pbkdf2_sha256
from datetime import datetime
from functools import wraps

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

# This will add a review to a specific park
@app.post("/api/parks/<park_id>/reviews")
@login_required
def create_park_review(park_id):
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
        INSERT INTO PARK_REVIEW (user_id, park_id, rating, review_text, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        """,
        (user["user_id"], park_id, int(rating), review_text),
    )
    db.commit()

    log_activity(user["session_id"], user["user_id"], f"CREATE_PARK_REVIEW park_id={park_id}")

    return jsonify({"message": "Review created"}), 201

# This will return all of the reviews attached to a specific park id
@app.get("/api/parks/<park_id>/reviews")
def list_park_reviews(park_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        SELECT r.review_id, r.rating, r.review_text, r.created_at, u.username
        FROM PARK_REVIEW r
        JOIN APP_USER u ON u.user_id = r.user_id
        WHERE r.park_id = %s
        ORDER BY r.created_at DESC
        """,
        (park_id,),
    )
    rows = cur.fetchall()

    reviews = []
    for review_id, rating, text, created_at, username in rows:
        reviews.append(
            {
                "review_id": review_id,
                "rating": rating,
                "review_text": text,
                "created_at": created_at.isoformat() if created_at else None,
                "username": username,
            }
        )
    return jsonify({"reviews": reviews})


if __name__ == "__main__":
    # For local dev
    app.run(debug=True, port=8000)
