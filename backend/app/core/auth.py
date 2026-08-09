from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.core.config import settings
from app.core.supabase import get_supabase_client
from app.models.user import UserResponse

_bearer_scheme = HTTPBearer(auto_error=False)

# Supabase signs tokens asymmetrically and publishes public keys at this
# well-known JWKS URL — verifying against it (rather than a shared secret)
# means keys can rotate on Supabase's side without a backend redeploy.
_jwks_client = jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")


def decode_token(token: str) -> dict:
    """Verify a Supabase-issued JWT against its JWKS and return the decoded
    payload. Raises `jwt.PyJWTError` (not HTTPException) on anything invalid
    so non-HTTP callers (e.g. the rate limiter's key function) can decide
    for themselves how to handle a bad/missing token.
    """
    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience="authenticated",
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> UserResponse:
    """Verify the `Authorization: Bearer <token>` header against Supabase's
    JWKS and return the caller's identity. Raises 401 on anything invalid.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    return UserResponse(id=payload["sub"], email=payload["email"])


def get_current_user_client(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    user: UserResponse = Depends(get_current_user),
) -> Client:
    """A Supabase client scoped to the current request's caller, for route
    handlers that need to run queries under the caller's own RLS context.
    """
    return get_supabase_client(credentials.credentials)
