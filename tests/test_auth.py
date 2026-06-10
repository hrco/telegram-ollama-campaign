import os
os.environ["SECRET_KEY"] = "testsecret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass"

import pytest
from auth import (
    get_password_hash, verify_password,
    create_token, verify_token,
)

def test_password_hash_and_verify():
    hashed = get_password_hash("mypassword")
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrongpass", hashed) is False

def test_create_and_verify_token():
    token = create_token("admin")
    username = verify_token(token)
    assert username == "admin"

def test_verify_invalid_token():
    result = verify_token("not.a.real.token")
    assert result is None

def test_verify_expired_token():
    import jwt
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "admin", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    expired = jwt.encode(payload, "testsecret", algorithm="HS256")
    assert verify_token(expired) is None