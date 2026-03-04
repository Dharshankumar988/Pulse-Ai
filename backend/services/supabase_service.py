from uuid import uuid4
from datetime import date, datetime

from config.settings import settings
from config.supabase_client import get_supabase_client


class SupabaseServiceError(RuntimeError):
    pass


def _to_json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_safe(item) for item in value]
    return value


def _apply_filters(query, filters: dict):
    for key, value in filters.items():
        query = query.eq(key, value)
    return query


def select_rows(table: str, filters: dict | None = None, columns: str = "*") -> list[dict]:
    try:
        client = get_supabase_client()
        query = client.table(table).select(columns)
        query = _apply_filters(query, filters or {})
        response = query.execute()
        return response.data or []
    except Exception as exc:
        raise SupabaseServiceError(f"Failed to select from '{table}': {exc}") from exc


def insert_row(table: str, payload: dict) -> dict:
    try:
        client = get_supabase_client()
        response = client.table(table).insert(_to_json_safe(payload)).execute()
        data = response.data or []
        if not data:
            raise SupabaseServiceError(f"Insert into '{table}' returned no data")
        return data[0]
    except SupabaseServiceError:
        raise
    except Exception as exc:
        raise SupabaseServiceError(f"Failed to insert into '{table}': {exc}") from exc


def update_rows(table: str, match_filters: dict, updates: dict) -> list[dict]:
    try:
        client = get_supabase_client()
        query = client.table(table).update(_to_json_safe(updates))
        query = _apply_filters(query, match_filters)
        response = query.execute()
        return response.data or []
    except Exception as exc:
        raise SupabaseServiceError(f"Failed to update '{table}': {exc}") from exc


def delete_rows(table: str, match_filters: dict) -> list[dict]:
    try:
        client = get_supabase_client()
        query = client.table(table).delete()
        query = _apply_filters(query, match_filters)
        response = query.execute()
        return response.data or []
    except Exception as exc:
        raise SupabaseServiceError(f"Failed to delete from '{table}': {exc}") from exc


def upload_image_and_get_public_url(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    folder: str = "records",
) -> str:
    try:
        client = get_supabase_client()
        safe_filename = f"{uuid4()}-{filename}"
        object_path = f"{folder}/{safe_filename}"
        bucket = client.storage.from_(settings.supabase_storage_bucket)

        try:
            bucket.upload(
                path=object_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        except TypeError:
            bucket.upload(
                object_path,
                file_bytes,
                {"content-type": content_type, "upsert": "true"},
            )

        public_url_response = bucket.get_public_url(object_path)
        if isinstance(public_url_response, str):
            return public_url_response

        if isinstance(public_url_response, dict):
            data = public_url_response.get("data", {})
            public_url = data.get("publicUrl") or data.get("public_url")
            if public_url:
                return public_url

        response_data = getattr(public_url_response, "data", None)
        if isinstance(response_data, dict):
            public_url = response_data.get("publicUrl") or response_data.get("public_url")
            if public_url:
                return public_url

        raise SupabaseServiceError("Failed to resolve public URL for uploaded image")
    except SupabaseServiceError:
        raise
    except Exception as exc:
        raise SupabaseServiceError(f"Image upload failed: {exc}") from exc
