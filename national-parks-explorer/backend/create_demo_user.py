"""
Helper script to quickly create a user in APP_USER.

Usage:

    # Create default demo user
    python -m backend.create_demo_user

    # Create a custom user
    python -m backend.create_demo_user <username> <email> <password>
"""

import sys
from passlib.hash import pbkdf2_sha256
from backend.db import get_connection


def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-SHA256.
    No 72-byte limit like bcrypt; passlib handles salt & iterations.
    """
    return pbkdf2_sha256.hash(password)


def create_user(username: str, email: str, password: str) -> int:
    """
    Creates a new user if username/email does not exist.
    Returns user_id (existing or newly created).
    """
    conn = get_connection()
    cur = conn.cursor()

    username = username.strip()
    email = email.strip()

    if not username or not email or not password:
        conn.close()
        raise ValueError("Username, email, and password must all be non-empty.")

    # Check if user already exists
    cur.execute(
        """
        SELECT user_id
        FROM APP_USER
        WHERE username = %s OR email = %s
        """,
        (username, email),
    )
    row = cur.fetchone()
    if row:
        user_id = row[0]
        print(f"[INFO] User already exists: user_id={user_id}, username={username!r}, email={email!r}")
        conn.close()
        return user_id

    # Hash password
    password_hash = hash_password(password)

    # Insert user
    cur.execute(
        """
        INSERT INTO APP_USER (username, email, password_hash, role)
        VALUES (%s, %s, %s, 'user')
        """,
        (username, email, password_hash),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    print(f"[SUCCESS] Created user: user_id={user_id}, username={username!r}, email={email!r}")
    return user_id


def main():
    if len(sys.argv) == 4:
        username = sys.argv[1]
        email = sys.argv[2]
        password = sys.argv[3]
        print("[INFO] Creating custom user from CLI arguments…")
    else:
        print("[INFO] No arguments provided, creating default demo user…")
        username = "demo"
        email = "demo@example.com"
        password = "ChangeMe123!"

    try:
        create_user(username, email, password)
    except Exception as e:
        print(f"[ERROR] Failed to create user: {e}")


if __name__ == "__main__":
    main()
