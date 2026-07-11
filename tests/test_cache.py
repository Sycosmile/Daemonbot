"""
tests/test_cache.py
"""

import asyncio
import pytest
from services.cache import TTLCache


@pytest.mark.asyncio
async def test_cache_returns_fresh_value_on_first_call():
    cache = TTLCache(ttl=60)
    calls = []

    async def fetch():
        calls.append(1)
        return "result"

    result = await cache.get_or_set("key1", fetch)
    assert result == "result"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cache_hits_on_second_call_within_ttl():
    cache = TTLCache(ttl=60)
    calls = []

    async def fetch():
        calls.append(1)
        return f"result-{len(calls)}"

    first = await cache.get_or_set("key1", fetch)
    second = await cache.get_or_set("key1", fetch)
    assert first == second  # same cached value, fetch only ran once
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_cache_expires_after_ttl():
    cache = TTLCache(ttl=0.05)  # 50ms
    calls = []

    async def fetch():
        calls.append(1)
        return f"result-{len(calls)}"

    first = await cache.get_or_set("key1", fetch)
    await asyncio.sleep(0.1)  # wait past TTL
    second = await cache.get_or_set("key1", fetch)
    assert first != second
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_different_keys_dont_collide():
    cache = TTLCache(ttl=60)

    async def fetch_a():
        return "A"

    async def fetch_b():
        return "B"

    a = await cache.get_or_set("key_a", fetch_a)
    b = await cache.get_or_set("key_b", fetch_b)
    assert a == "A"
    assert b == "B"
