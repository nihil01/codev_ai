import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import TypedDict, cast

import jwt


class JwtClaims(TypedDict):
    user_id: str
    email: str
    role: str
    company_id: str | None
    iat: datetime
    exp: datetime


# Simple password hashing (in production, use bcrypt or argon2)
def hash_password(password: str) -> str:
    """Hash password using PBKDF2."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000,
    )
    return f"{salt}${password_hash.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        salt, stored_hash = password_hash.split('$')
        password_verification = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000,
        )
        return password_verification.hex() == stored_hash
    except (ValueError, AttributeError):
        return False


def create_jwt_token(
    user_id: str,
    email: str,
    role: str,
    secret: str,
    company_id: str | None = None,
    expires_in_hours: int = 24,
) -> str:
    """Create JWT token."""
    now = datetime.now(timezone.utc)
    payload: JwtClaims = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "company_id": company_id,
        "iat": now,
        "exp": now + timedelta(hours=expires_in_hours),
    }
    return jwt.encode(dict(payload), secret, algorithm="HS256")


def decode_jwt_token(token: str, secret: str) -> JwtClaims | None:
    """Decode and verify JWT token."""
    try:
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        if not isinstance(decoded, dict):
            return None
        return cast(JwtClaims, decoded)
    except (jwt.InvalidTokenError, jwt.DecodeError, jwt.ExpiredSignatureError):
        return None
