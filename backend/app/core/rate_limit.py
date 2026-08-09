import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import decode_token


def rate_limit_key(request: Request) -> str:
    """Key by user ID for a valid bearer token, otherwise by IP. A bad or
    missing token just falls back to the IP-based (stricter) tier — auth
    itself is still enforced separately by each route's own dependencies.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        try:
            payload = decode_token(auth_header[7:])
            return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


def estimate_rate_limit(key: str) -> str:
    """5/min for anonymous (IP-keyed) callers, 15/min for authenticated
    ones — matches the free Gemini tier's need to stay well under quota
    while still being noticeably more generous for signed-in users.
    """
    return "15/minute" if key.startswith("user:") else "5/minute"


limiter = Limiter(key_func=rate_limit_key)
