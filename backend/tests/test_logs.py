import uuid
from datetime import date, datetime, timedelta, timezone

LOG_ID = uuid.uuid4()
FOOD_ID = uuid.uuid4()


def _summary_row(log_date, quantity, calories=200, protein_g=10, carbs_g=20, fat_g=5):
    return {
        "log_date": log_date,
        "quantity": quantity,
        "custom_foods": {"calories": calories, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g},
    }


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


def test_summary_averages_only_over_days_with_logs(client, fake_db):
    today = date.today()
    fake_db.set_response(
        "food_logs",
        [
            _summary_row(today.isoformat(), 2),  # 400 kcal
            _summary_row((today - timedelta(days=1)).isoformat(), 1),  # 200 kcal
            _summary_row((today - timedelta(days=3)).isoformat(), 3),  # 600 kcal
        ],
    )

    r = client.get("/v1/logs/summary?period=week")

    assert r.status_code == 200
    body = r.json()
    assert body["days_with_logs"] == 3
    # (400 + 200 + 600) / 3 = 400, not / 7 - unlogged days aren't "0 kcal"
    assert body["average"]["calories"] == 400
    assert body["average"]["protein_g"] == "20"
    assert len(body["daily"]) == 3
    assert body["daily"][0]["log_date"] <= body["daily"][-1]["log_date"]  # chronological


def test_summary_sums_multiple_dishes_on_the_same_day(client, fake_db):
    today = date.today().isoformat()
    fake_db.set_response(
        "food_logs",
        [
            _summary_row(today, 1, calories=300, protein_g=20, carbs_g=30, fat_g=10),
            _summary_row(today, 1, calories=150, protein_g=5, carbs_g=15, fat_g=5),
        ],
    )

    r = client.get("/v1/logs/summary?period=week")

    body = r.json()
    assert body["days_with_logs"] == 1
    assert body["daily"][0]["calories"] == 450
    assert body["average"]["calories"] == 450


def test_summary_returns_zero_when_no_logs(client, fake_db):
    fake_db.set_response("food_logs", [])

    r = client.get("/v1/logs/summary?period=month")

    assert r.status_code == 200
    body = r.json()
    assert body["days_with_logs"] == 0
    assert body["average"]["calories"] == 0
    assert body["daily"] == []


def test_summary_ignores_row_with_no_matching_food(client, fake_db):
    """A food_logs row whose food was deleted (shouldn't normally happen -
    FK cascade deletes the log too - but the embed could still come back
    null) shouldn't crash the aggregation."""
    today = date.today().isoformat()
    row = _summary_row(today, 1)
    row["custom_foods"] = None
    fake_db.set_response("food_logs", [row])

    r = client.get("/v1/logs/summary?period=week")

    assert r.status_code == 200
    assert r.json()["days_with_logs"] == 0


def test_summary_invalid_period_returns_422(client, fake_db):
    fake_db.set_response("food_logs", [])
    r = client.get("/v1/logs/summary?period=year")
    assert r.status_code == 422


def test_summary_requires_auth(anon_client):
    r = anon_client.get("/v1/logs/summary")
    assert r.status_code == 401
