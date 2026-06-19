import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Request
from fastapi.responses import RedirectResponse

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-use-secrets-token-hex")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
TOKEN_EXPIRE_HOURS = 24
COOKIE_NAME = "campaignos_session"


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> Optional[str]:
    """
    Verify a JWT token and extract the authenticated username.
    
    Returns:
    	str or None: The authenticated username if the token is valid, `None` if the token is expired or invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


async def check_credentials(username: str, password: str) -> bool:
    """
    Validate admin user credentials.
    
    Verifies that the username matches the admin username and the password
    is correct (either against a stored hash or against a fallback plaintext value).
    
    Returns:
    	bool: True if credentials are valid, False otherwise.
    """
    if username != ADMIN_USERNAME:
        return False
    from database import get_setting
    hashed = await get_setting("password_hash")
    if hashed:
        return verify_password(password, hashed)
    return password == ADMIN_PASSWORD


class NotAuthenticatedException(Exception):
    pass


def require_auth(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise NotAuthenticatedException()
    username = verify_token(token)
    if not username:
        raise NotAuthenticatedException()
    return username