"""
services/calendar.py — Economic calendar (/cal)
Daemonbot — MR SYCO (@Sycosmile)

NOTE: There's no solid free-and-no-key economic calendar API as of writing —
everything decent (Trading Economics, FXStreet, Finnhub) needs at least a free
signup. Finnhub's free tier covers this reasonably, so that's what's wired up
here. Get a key at https://finnhub.io/register and set FINNHUB_API_KEY in .env.
Without a key, this command degrades to a clear "add a key" message instead
of crashing.
"""

import httpx
from datetime import datetime, timedelta, timezone
from config import FINNHUB_API_KEY

FINNHUB_API = "https://finnhub.io/api/v1"


async def get_economic_calendar() -> str:
    if not FINNHUB_API_KEY:
        return (
            "❌ `/cal` needs a free Finnhub API key.\n"
            "Get one at https://finnhub.io/register (no credit card) and add "
            "`FINNHUB_API_KEY` to your `.env`."
        )

    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=2)

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(
                f"{FINNHUB_API}/calendar/economic",
                params={"from": today.isoformat(), "to": end.isoformat(), "token": FINNHUB_API_KEY},
            )
        except httpx.HTTPError as e:
            return f"❌ Calendar fetch failed: {type(e).__name__}"

        if r.status_code == 401:
            return "❌ Invalid Finnhub API key — double-check `FINNHUB_API_KEY` in `.env`."
        if r.status_code == 429:
            return "❌ Finnhub rate limit hit. Try again shortly."
        if r.status_code != 200:
            return f"❌ Finnhub returned {r.status_code}."

        data = r.json()

    events = data.get("economicCalendar") or data.get("data") or []
    if not isinstance(events, list) or not events:
        return "📅 No major economic events in the next 48 hours."

    # Keep medium/high impact only, sorted by time
    def _impact(e):
        return str(e.get("impact", "")).lower()

    filtered = [e for e in events if _impact(e) in ("high", "medium", "2", "3")]
    if not filtered:
        filtered = events  # fall back to showing everything if impact field is missing/different

    filtered.sort(key=lambda e: str(e.get("time", e.get("date", ""))))

    lines = ["📅 *Economic Calendar — Next 48h*\n"]
    for e in filtered[:12]:
        impact_emoji = "🔴" if _impact(e) in ("high", "3") else "🟡"
        when = str(e.get("time", e.get("date", "?")))[:16]
        country = e.get("country", "")
        name = e.get("event", e.get("name", "Unknown event"))
        prev = e.get("prev", e.get("previous", "-"))
        est = e.get("estimate", e.get("forecast", "-"))
        lines.append(f"{impact_emoji} `{when}` {country} — *{name}* (prev: {prev}, est: {est})")

    lines.append("\n_High-impact macro events move crypto too, not just forex. NFA._")
    return "\n".join(lines)
