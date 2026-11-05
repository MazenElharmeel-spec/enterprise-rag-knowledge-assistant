from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from backend.app.core.config import get_settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerificationError:
        return False


def create_token(user_id: UUID, organization_id: UUID, token_type: str, expires: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def decode_token(token: str, expected_type: str = "access") -> tuple[UUID, UUID]:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return UUID(payload["sub"]), UUID(payload["org"])
