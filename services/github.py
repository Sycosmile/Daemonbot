"""
services/github.py — GitHub repo health check (/gh)
Daemonbot — MR SYCO (@Sycosmile)
"""

import re
import httpx
from datetime import datetime, timezone
from config import GITHUB_TOKEN

GITHUB_API = "https://api.github.com"


async def get_repo_health(owner_repo: str) -> str:
    owner_repo = owner_repo.strip()
    owner_repo = re.sub(r"^https?://github\.com/", "", owner_repo).strip("/")
    if "/" not in owner_repo:
        return "❌ Format: `/gh owner/repo` (e.g. `/gh Sycosmile/Daemonbot`)"
    parts = owner_repo.split("/")
    owner, repo = parts[0], parts[1]

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            r = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        except httpx.HTTPError as e:
            return f"❌ GitHub lookup failed: {type(e).__name__}"

        if r.status_code == 404:
            return f"❌ Repo `{owner}/{repo}` not found."
        if r.status_code == 403:
            return ("❌ GitHub rate limit hit (60/hr unauthenticated). "
                    "Add `GITHUB_TOKEN` to `.env` for 5,000/hr.")
        if r.status_code != 200:
            return f"❌ GitHub returned {r.status_code}."

        data = r.json()

        # Contributor count — best effort, GitHub doesn't expose this directly
        contrib_count = "?"
        try:
            cr = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
                params={"per_page": 1, "anon": "true"},
            )
            if cr.status_code == 200:
                link = cr.headers.get("Link", "")
                m = re.search(r'page=(\d+)>;\s*rel="last"', link)
                contrib_count = m.group(1) if m else str(len(cr.json()))
        except Exception:
            pass

    name = data.get("full_name", owner_repo)
    desc = (data.get("description") or "No description set").strip()
    stars = data.get("stargazers_count", 0)
    forks = data.get("forks_count", 0)
    watchers = data.get("subscribers_count", 0)
    open_issues = data.get("open_issues_count", 0)
    language = data.get("language") or "Unknown"
    license_info = data.get("license") or {}
    license_name = license_info.get("spdx_id") or "None"
    archived = data.get("archived", False)
    created = (data.get("created_at") or "")[:10]
    pushed = (data.get("pushed_at") or "")[:10]
    homepage = data.get("homepage") or ""

    days_since_push = None
    try:
        pushed_dt = datetime.fromisoformat(data["pushed_at"].replace("Z", "+00:00"))
        days_since_push = (datetime.now(timezone.utc) - pushed_dt).days
    except Exception:
        pass

    pros, cons = [], []

    if archived:
        cons.append("🗄️ Archived — read-only, no longer maintained")
    elif days_since_push is not None:
        if days_since_push <= 30:
            pros.append(f"🟢 Active — last push {days_since_push}d ago")
        elif days_since_push <= 180:
            pros.append(f"🟡 Semi-active — last push {days_since_push}d ago")
        else:
            cons.append(f"🔴 Stale — last push {days_since_push}d ago")

    if stars >= 100:
        pros.append(f"⭐ {stars:,} stars — decent traction")
    elif stars < 5:
        cons.append("⭐ Very few stars — low visibility")

    if license_name and license_name not in ("None", "NOASSERTION"):
        pros.append(f"📜 Licensed ({license_name})")
    else:
        cons.append("📜 No clear license — legally murky to fork/use")

    if str(contrib_count).isdigit():
        cc = int(contrib_count)
        if cc == 1:
            cons.append("👤 Single contributor — bus-factor of 1, no peer review")
        elif cc >= 5:
            pros.append(f"👥 {cc}+ contributors — peer-reviewed codebase")

    if open_issues > 50:
        cons.append(f"🐛 {open_issues} open issues — may be undermaintained")

    if data.get("description") is None:
        cons.append("📝 No description set")

    pros_text = "\n".join(f"  {p}" for p in pros) or "  (none flagged)"
    cons_text = "\n".join(f"  {c}" for c in cons) or "  (none flagged)"

    msg = (
        f"🔍 *GitHub Repo Check*\n"
        f"📦 *{name}*\n"
        f"_{desc[:150]}_\n\n"
        f"⭐ Stars: `{stars:,}` | 🍴 Forks: `{forks:,}` | 👁️ Watchers: `{watchers:,}`\n"
        f"🧑‍💻 Contributors: `{contrib_count}` | 🐛 Open issues: `{open_issues:,}`\n"
        f"💻 Language: `{language}` | 📜 License: `{license_name}`\n"
        f"📅 Created: `{created}` | Last push: `{pushed}`\n"
    )
    if homepage:
        msg += f"🔗 {homepage}\n"
    msg += (
        f"\n✅ *Pros:*\n{pros_text}\n\n"
        f"⚠️ *Cons:*\n{cons_text}\n\n"
        f"[View on GitHub](https://github.com/{owner}/{repo})"
    )
    return msg
