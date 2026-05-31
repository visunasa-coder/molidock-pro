from datetime import datetime, timedelta, timezone
import hashlib

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings


ALGORITHM = "HS256"
PASSWORD_SCHEME_PREFIX = "bcrypt_sha256$"


def _password_secret(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("ascii")


def hash_password(password: str) -> str:
    password_hash = bcrypt.hashpw(_password_secret(password), bcrypt.gensalt(rounds=12)).decode("ascii")
    return PASSWORD_SCHEME_PREFIX + password_hash


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith(PASSWORD_SCHEME_PREFIX):
        stored_hash = password_hash.removeprefix(PASSWORD_SCHEME_PREFIX).encode("ascii")
        return bcrypt.checkpw(_password_secret(password), stored_hash)
    return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("ascii"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
    subject = payload.get("sub")
    return str(subject) if subject else None
