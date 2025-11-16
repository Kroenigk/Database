"""
Authentication and session management utilities.
"""
import os
import secrets
import datetime
from passlib.context import CryptContext
from dotenv import load_dotenv
from .db import fetch_one, execute

load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_DURATION_MINUTES = 60

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_user(username: str, email: str, password: str):
    """
    Create a user if username/email not taken.
    """
    existing = fetch_one("SELECT id FROM app_user WHERE username=%s OR email=%s", [username, email])
    if existing:
        raise ValueError("Username or email already exists.")
    ph = hash_password(password)
    execute("INSERT INTO app_user(username, email, password_hash) VALUES (%s,%s,%s)", [username, email, ph])
    user = fetch_one("SELECT id FROM app_user WHERE username=%s", [username])
    return user["id"]

def start_session(user_id: int, ip: str = None, user_agent: str = None):
    """
    Start a user session and return session token.
    """
    token = secrets.token_hex(32)
    expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=SESSION_DURATION_MINUTES)
    execute("""
        INSERT INTO user_session(user_id, session_token, expires_at, ip_address, user_agent)
        VALUES (%s,%s,%s,%s,%s)
    """, [user_id, token, expires, ip, user_agent])
    execute("UPDATE app_user SET last_login=NOW() WHERE id=%s", [user_id])
    log_action(user_id, "login", "user", user_id, {"ip": ip})
    return token

def end_session(token: str):
    """
    Invalidate a session.
    """
    execute("UPDATE user_session SET is_active=0 WHERE session_token=%s", [token])
    sess = fetch_one("SELECT user_id FROM user_session WHERE session_token=%s", [token])
    if sess:
        log_action(sess["user_id"], "logout", "user", sess["user_id"], {})

def authenticate(username: str, password: str):
    """
    Validate user credentials; return user_id if valid else None.
    """
    user = fetch_one("SELECT id, password_hash FROM app_user WHERE username=%s AND is_active=1", [username])
    if not user:
        return None
    if verify_password(password, user["password_hash"]):
        return user["id"]
    return None

def log_action(user_id: int | None, action: str, entity_type: str, entity_id: int | None, metadata: dict):
    """
    Insert an activity_log row.
    """
    import json
    meta_json = json.dumps(metadata) if metadata else None
    execute("""
        INSERT INTO activity_log(user_id, action, entity_type, entity_id, metadata)
        VALUES (%s,%s,%s,%s,%s)
    """, [user_id, action, entity_type, entity_id, meta_json])

# TODO: Add rate limiting, password reset, email verification.
