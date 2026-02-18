"""Singleton Supabase client initialized with service role key."""

from supabase import create_client, Client

_client: Client | None = None


def get_supabase_client() -> Client:
    """Return the shared Supabase client, creating it on first call."""
    global _client
    if _client is None:
        from config import Config
        _client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
    return _client
