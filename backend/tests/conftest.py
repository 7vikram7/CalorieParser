import os

# Settings() is constructed at import time in app.core.config, and
# app.core.auth builds a jwt.PyJWKClient against SUPABASE_URL at import
# time too (lazily - no network call until a token is actually decoded,
# verified directly before writing this). These must be set before
# anything under app/ is imported, so this has to be the first thing that
# happens in this file, ahead of any app.* import below.
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-role-key")
os.environ.setdefault("GEMINI_API_KEY", "fake-gemini-key")
os.environ.setdefault("GROQ_API_KEY", "fake-groq-key")
os.environ.setdefault("USDA_API_KEY", "fake-usda-key")

import uuid  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.auth import get_current_user, get_current_user_client  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserResponse  # noqa: E402

TEST_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TEST_USER_EMAIL = "test@example.com"


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQueryBuilder:
    """Stands in for supabase-py's fluent query builder. Filter methods
    (.eq/.order/.range/.single/etc.) are no-ops that return self - these
    tests are about route logic (status codes, response shaping,
    validation, PR-detection math), not re-verifying Postgres/RLS
    filtering, which only a real database can actually exercise.
    .execute() returns whatever the test configured via
    FakeSupabaseClient.set_response() for this table.
    """

    def __init__(self, client: "FakeSupabaseClient", table_name: str):
        self._client = client
        self._table = table_name

    def select(self, *a, **k):
        return self

    def insert(self, body):
        self._client.inserted.setdefault(self._table, []).append(body)
        return self

    def update(self, body):
        self._client.updated.setdefault(self._table, []).append(body)
        return self

    def upsert(self, body, **k):
        self._client.upserted.setdefault(self._table, []).append(body)
        return self

    def delete(self):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def single(self):
        return self

    def execute(self):
        queue = self._client.queued.get(self._table)
        if queue:
            return FakeResult(queue.pop(0))
        return FakeResult(self._client.responses.get(self._table, []))


class FakeSupabaseClient:
    def __init__(self):
        self.responses: dict[str, object] = {}
        self.queued: dict[str, list] = {}
        self.inserted: dict[str, list] = {}
        self.updated: dict[str, list] = {}
        self.upserted: dict[str, list] = {}

    def table(self, name: str) -> FakeQueryBuilder:
        return FakeQueryBuilder(self, name)

    def set_response(self, table_name: str, data) -> None:
        """`data` is a list for most queries, or a single dict for a
        `.single()` call (matches supabase-py's real return shape, which
        `profiles.get_my_profile` relies on by returning `result.data`
        directly rather than `result.data[0]`).
        """
        self.responses[table_name] = data

    def queue_responses(self, table_name: str, *responses) -> None:
        """For routes that call `.execute()` on the same table more than
        once per request with different intent (e.g. add_set's "look up
        previous sets, then insert the new one") - each call to
        `.execute()` on this table pops the next queued response, in
        order, before falling back to `set_response`'s static value.
        """
        self.queued.setdefault(table_name, []).extend(responses)


@pytest.fixture
def fake_db() -> FakeSupabaseClient:
    return FakeSupabaseClient()


@pytest.fixture
def test_user() -> UserResponse:
    return UserResponse(id=TEST_USER_ID, email=TEST_USER_EMAIL)


@pytest.fixture
def client(fake_db, test_user):
    """An authenticated TestClient: get_current_user/get_current_user_client
    are overridden so routes never hit Supabase's real JWKS endpoint or a
    real database - standard FastAPI testing pattern, and the only
    practical one here, since actually satisfying JWKS verification in a
    test would require Supabase's real private signing key.
    """
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_current_user_client] = lambda: fake_db
    limiter.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """A TestClient with no auth override, for testing 401s and the
    unauthenticated /v1/foods/estimate endpoint."""
    limiter.reset()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
