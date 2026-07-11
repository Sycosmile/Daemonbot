"""
services/fixlinks.py — Auto-detect and fix social media links in group messages.

Phanes-style: When someone pastes an X/Twitter, TikTok, Instagram, or
Polymarket link in a group, the bot intercepts it and returns a clean
readable summary.

For X/Twitter: fetch tweet text via Nitter
For TikTok: real title/author via TikTok's public oEmbed endpoint
For Instagram: clean labeled link (Instagram's oEmbed now needs a Meta token)
For Polymarket: market question + current Yes price via the public Gamma API
Also: if tweet contains a CA, auto-fetch token price.
"""

import httpx
import asyncio
import re
from typing import Optional

from services.crypto import fetch_token_by_address, build_price_message

# ── Regex patterns ────────────────────────────────────────────────────────────
TWITTER_URL_RE = re.compile(
    r'https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/\s]+)/status/(\d+)',
    re.IGNORECASE
)
TWITTER_PROFILE_RE = re.compile(
    r'https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/?\s]+)/?(?:\?[^\s]*)?$',
    re.IGNORECASE
)
TIKTOK_URL_RE = re.compile(
    r'https?://(?:www\.)?(?:vm\.tiktok\.com|tiktok\.com)/[^\s]+',
    re.IGNORECASE
)
INSTAGRAM_URL_RE = re.compile(
    r'https?://(?:www\.)?instagram\.com/[^\s]+',
    re.IGNORECASE
)
POLYMARKET_URL_RE = re.compile(
    r'https?://(?:www\.)?polymarket\.com/(?:event|market)/([^/\s?]+)',
    re.IGNORECASE
)

# CA patterns (Solana = 32-44 base58 chars, EVM = 0x + 40 hex)
CA_RE = re.compile(
    r'\b(0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})\b'
)

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]


async def fetch_tweet_text(tweet_id: str, username: str) -> Optional[str]:
    """Fetch tweet content via Nitter."""
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{username}/status/{tweet_id}"
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                # Extract tweet text
                html = r.text
                match = re.search(
                    r'<div class="tweet-content media-body"[^>]*>(.*?)</div>',
                    html, re.DOTALL
                )
                if match:
                    raw = match.group(1)
                    # Strip HTML tags
                    text = re.sub(r'<[^>]+>', '', raw).strip()
                    return text
        except Exception:
            continue
    return None


async def fetch_tiktok_info(url: str) -> Optional[dict]:
    """TikTok's oEmbed endpoint is public and needs no key — unlike Instagram's
    (which now requires a Meta app token), so we can get real title/author here."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://www.tiktok.com/oembed", params={"url": url})
            if r.status_code == 200:
                data = r.json()
                return {
                    "title": data.get("title", "TikTok video"),
                    "author": data.get("author_name", "Unknown"),
                }
    except Exception:
        pass
    return None


def fix_instagram_link(url: str) -> str:
    """Return a cleaner Instagram link.
    NOTE: full caption extraction isn't available without a Meta Graph API
    token (Instagram's oEmbed walled that off years ago) — this stays a
    clean labeled link rather than guessing at content we can't verify."""
    return f"[Instagram Post]({url})"


async def fetch_polymarket_market(slug: str) -> Optional[dict]:
    """Polymarket's Gamma API is public/read-only, no key needed."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get("https://gamma-api.polymarket.com/markets", params={"slug": slug})
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data[0]
    except Exception:
        pass
    return None


async def process_tweet_link(username: str, tweet_id: str, original_url: str) -> str:
    """Process a tweet URL — fetch text, detect CA, return formatted message."""
    tweet_text = await fetch_tweet_text(tweet_id, username)

    parts = [f"🐦 *Tweet by @{username}*\n"]

    if tweet_text:
        # Truncate if too long
        display_text = tweet_text[:280] + ("..." if len(tweet_text) > 280 else "")
        parts.append(f"_{display_text}_\n")

        # Check for CA in tweet
        ca_matches = CA_RE.findall(tweet_text)
        if ca_matches:
            parts.append("💊 *CA detected — fetching price...*")
            ca = ca_matches[0]
            pair = await fetch_token_by_address(ca)
            if pair:
                price_msg = build_price_message(pair)
                parts.append(f"\n{price_msg}")
            else:
                parts.append(f"\n`{ca}`\n_Token not found on DexScreener._")
    else:
        parts.append("_Could not fetch tweet content — Nitter may be down._")

    parts.append(f"\n[View Original]({original_url})")
    return "\n".join(parts)


async def process_message_for_links(text: str) -> Optional[str]:
    """
    Check a message for social links. Returns formatted response or None.
    Called for every group message.
    """
    results = []

    # X/Twitter tweet links
    for match in TWITTER_URL_RE.finditer(text):
        username  = match.group(1)
        tweet_id  = match.group(2)
        orig_url  = match.group(0)
        # Skip bot/spam accounts
        if username.lower() in ("i", "share", "intent"):
            continue
        result = await process_tweet_link(username, tweet_id, orig_url)
        results.append(result)

    # Twitter profile links (not tweet)
    for match in TWITTER_PROFILE_RE.finditer(text):
        username = match.group(1)
        if username.lower() in ("i", "share", "intent", "home", "explore"):
            continue
        # Don't double-process if already caught as tweet
        if TWITTER_URL_RE.search(text):
            continue
        results.append(
            f"👤 *X Profile: @{username}*\n"
            f"[View Profile](https://x.com/{username}) | "
            f"[Check Recycled](/x @{username})\n"
            f"_Use /x @{username} to check for recycled account signals._"
        )

    # TikTok
    for match in TIKTOK_URL_RE.finditer(text):
        url = match.group(0)
        info = await fetch_tiktok_info(url)
        if info:
            results.append(f"🎵 *TikTok by {info['author']}*\n_{info['title'][:150]}_\n[Watch]({url})")
        else:
            results.append(f"🎵 *TikTok Video*\n[Watch]({url})")

    # Instagram
    for match in INSTAGRAM_URL_RE.finditer(text):
        results.append(f"📸 *Instagram Link*\n{fix_instagram_link(match.group(0))}")

    # Polymarket
    for match in POLYMARKET_URL_RE.finditer(text):
        slug = match.group(1)
        orig_url = match.group(0)
        market = await fetch_polymarket_market(slug)
        if market:
            question = market.get("question", slug)
            yes_price = market.get("outcomePrices", ["?", "?"])
            try:
                import json as _json
                prices = _json.loads(yes_price) if isinstance(yes_price, str) else yes_price
                yes_pct = f"{float(prices[0]) * 100:.0f}%"
            except Exception:
                yes_pct = "?"
            results.append(
                f"🎲 *Polymarket*\n*{question}*\n"
                f"📊 Yes: `{yes_pct}`\n[View Market]({orig_url})"
            )
        else:
            results.append(f"🎲 *Polymarket Market*\n[View]({orig_url})")

    if results:
        return "\n\n━━━━━━━━━━━━━━━\n\n".join(results)
    return None
