import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

SESSION_COOKIE = "cartaad_session"
CLIENT_COOKIE = "cartaad_client"


def hash_password(password: str) -> str:
    iterations = get_settings().password_iterations
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def _serializer(salt: str = "session") -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=salt)


def make_session_token(user_id: int) -> str:
    return _serializer().dumps({"uid": user_id})


def read_session_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=get_settings().session_max_age)
    except (BadSignature, SignatureExpired):
        return None
    return int(data.get("uid")) if isinstance(data, dict) and data.get("uid") else None


def sign_file_key(key: str, salt: str = "file") -> str:
    return _serializer(salt).dumps(key)


def read_file_key(token: str, max_age: int = 60 * 60 * 24 * 30, salt: str = "file") -> str | None:
    try:
        return _serializer(salt).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
