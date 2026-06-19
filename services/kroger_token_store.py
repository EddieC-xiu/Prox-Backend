# services/kroger_token_store.py
#
# Pluggable storage for per-user Kroger OAuth tokens.
#
# Two backends:
#   - LocalJSONTokenStore   -> writes to a local JSON file. Default. Used for the
#                             demo so nothing touches production Supabase.
#   - SupabaseTokenStore    -> writes to a `kroger_tokens` table. Used later, only
#                             after the migration in migrations/ is applied.
#
# Backend is chosen by the env var KROGER_TOKEN_STORE = "local" | "supabase".
# Default is "local".
#
# A "token record" is a plain dict:
#   {
#     "user_id":       str,
#     "access_token":  str,
#     "refresh_token": str | None,
#     "expires_at":    float,   # unix epoch seconds
#     "scope":         str,
#     "updated_at":    str,     # ISO timestamp
#   }

import os
import json
import time
import threading
from datetime import datetime, timezone

_LOCAL_PATH = os.getenv(
    "KROGER_TOKEN_FILE",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".kroger_tokens.json"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalJSONTokenStore:
    """Demo-safe token store backed by a single JSON file on disk.

    Keyed by user_id. Thread-safe for the single-process dev server.
    """

    def __init__(self, path: str = _LOCAL_PATH):
        self.path = path
        self._lock = threading.Lock()

    def _read_all(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_all(self, data: dict) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, self.path)

    def get(self, user_id: str) -> dict | None:
        with self._lock:
            return self._read_all().get(user_id)

    def set(self, record: dict) -> None:
        with self._lock:
            data = self._read_all()
            data[record["user_id"]] = record
            self._write_all(data)

    def delete(self, user_id: str) -> None:
        with self._lock:
            data = self._read_all()
            data.pop(user_id, None)
            self._write_all(data)


class SupabaseTokenStore:
    """Production token store backed by the `kroger_tokens` Supabase table.

    Requires the migration in migrations/2026..._create_kroger_tokens.sql to be
    applied first. Only used when KROGER_TOKEN_STORE=supabase.
    """

    TABLE = "kroger_tokens"

    def __init__(self):
        # Imported lazily so the demo path never needs Supabase configured.
        from config.supabase import get_supabase_client
        self.sb = get_supabase_client()

    def get(self, user_id: str) -> dict | None:
        res = (
            self.sb.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    def set(self, record: dict) -> None:
        self.sb.table(self.TABLE).upsert(record, on_conflict="user_id").execute()

    def delete(self, user_id: str) -> None:
        self.sb.table(self.TABLE).delete().eq("user_id", user_id).execute()


_store = None


def get_token_store():
    """Return the configured token store singleton."""
    global _store
    if _store is None:
        backend = os.getenv("KROGER_TOKEN_STORE", "local").strip().lower()
        if backend == "supabase":
            _store = SupabaseTokenStore()
        else:
            _store = LocalJSONTokenStore()
    return _store


def make_record(
    user_id: str,
    token_response: dict,
) -> dict:
    """Build a normalized token record from a Kroger token-endpoint response."""
    expires_in = int(token_response.get("expires_in", 1800))
    return {
        "user_id": user_id,
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token"),
        # subtract a 60s safety margin so we refresh slightly early
        "expires_at": time.time() + expires_in - 60,
        "scope": token_response.get("scope", ""),
        "updated_at": _now_iso(),
    }


def is_expired(record: dict) -> bool:
    return time.time() >= float(record.get("expires_at", 0))
