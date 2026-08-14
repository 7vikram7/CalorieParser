import uuid
from datetime import datetime, timezone

ATHLETE_ID = uuid.uuid4()
LINK_ID = uuid.uuid4()


def _link_row(coach_id, athlete_id, status="pending", **overrides):
    row = {
        "id": str(LINK_ID),
        "coach_id": str(coach_id),
        "athlete_id": str(athlete_id),
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "responded_at": None,
    }
    row.update(overrides)
    return row


def test_invite_athlete_by_email_returns_201(client, fake_db, test_user):
    fake_db.queue_responses(
        "profiles", [{"id": str(ATHLETE_ID)}]  # email lookup finds the athlete
    )
    fake_db.queue_responses("coach_athlete_links", [])  # no existing invite
    fake_db.set_response("coach_athlete_links", [_link_row(test_user.id, ATHLETE_ID)])

    r = client.post("/v1/coaches/invite", json={"athlete_email": "athlete@example.com"})

    assert r.status_code == 201
    assert r.json()["athlete_id"] == str(ATHLETE_ID)
    assert fake_db.inserted["coach_athlete_links"][0]["coach_id"] == str(test_user.id)


def test_invite_unknown_email_returns_404(client, fake_db):
    fake_db.set_response("profiles", [])  # no matching user

    r = client.post("/v1/coaches/invite", json={"athlete_email": "nobody@example.com"})

    assert r.status_code == 404


def test_invite_self_returns_400(client, fake_db, test_user):
    fake_db.set_response("profiles", [{"id": str(test_user.id)}])  # email resolves to caller

    r = client.post("/v1/coaches/invite", json={"athlete_email": test_user.email})

    assert r.status_code == 400


def test_invite_duplicate_returns_409(client, fake_db, test_user):
    fake_db.queue_responses("profiles", [{"id": str(ATHLETE_ID)}])
    fake_db.set_response("coach_athlete_links", [_link_row(test_user.id, ATHLETE_ID)])  # already exists

    r = client.post("/v1/coaches/invite", json={"athlete_email": "athlete@example.com"})

    assert r.status_code == 409


def test_list_pending_invites_returns_invites_for_athlete(client, fake_db, test_user):
    fake_db.set_response("coach_athlete_links", [_link_row(uuid.uuid4(), test_user.id, status="pending")])

    r = client.get("/v1/coaches/invites/pending")

    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "pending"


def test_respond_to_invite_accepts(client, fake_db, test_user):
    fake_db.set_response(
        "coach_athlete_links", [_link_row(uuid.uuid4(), test_user.id, status="active", responded_at=datetime.now(timezone.utc).isoformat())]
    )

    r = client.patch(f"/v1/coaches/links/{LINK_ID}", json={"status": "active"})

    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_respond_to_nonexistent_invite_returns_404(client, fake_db):
    fake_db.set_response("coach_athlete_links", [])

    r = client.patch(f"/v1/coaches/links/{uuid.uuid4()}", json={"status": "active"})

    assert r.status_code == 404


def test_list_my_athletes_returns_active_links(client, fake_db, test_user):
    fake_db.set_response("coach_athlete_links", [_link_row(test_user.id, ATHLETE_ID, status="active")])

    r = client.get("/v1/coaches/athletes")

    assert r.status_code == 200
    assert len(r.json()) == 1


def test_invite_athlete_requires_auth(anon_client):
    r = anon_client.post("/v1/coaches/invite", json={"athlete_email": "athlete@example.com"})
    assert r.status_code == 401
