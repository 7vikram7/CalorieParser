import uuid
from datetime import date, datetime, timezone

LOG_ID = uuid.uuid4()
FOOD_ID = uuid.uuid4()


def _log_row(user_id, **overrides):
    row = {
        "id": str(LOG_ID),
        "user_id": str(user_id),
        "food_id": str(FOOD_ID),
        "log_date": date.today().isoformat(),
        "quantity": "1.5",
        "meal_type": "breakfast",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    row.update(overrides)
    return row


def test_create_log_returns_200(client, fake_db, test_user):
    fake_db.set_response("food_logs", [_log_row(test_user.id)])

    r = client.post(
        "/v1/logs",
        json={
            "food_id": str(FOOD_ID),
            "log_date": date.today().isoformat(),
            "quantity": 1.5,
            "meal_type": "breakfast",
        },
    )

    assert r.status_code == 200
    assert r.json()["quantity"] == "1.5"
    assert fake_db.inserted["food_logs"][0]["user_id"] == str(test_user.id)


def test_list_my_logs_returns_created_log(client, fake_db, test_user):
    fake_db.set_response("food_logs", [_log_row(test_user.id)])

    r = client.get("/v1/logs")

    assert r.status_code == 200
    assert len(r.json()) == 1


def test_update_log_returns_updated_quantity(client, fake_db, test_user):
    fake_db.set_response("food_logs", [_log_row(test_user.id, quantity="2.0")])

    r = client.patch(f"/v1/logs/{LOG_ID}", json={"quantity": 2.0})

    assert r.status_code == 200
    assert r.json()["quantity"] == "2.0"
    # model_dump(mode="json") serializes Decimal as a string, not a float -
    # this is the route's correct, existing behavior, not a test choice.
    assert fake_db.updated["food_logs"][0] == {"quantity": "2.0"}


def test_update_nonexistent_log_returns_404(client, fake_db):
    fake_db.set_response("food_logs", [])  # no row matched the id/user_id filter

    r = client.patch(f"/v1/logs/{uuid.uuid4()}", json={"quantity": 2.0})

    assert r.status_code == 404


def test_delete_log_returns_204(client, fake_db, test_user):
    fake_db.set_response("food_logs", [])

    r = client.delete(f"/v1/logs/{LOG_ID}")

    assert r.status_code == 204


def test_create_log_requires_auth(anon_client):
    r = anon_client.post(
        "/v1/logs",
        json={"food_id": str(FOOD_ID), "log_date": date.today().isoformat(), "quantity": 1},
    )
    assert r.status_code == 401
