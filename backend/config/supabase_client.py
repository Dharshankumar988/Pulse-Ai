from supabase import Client, create_client

from config.settings import settings


class SupabaseConfigError(RuntimeError):
    pass


_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not settings.supabase_url or not settings.supabase_key:
        raise SupabaseConfigError(
            "Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_KEY."
        )

    _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase_client
