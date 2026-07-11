"""
services/domain.py — WHOIS lookup (/do)
Daemonbot — MR SYCO (@Sycosmile)

NOTE: uses python-whois, which speaks raw WHOIS (TCP/43) to registry servers.
That protocol is older and less firewall-friendly than HTTPS — if this runs
somewhere that blocks outbound port 43 (some corporate networks/containers),
lookups will time out. Works fine on a normal VPS/home connection.
"""

import asyncio
import whois
from datetime import datetime, timezone


def _fmt_date(val) -> str:
    """WHOIS dates come back as datetime, list of datetimes, or None — normalize."""
    if isinstance(val, list):
        val = val[0] if val else None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val) if val else "Unknown"


def _fmt_field(val) -> str:
    if isinstance(val, list):
        val = ", ".join(str(v) for v in val[:3]) if val else None
    return str(val) if val else "Unknown / redacted"


async def lookup_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    if "." not in domain:
        return "❌ That doesn't look like a domain. Try `/do example.com`"

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: whois.whois(domain, timeout=10))
    except Exception as e:
        return (f"❌ WHOIS lookup failed for `{domain}` ({type(e).__name__}). "
                f"Registry may be rate-limiting or the domain doesn't exist.")

    if not result or not result.get("domain_name"):
        return f"❌ No WHOIS record found for `{domain}`."

    registrar = _fmt_field(result.get("registrar"))
    created = _fmt_date(result.get("creation_date"))
    expires = _fmt_date(result.get("expiration_date"))
    updated = _fmt_date(result.get("updated_date"))
    status = _fmt_field(result.get("status"))
    name_servers = result.get("name_servers")
    ns_text = ", ".join(sorted(set(name_servers))[:4]) if name_servers else "Unknown"
    org = _fmt_field(result.get("org") or result.get("registrant_organization"))
    country = _fmt_field(result.get("country") or result.get("registrant_country"))

    # Age-based flag — freshly registered domains are a common scam signal
    age_flag = ""
    try:
        created_raw = result.get("creation_date")
        if isinstance(created_raw, list):
            created_raw = created_raw[0]
        if isinstance(created_raw, datetime):
            if created_raw.tzinfo is None:
                created_raw = created_raw.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created_raw).days
            if age_days < 30:
                age_flag = f"\n🚨 *Domain is only {age_days} days old* — common scam-site signal."
            elif age_days < 180:
                age_flag = f"\n⚠️ Domain is {age_days} days old — still fairly new."
    except Exception:
        pass

    msg = (
        f"🌐 *Domain Check*\n"
        f"🔗 `{domain}`\n\n"
        f"🏢 Registrar: `{registrar}`\n"
        f"📅 Created: `{created}` | Expires: `{expires}` | Updated: `{updated}`\n"
        f"📍 Org/Country: `{org}` / `{country}`\n"
        f"📡 Nameservers: `{ns_text}`\n"
        f"📋 Status: `{status}`"
        f"{age_flag}"
    )
    return msg
