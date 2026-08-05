from supabase import Client, create_client

from app.core.config import settings


def get_supabase_client(access_token: str) -> Client:
    """A Supabase client scoped to the caller's own JWT.

    Using the anon key + the caller's token (rather than the service role
    key) means every query still goes through RLS as that specific user —
    so a coach querying an athlete's food_logs is only allowed through
    because the `is_active_coach_of` policy says so, not because the
    backend silently has admin rights.
    """
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


def get_service_role_client() -> Client:
    """Bypasses RLS entirely. Reserve for operations with no natural 'owner'
    context — e.g. resolving an athlete's email to a user_id during a coach
    invite. Never use this for anything a normal user-scoped query can do.
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
