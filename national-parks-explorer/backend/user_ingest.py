from .db import get_connection
from passlib.hash import bcrypt

def create_user(username, email, password, role="user"):
    conn = get_connection()
    cur = conn.cursor()

    password_hash = bcrypt.hash(password)

    try:
        cur.execute(
            """
            INSERT INTO APP_USER (username, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            """,
            (username, email, password_hash, role),
        )
        conn.commit()
        print(f"User '{username}' created successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error creating user '{username}': {e}")
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_id, username, email, password_hash, role FROM APP_USER WHERE username = %s",
            (username,)
        )
        user_data = cur.fetchone()
        if user_data:
            return {
                "user_id": user_data[0],
                "username": user_data[1],
                "email": user_data[2],
                "password_hash": user_data[3],
                "role": user_data[4],
            }
        return None
    finally:
        conn.close()

def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT user_id, username, email, password_hash, role FROM APP_USER WHERE email = %s",
            (email,)
        )
        user_data = cur.fetchone()
        if user_data:
            return {
                "user_id": user_data[0],
                "username": user_data[1],
                "email": user_data[2],
                "password_hash": user_data[3],
                "role": user_data[4],
            }
        return None
    finally:
        conn.close()
        return None
