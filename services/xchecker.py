"""
services/xchecker.py — Recycled X (Twitter) account detector (/x)

Strategy (no paid API needed):
1. Fetch public profile via Nitter or web scrape proxies
2. Use RapidAPI Twitter scraper (free tier) OR tweeter.me public data
3. Flag signals: account age vs followers, username change patterns,
   creation date vs project launch, suspended/reactivated history

For full recycled detection like Phanes (User ID cross-reference),
you need a Twitter/X API v2 Basic plan (~$100/mo). This implementation
uses free signals + heuristics as a strong approximation.
"""

import httpx
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional


# ── Free public data sources ──────────────────────────────────────────────────
# NOTE: Public Nitter instances are unreliable — most got shut down or rate-
# limited after X tightened anti-scraping measures. /x will gracefully fall
# back to "couldn't fetch" if all instances fail. Swap in working instances as
# you find them, or replace this with a paid X API v2 lookup if it matters
# enough to your group.
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.net",
]

TWITTER_API_BASE = "https://api.twitter.com/2"  # needs Bearer token


async def fetch_nitter_profile(username: str) -> Optional[dict]:
    """Scrape basic profile info from Nitter (free, no API key)."""
    username = username.lstrip("@")
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{username}"
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                html = r.text
                return parse_nitter_html(html, username)
        except Exception:
            continue
    return None


def parse_nitter_html(html: str, username: str) -> dict:
    """Extract key fields from Nitter profile HTML."""
    result = {"username": username, "raw_html": True}

    # Join date
    join_match = re.search(r'Joined\s+(\w+\s+\d{4})', html)
    if join_match:
        result["joined"] = join_match.group(1)
        try:
            result["joined_dt"] = datetime.strptime(join_match.group(1), "%B %Y")
        except ValueError:
            pass

    # Display name
    name_match = re.search(r'<a class="profile-card-fullname"[^>]*>([^<]+)<', html)
    if name_match:
        result["display_name"] = name_match.group(1).strip()

    # Followers
    followers_match = re.search(r'(\d[\d,]*)\s*<span[^>]*>Followers', html)
    if followers_match:
        result["followers"] = int(followers_match.group(1).replace(",", ""))

    # Following
    following_match = re.search(r'(\d[\d,]*)\s*<span[^>]*>Following', html)
    if following_match:
        result["following"] = int(following_match.group(1).replace(",", ""))

    # Tweets count
    tweets_match = re.search(r'(\d[\d,]*)\s*<span[^>]*>Tweets', html)
    if tweets_match:
        result["tweets"] = int(tweets_match.group(1).replace(",", ""))

    # Bio
    bio_match = re.search(r'<div class="profile-bio"><p>(.*?)</p>', html, re.DOTALL)
    if bio_match:
        result["bio"] = re.sub(r'<[^>]+>', '', bio_match.group(1)).strip()

    # Verified badge
    result["verified"] = 'title="Verified account"' in html or "verified-icon" in html

    # Suspended check
    result["suspended"] = "This account has been suspended" in html or "Account suspended" in html

    return result


