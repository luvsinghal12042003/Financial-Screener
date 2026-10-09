import time
import threading
from typing import Any, Optional, Dict, Tuple


class BaseCache:
    """Base cache interface to facilitate swapping in Redis or Memcached in future phases."""
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError


class InMemoryCache(BaseCache):
    """
    Thread-safe in-memory cache with TTL (Time To Live).
    Can easily be swapped for Redis in future production phases.
    """
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            expiry, value = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + effective_ttl
        with self._lock:
            self._cache[key] = (expiry, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> None:
        """Removes expired items to prevent unbounded memory growth."""
        now = time.time()
        with self._lock:
            expired_keys = [k for k, (exp, _) in self._cache.items() if now > exp]
            for k in expired_keys:
                del self._cache[k]


# Global cache instance for Phase 1
cache = InMemoryCache(default_ttl=180)
