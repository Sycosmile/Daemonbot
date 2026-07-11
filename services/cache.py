"""
services/cache.py — Simple in-memory TTL cache.

Why this exists: with passive $ticker/CA autodetect now live, the same CA
getting pasted a few times in a row in a busy group used to mean a fresh
DexScreener/CoinGecko call every single time. Free-tier APIs will start
429-ing under that kind of load. A short TTL (price doesn't meaningfully
change in 15-20s for casual lookups) fixes that cheaply.

Not meant for anything that needs to be exact to the second — /scan and /p
results can be ~20s stale and nobody will notice.
"""

import time
import asyncio


class TTLCache:
    def __init__(self, ttl: int = 20):
        self.ttl = ttl
        self._store: dict[str, tuple] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(self, key: str, coro_func):
        """coro_func is a zero-arg callable returning a coroutine."""
        async with self._lock:
            entry = self._store.get(key)
            if entry and (time.time() - entry[1]) < self.ttl:
                return entry[0]

        result = await coro_func()

        async with self._lock:
            self._store[key] = (result, time.time())
        return result

    def clear_expired(self):
        now = time.time()
        self._store = {k: v for k, v in self._store.items() if now - v[1] < self.ttl}

    def size(self) -> int:
        return len(self._store)
