from flask import Flask, request, jsonify, make_response, g
from flask_cors import CORS
from passlib.hash import pbkdf2_sha256
from datetime import datetime
from functools import wraps

from backend.db import get_connection
from backend.config import FLASK_SECRET_KEY


app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY

# Allow your frontend to talk to this API
CORS(app, supports_credentials=True)


# --------- Helpers ---------

# Password hashing and verification
def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256."""
    return pbkdf2_sha256.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password using PBKDF2-SHA256."""
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
    """
    Look up current user from USER_SESSION based on session_id cookie.
    Attach user info to g.user.
    """
    if hasattr(g, "user"):
        return g.user

    g.user = None
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    db = get_db()
    cur = db.cursor()
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
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user_from_cookie()
        if not user:
            return jsonify({"error": "Not authenticated"}), 401
        return fn(*args, **kwargs)
    return wrapper


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

    # Check uniqueness
    cur.execute(
        "SELECT user_id FROM APP_USER WHERE username = %s OR email = %s",
        (username, email),
    )
    if cur.fetchone():
        return jsonify({"error": "Username or email already in use"}), 400

    password_hash = hash_password(password)

    cur.execute(
        """
        INSERT INTO APP_USER (username, email, password_hash, role)
        VALUES (%s, %s, %s, 'user')
        """,
        (username, email, password_hash),
    )
    db.commit()

    return jsonify({"message": "User created"}), 201


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
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401

    user_id, password_hash, role = row

    if not verify_password(password, password_hash):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create session
    cur.execute(
        "INSERT INTO USER_SESSION (user_id, login_time) VALUES (%s, NOW())",
        (user_id,),
    )
    session_id = cur.lastrowid
    db.commit()

    resp = make_response(
        jsonify({"message": "Logged in", "user_id": user_id, "role": role})
    )
    # Session cookie
    resp.set_cookie(
        "session_id",
        str(session_id),
        httponly=True,
        secure=False,  # set True in production with HTTPS
        samesite="Lax",
    )
    return resp


@app.post("/api/auth/logout")
def logout():
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


@app.get("/api/auth/me")
def get_me():
    user = get_current_user_from_cookie()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user})


# --------- Example user features ---------

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
