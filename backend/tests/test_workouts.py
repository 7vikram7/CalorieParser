import uuid
from datetime import date, datetime, timezone

WORKOUT_ID = uuid.uuid4()
EXERCISE_ID = uuid.uuid4()


def _workout_row(user_id, **overrides):
    row = {
        "id": str(WORKOUT_ID),
        "user_id": str(user_id),
        "workout_date": date.today().isoformat(),
        "name": "Push Day",
        "notes": None,
        "duration_minutes": 45,
        "intensity": "hard",
        "calories_burned": 400,
        "avg_heart_rate": 140,
        "source": "manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    row.update(overrides)
    return row


def _set_row(is_pr=False, weight_kg="100.0"):
    return {
        "id": str(uuid.uuid4()),
        "workout_id": str(WORKOUT_ID),
        "exercise_id": str(EXERCISE_ID),
        "set_number": 1,
        "reps": 5,
        "weight_kg": weight_kg,
        "duration_seconds": None,
        "distance_m": None,
        "rpe": None,
        "notes": None,
        "is_pr": is_pr,
    }


def test_create_workout_returns_200(client, fake_db, test_user):
    fake_db.set_response("workouts", [_workout_row(test_user.id)])

    r = client.post("/v1/workouts", json={"workout_date": date.today().isoformat(), "name": "Push Day"})

    assert r.status_code == 200
    assert r.json()["name"] == "Push Day"
    assert fake_db.inserted["workouts"][0]["user_id"] == str(test_user.id)


def test_list_my_workouts_returns_created_workout(client, fake_db, test_user):
    fake_db.set_response("workouts", [_workout_row(test_user.id)])

    r = client.get("/v1/workouts")

    assert r.status_code == 200
    assert len(r.json()) == 1


def test_delete_workout_returns_204(client, fake_db):
    fake_db.set_response("workouts", [])

    r = client.delete(f"/v1/workouts/{WORKOUT_ID}")

    assert r.status_code == 204


def test_add_set_flags_pr_when_weight_beats_previous_max(client, fake_db):
    # First execute() on "workout_sets" (the previous-max lookup) sees a
    # lighter set than what's being logged now; second execute() (the
    # insert) returns the row the route just wrote.
    fake_db.queue_responses("workout_sets", [_set_row(weight_kg="80.0")], [_set_row(is_pr=True, weight_kg="100.0")])

    r = client.post(
        f"/v1/workouts/{WORKOUT_ID}/sets",
        json={"exercise_id": str(EXERCISE_ID), "set_number": 1, "reps": 5, "weight_kg": 100},
    )

    assert r.status_code == 200
    assert r.json()["is_pr"] is True
    assert fake_db.inserted["workout_sets"][0]["is_pr"] is True


def test_add_set_does_not_flag_pr_when_weight_below_previous_max(client, fake_db):
    fake_db.queue_responses(
        "workout_sets", [_set_row(weight_kg="120.0")], [_set_row(is_pr=False, weight_kg="100.0")]
    )

    r = client.post(
        f"/v1/workouts/{WORKOUT_ID}/sets",
        json={"exercise_id": str(EXERCISE_ID), "set_number": 1, "reps": 5, "weight_kg": 100},
    )

    assert r.status_code == 200
    assert r.json()["is_pr"] is False
    assert fake_db.inserted["workout_sets"][0]["is_pr"] is False


def test_add_set_flags_pr_on_first_ever_set_for_exercise(client, fake_db):
    # No previous sets at all -> previous_max is None -> is_pr defaults True.
    fake_db.queue_responses("workout_sets", [], [_set_row(is_pr=True, weight_kg="50.0")])

    r = client.post(
        f"/v1/workouts/{WORKOUT_ID}/sets",
        json={"exercise_id": str(EXERCISE_ID), "set_number": 1, "reps": 5, "weight_kg": 50},
    )

    assert r.status_code == 200
    assert r.json()["is_pr"] is True


def test_create_workout_requires_auth(anon_client):
    r = anon_client.post("/v1/workouts", json={"workout_date": date.today().isoformat()})
    assert r.status_code == 401
