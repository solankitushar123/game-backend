"""Shared time helper — always use timezone-aware UTC datetimes throughout the app
to match Postgres TIMESTAMPTZ columns and avoid naive/aware comparison errors."""
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
