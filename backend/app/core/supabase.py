import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.core.config import settings

# Shared connection pool: create_client() otherwise opens a fresh httpx.Client
# (and TCP/TLS handshake) on every single request. Passing the same
# httpx.Client into every Supabase client reuses its connection pool instead.
# Safe under concurrency — .postgrest.auth() sets a header on the per-request
# Client/PostgrestClient wrapper, not on this shared httpx.Client itself.
_http_client = httpx.Client()


def get_supabase_client(access_token: str) -> Client:
    """A Supabase client scoped to the caller's own JWT.

    Using the anon key + the caller's token (rather than the service role
    key) means every query still goes through RLS as that specific user —
    so a coach querying an athlete's food_logs is only allowed through
    because the `is_active_coach_of` policy says so, not because the
    backend silently has admin rights.
    """
    client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY,
        options=SyncClientOptions(httpx_client=_http_client),
    )
    client.postgrest.auth(access_token)
    return client


def get_service_role_client() -> Client:
    """Bypasses RLS entirely. Reserve for operations with no natural 'owner'
    context — e.g. resolving an athlete's email to a user_id during a coach
    invite. Never use this for anything a normal user-scoped query can do.
    """
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
        options=SyncClientOptions(httpx_client=_http_client),
    )