def analyze_recycled_signals(profile: dict) -> dict:
    """
    Score recycled account likelihood based on available signals.
    Returns: { score: 0-100, flags: [...], verdict: str }
    """
    flags = []
    score = 0

    joined_dt = profile.get("joined_dt")
    followers  = profile.get("followers", 0)
    following  = profile.get("following", 0)
    tweets     = profile.get("tweets", 0)
    bio        = profile.get("bio", "")
    suspended  = profile.get("suspended", False)

    now = datetime.now()

    # Flag: account age
    if joined_dt:
        age_months = (now.year - joined_dt.year) * 12 + (now.month - joined_dt.month)
        if age_months > 36 and followers < 500 and tweets < 100:
            flags.append("🚩 Old account, low activity — possible recycled shell")
            score += 35
        elif age_months > 24 and followers < 200:
            flags.append("⚠️ Aged account with suspiciously low following")
            score += 20

    # Flag: follower/following ratio
    if following > 0 and followers < following * 0.1:
        flags.append("🚩 Very low follower/following ratio — botted or recycled")
        score += 25
    elif following > 5000 and followers < 1000:
        flags.append("⚠️ Mass following with few followers — suspicious")
        score += 15

    # Flag: low tweet count on old account
    if joined_dt and tweets < 50:
        age_months = (now.year - joined_dt.year) * 12 + (now.month - joined_dt.month)
        if age_months > 12:
            flags.append("🚩 Barely any tweets for account age — likely dormant/recycled")
            score += 20

    # Flag: suspended history (can't detect directly from Nitter, but check current)
    if suspended:
        flags.append("🚨 Account is currently SUSPENDED")
        score += 40

    # Flag: crypto project bio keywords on old account
    crypto_keywords = ["launch", "presale", "mint", "token", "ca:", "0x", "pump", "gem", "degen"]
    if bio and any(kw in bio.lower() for kw in crypto_keywords):
        if joined_dt:
            age_months = (now.year - joined_dt.year) * 12 + (now.month - joined_dt.month)
            if age_months > 12:
                flags.append("⚠️ Old account now shilling crypto — possible rebrand")
                score += 15

    # No flags
    if not flags:
        flags.append("✅ No obvious recycled signals detected")

    # Verdict
    score = min(score, 100)
    if score >= 60:
        verdict = "🔴 HIGH RISK — likely recycled or compromised account"
    elif score >= 30:
        verdict = "🟡 MEDIUM RISK — some suspicious signals"
    else:
        verdict = "🟢 LOW RISK — looks clean"

    return {"score": score, "flags": flags, "verdict": verdict}


def _fmt_count(val) -> str:
    """Format a count with thousands separators, falling back safely
    when Nitter parsing didn't find the field (val stays '?')."""
    try:
        return f"{int(val):,}"
    except (TypeError, ValueError):
        return "?"


def format_x_check(profile: dict, analysis: dict, username: str) -> str:
    joined   = profile.get("joined", "Unknown")
    followers = _fmt_count(profile.get("followers", "?"))
    following = _fmt_count(profile.get("following", "?"))
    tweets   = _fmt_count(profile.get("tweets", "?"))
    name     = profile.get("display_name", username)
    bio      = profile.get("bio", "—")[:100]
    verified = "✅" if profile.get("verified") else "❌"
    suspended = "🚨 YES" if profile.get("suspended") else "No"

    flags_text = "\n".join(f"  {f}" for f in analysis["flags"])
    score = analysis["score"]
    verdict = analysis["verdict"]

    msg = (
        f"🔍 *X Account Check*\n"
        f"👤 *{name}* `@{username}`\n\n"
        f"📅 Joined: `{joined}`\n"
        f"👥 Followers: `{followers}` | Following: `{following}`\n"
        f"🐦 Tweets: `{tweets}`\n"
        f"✔️ Verified: {verified} | Suspended: {suspended}\n"
        f"📝 Bio: _{bio}_\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🧪 *Recycle Score: {score}/100*\n"
        f"{verdict}\n\n"
        f"*Signals:*\n{flags_text}\n\n"
        f"⚠️ _Note: Full User ID recycled detection requires X API. "
        f"These are heuristic signals only._\n"
        f"[View Profile](https://x.com/{username})"
    )
    return msg


async def check_x_account(username: str) -> str:
    username = username.lstrip("@").strip()
    if not username:
        return "❌ Please provide a username. Usage: `/x @username`"

    profile = await fetch_nitter_profile(username)

    if not profile:
        return (
            f"❌ Couldn't fetch `@{username}` — Nitter may be down.\n"
            f"Try checking manually: [x.com/{username}](https://x.com/{username})"
        )

    analysis = analyze_recycled_signals(profile)
    return format_x_check(profile, analysis, username)
