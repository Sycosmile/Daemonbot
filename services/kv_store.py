"""
services/kv_store.py — Persistent key-value storage via Upstash Redis's
REST API (survives Render redeploys, unlike local disk on the free tier),
with automatic fallback to local JSON files when Upstash isn't configured
— e.g. local dev on your machine where you don't want every test hitting
the network.

Set these two env vars (in Render's dashboard, never committed to a file):
  UPSTASH_REDIS_REST_URL
  UPSTASH_REDIS_REST_TOKEN

If they're not set, every function below just returns None / False and
callers fall back to their local-file path automatically.
"""

import os
import json
import httpx

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

_HEADERS = {"Authorization": f"Bearer {UPSTASH_TOKEN}"} if UPSTASH_TOKEN else {}


def is_configured() -> bool:
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


def kv_get(key: str) -> dict | None:
    """Fetch and JSON-decode a value. None if missing, unconfigured, or on
    any error — callers should treat None as 'fall back to local file'."""
    if not is_configured():
        return None
    try:
        r = httpx.get(f"{UPSTASH_URL}/get/{key}", headers=_HEADERS, timeout=5)
        r.raise_for_status()
        result = r.json().get("result")
        if result is None:
            return None
        return json.loads(result)
    except Exception:
        return None


def kv_set(key: str, value: dict) -> bool:
    """JSON-encode and store a value. Returns True only on confirmed
    success — callers should fall back to writing the local file if this
    returns False, so data is never silently lost."""
    if not is_configured():
        return False
    try:
        payload = json.dumps(value)
        r = httpx.post(f"{UPSTASH_URL}/set/{key}", headers=_HEADERS, content=payload, timeout=5)
        r.raise_for_status()
        return bool(r.json().get("result"))
    except Exception:
        return False
