from unittest.mock import patch

import jwt as pyjwt

from app.core import auth


def test_no_token_returns_401(anon_client):
    r = anon_client.get("/v1/profiles/me")
    assert r.status_code == 401


def test_invalid_token_returns_401(anon_client):
    """decode_token is mocked to raise rather than sending a garbage token
    through the real JWKS flow - that would hit the network (a fake
    SUPABASE_URL in tests), which is a different failure mode
    (connection error, not "invalid token") than what this test is for.
    """
    with patch.object(auth, "decode_token", side_effect=pyjwt.InvalidTokenError("bad token")):
        r = anon_client.get("/v1/profiles/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_valid_token_returns_200(client, fake_db, test_user):
    fake_db.set_response(
        "profiles",
        {
            "id": str(test_user.id),
            "email": test_user.email,
            "is_coach": False,
            "display_name": None,
            "created_at": "2026-01-01T00:00:00Z",
        },
    )
    r = client.get("/v1/profiles/me")
    assert r.status_code == 200
    assert r.json()["email"] == test_user.email
