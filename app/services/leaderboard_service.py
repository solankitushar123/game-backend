"""
LeaderboardService — Redis sorted-set backed leaderboards.

Why Redis ZSET instead of live SQL aggregation on every page view:
  - O(log N) rank lookups and O(log N + M) range reads, regardless of player count.
  - Avoids hammering Postgres with ORDER BY/LIMIT queries from every concurrent viewer.
  - This is exactly the "Redis-cached leaderboards instead of live aggregation queries"
    scale-readiness requirement from the blueprint.

Postgres (tournament_entries.best_score) remains the source of truth — Redis is a
cache that is rebuilt from Postgres on submission and can be fully rehydrated at any time.
"""
from typing import List, Tuple
import uuid

from app.core.redis_client import redis_client


def _zset_key(tournament_id: uuid.UUID) -> str:
    return f"leaderboard:tournament:{tournament_id}"


class LeaderboardService:

    @staticmethod
    def update_score(tournament_id: uuid.UUID, user_id: uuid.UUID, score: int) -> None:
        key = _zset_key(tournament_id)
        # ZADD with GT-like semantics: only raise, never lower a player's best score in the cache.
        current = redis_client.zscore(key, str(user_id))
        if current is None or score > current:
            redis_client.zadd(key, {str(user_id): score})

    @staticmethod
    def get_top(tournament_id: uuid.UUID, limit: int = 50) -> List[Tuple[str, float]]:
        key = _zset_key(tournament_id)
        return redis_client.zrevrange(key, 0, limit - 1, withscores=True)

    @staticmethod
    def get_rank(tournament_id: uuid.UUID, user_id: uuid.UUID) -> int | None:
        key = _zset_key(tournament_id)
        rank = redis_client.zrevrank(key, str(user_id))
        return rank + 1 if rank is not None else None

    @staticmethod
    def get_score(tournament_id: uuid.UUID, user_id: uuid.UUID) -> float | None:
        key = _zset_key(tournament_id)
        return redis_client.zscore(key, str(user_id))

    @staticmethod
    def get_all_ranked(tournament_id: uuid.UUID) -> List[Tuple[str, float]]:
        """Used at settlement time to compute final ranks for the whole tournament."""
        key = _zset_key(tournament_id)
        return redis_client.zrevrange(key, 0, -1, withscores=True)

    @staticmethod
    def rebuild_from_db(tournament_id: uuid.UUID, entries: List[Tuple[str, int]]) -> None:
        """Rehydrate Redis cache from Postgres (source of truth) — used on cache miss/restart."""
        key = _zset_key(tournament_id)
        redis_client.delete(key)
        if entries:
            redis_client.zadd(key, {user_id: score for user_id, score in entries})
