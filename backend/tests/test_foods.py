import uuid
from datetime import datetime, timezone

FOOD_ID = uuid.uuid4()


def _food_row(user_id):
    return {
        "id": str(FOOD_ID),
        "user_id": str(user_id),
        "name": "Homemade Dal",
        "serving_size_value": "250.0",
        "serving_size_unit": "g",
        "calories": 300,
        "protein_g": "15.0",
        "carbs_g": "40.0",
        "fat_g": "8.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_create_custom_food_returns_200_with_correct_fields(client, fake_db, test_user):
    fake_db.set_response("custom_foods", [_food_row(test_user.id)])

    r = client.post(
        "/v1/foods",
        json={
            "name": "Homemade Dal",
            "serving_size_value": 250,
            "serving_size_unit": "g",
            "calories": 300,
            "protein_g": 15,
            "carbs_g": 40,
            "fat_g": 8,
        },
    )

    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Homemade Dal"
    assert body["calories"] == 300
    assert body["user_id"] == str(test_user.id)
    assert fake_db.inserted["custom_foods"][0]["user_id"] == str(test_user.id)


def test_list_my_foods_returns_created_food(client, fake_db, test_user):
    fake_db.set_response("custom_foods", [_food_row(test_user.id)])

    r = client.get("/v1/foods")

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == str(FOOD_ID)


def test_list_my_foods_requires_auth(anon_client):
    r = anon_client.get("/v1/foods")
    assert r.status_code == 401
