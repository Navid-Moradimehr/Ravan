"""Simple in-memory cache with TTL for frequently accessed data."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    """Simple TTL cache with max size."""
    
    def __init__(self, ttl_seconds: float = 60.0, max_size: int = 1000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache: dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None
        return value
    
    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_size:
            # Evict oldest
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del self._cache[oldest[0]]
        self._cache[key] = (value, time.time() + self.ttl)
    
    def clear(self) -> None:
        self._cache.clear()


# Global cache instances
_hierarchy_cache = TTLCache(ttl_seconds=300.0, max_size=1)
_scenarios_cache = TTLCache(ttl_seconds=300.0, max_size=1)


def cached_hierarchy() -> TTLCache:
    return _hierarchy_cache


def cached_scenarios() -> TTLCache:
    return _scenarios_cache


def ttl_cache(ttl_seconds: float = 60.0, max_size: int = 1000) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for TTL-cached functions."""
    cache = TTLCache(ttl_seconds=ttl_seconds, max_size=max_size)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            key = f"{func.__name__}:{args}:{kwargs}"
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result
        return wrapper
    return decorator
