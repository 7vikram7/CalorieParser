import uuid
from datetime import datetime, timezone

BODY_METRICS_ID = uuid.uuid4()


def _profile_row(test_user, **overrides):
    row = {
        "id": str(test_user.id),
        "email": test_user.email,
        "display_name": "Test User",
        "is_coach": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    row.update(overrides)
    return row


def _body_metrics_row(test_user, **overrides):
    row = {
        "id": str(BODY_METRICS_ID),
        "user_id": str(test_user.id),
        "height_cm": "175.0",
        "weight_kg": "70.0",
        "bmr": 1650,
        "activity_level": "moderately_active",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    row.update(overrides)
    return row


def test_get_my_profile_returns_200(client, fake_db, test_user):
    fake_db.set_response("profiles", _profile_row(test_user))  # single() -> dict, not list

    r = client.get("/v1/profiles/me")

    assert r.status_code == 200
    assert r.json()["email"] == test_user.email


def test_update_my_profile_returns_updated_name(client, fake_db, test_user):
    fake_db.set_response("profiles", [_profile_row(test_user, display_name="New Name")])

    r = client.patch("/v1/profiles/me", json={"display_name": "New Name"})

    assert r.status_code == 200
    assert r.json()["display_name"] == "New Name"


def test_get_body_metrics_404_when_none_set(client, fake_db):
    fake_db.set_response("body_metrics", [])

    r = client.get("/v1/profiles/me/body-metrics")

    assert r.status_code == 404


def test_get_body_metrics_returns_row_when_set(client, fake_db, test_user):
    fake_db.set_response("body_metrics", [_body_metrics_row(test_user)])

    r = client.get("/v1/profiles/me/body-metrics")

    assert r.status_code == 200
    assert r.json()["bmr"] == 1650


def test_upsert_body_metrics_uses_on_conflict_user_id(client, fake_db, test_user):
    fake_db.set_response("body_metrics", [_body_metrics_row(test_user, bmr=1700)])

    r = client.put("/v1/profiles/me/body-metrics", json={"bmr": 1700})

    assert r.status_code == 200
    assert r.json()["bmr"] == 1700
    assert fake_db.upserted["body_metrics"][0]["user_id"] == str(test_user.id)


def test_get_my_profile_requires_auth(anon_client):
    r = anon_client.get("/v1/profiles/me")
    assert r.status_code == 401
