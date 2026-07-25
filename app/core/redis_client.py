import time
import threading
from typing import Dict, Any, List, Tuple, Optional

class InMemoryCache:
    """
    A production-ready thread-safe in-memory cache to replace Redis.
    Supports basic keys (with TTL) and Sorted Sets (ZADD, ZSCORE, etc).
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}

    def _cleanup_expired(self, key: str):
        if key in self._expires and time.time() > self._expires[key]:
            self._data.pop(key, None)
            self._expires.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._cleanup_expired(key)
            return self._data.get(key)

    def set(self, key: str, value: Any, ex: int = None):
        with self._lock:
            self._data[key] = value
            if ex is not None:
                self._expires[key] = time.time() + ex
            else:
                self._expires.pop(key, None)

    def setex(self, key: str, time_sec: int, value: Any):
        self.set(key, value, ex=time_sec)

    def delete(self, key: str):
        with self._lock:
            self._data.pop(key, None)
            self._expires.pop(key, None)

    # Sorted Set Operations
    def zadd(self, name: str, mapping: Dict[str, float]):
        with self._lock:
            self._cleanup_expired(name)
            if name not in self._data or not isinstance(self._data[name], dict):
                self._data[name] = {}
            for member, score in mapping.items():
                self._data[name][str(member)] = float(score)

    def zscore(self, name: str, value: str) -> Optional[float]:
        with self._lock:
            self._cleanup_expired(name)
            zset = self._data.get(name, {})
            if isinstance(zset, dict):
                return zset.get(str(value))
            return None

    def _get_sorted_members(self, name: str) -> List[Tuple[str, float]]:
        zset = self._data.get(name, {})
        if not isinstance(zset, dict):
            return []
        # sort descending by score, then ascending by member name (lexicographical) to ensure deterministic order
        return sorted(zset.items(), key=lambda x: (-x[1], x[0]))

    def zrevrank(self, name: str, value: str) -> Optional[int]:
        with self._lock:
            self._cleanup_expired(name)
            members = self._get_sorted_members(name)
            for i, (member, _) in enumerate(members):
                if member == str(value):
                    return i
            return None

    def zrevrange(self, name: str, start: int, end: int, withscores: bool = False) -> List[Any]:
        with self._lock:
            self._cleanup_expired(name)
            members = self._get_sorted_members(name)
            if end < 0:
                end = len(members) + end
            
            # handle out of bounds gracefully like redis
            end = min(end, len(members) - 1)
            start = max(start, 0)
            
            if start > end or start >= len(members):
                return []
                
            slice_data = members[start:end+1]
            if withscores:
                return slice_data
            return [member for member, _ in slice_data]

redis_client = InMemoryCache()

def get_redis():
    return redis_client
