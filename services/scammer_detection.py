"""
services/scammer_detection.py — Drainer/scam link + phishing pattern detection.
Daemonbot — MR SYCO (@Sycosmile)

Design: fast local heuristics run on every message (cheap, no API call). Claude
only gets called as a tie-breaker when a message already has a link AND at
least one heuristic flag — calling AI on every single group message would be
slow and expensive for no benefit on the 99% of messages that are obviously
fine.

Deliberately conservative: this module only DETECTS and SCORES. Deciding what
to do about it (delete/warn/ban) lives in the handler, and v1 of that handler
only deletes + warns — it does NOT auto-ban. An automated system banning real
people on a false positive is a much worse outcome than letting one scam
message slip through for a human admin to handle.
"""

import re
from openai import AsyncOpenAI
from config import GROQ_API_KEY, AI_MODEL

client = AsyncOpenAI(api_key=GROQ_API_KEY or "unset", base_url="https://api.groq.com/openai/v1")

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
IP_URL_RE = re.compile(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

# Starter list — expand as you see real spam in your own groups. This is
# intentionally NOT exhaustive; it's a first line of defense, not a complete
# blocklist.
URGENCY_PHRASES = [
    r"connect (your )?wallet to claim",
    r"verify (your )?wallet",
    r"wallet (has been )?selected",
    r"claim your airdrop",
    r"limited time.{0,20}claim",
    r"\bact now\b.{0,20}(claim|wallet|airdrop)",
    r"congratulations.{0,30}(won|selected|airdrop)",
    r"validate your wallet",
    r"free mint.{0,20}(connect|claim)",
]
URGENCY_RE = re.compile("|".join(URGENCY_PHRASES), re.IGNORECASE)

# Common typosquat patterns of wallet/exchange brand names combined with a
# suspicious extra word — real Metamask/Phantom/Binance domains don't look like this.
TYPOSQUAT_RE = re.compile(
    r"(metamask|phantom|binance|coinbase|trustwallet|uniswap|opensea)"
    r"[-.](?:support|verify|claim|airdrop|wallet|secure|login|connect)",
    re.IGNORECASE,
)

SUSPICIOUS_TLDS = (".xyz", ".top", ".click", ".live", ".club", ".info", ".gq", ".cf")


def _local_score(text: str) -> dict:
    """Fast, no-network heuristic pass. Returns flags + a 0-100 score."""
    flags = []
    score = 0

    urls = URL_RE.findall(text)
    has_link = bool(urls)

    if IP_URL_RE.search(text):
        flags.append("Raw IP-address link (legit sites essentially never look like this)")
        score += 40

    if URGENCY_RE.search(text):
        flags.append("Urgency/claim-bait phrasing typical of drainer scams")
        score += 35

    if TYPOSQUAT_RE.search(text):
        flags.append("Wallet/exchange brand name combined with a suspicious word")
        score += 40

    for url in urls:
        if any(url.lower().endswith(tld) or f"{tld}/" in url.lower() for tld in SUSPICIOUS_TLDS):
            flags.append(f"Link uses a TLD commonly abused for scam sites ({url[:40]})")
            score += 15
            break

    return {"score": min(score, 100), "flags": flags, "has_link": has_link}


async def _ai_second_opinion(text: str) -> dict:
    """Only called when local heuristics already flagged something borderline."""
    try:
        resp = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=120,
            messages=[
                {"role": "system", "content": (
                    "You detect crypto wallet-drainer / phishing scam messages in a "
                    "Telegram group. Reply with ONLY valid JSON: "
                    '{"is_scam": true/false, "confidence": 0-100, "reason": "short reason"}. '
                    "Be conservative — only flag clear scam-bait (fake airdrop claims, "
                    "wallet verification requests, urgency to connect a wallet). "
                    "Normal crypto trading talk, including links to real DEXs/explorers, is NOT a scam."
                )},
                {"role": "user", "content": text[:500]},
            ],
        )
        import json
        raw = resp.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        return json.loads(raw)
    except Exception:
        return {"is_scam": False, "confidence": 0, "reason": "AI check failed, defaulting to safe"}


async def check_message(text: str) -> dict:
    """
    Main entry point. Returns:
    {"is_scam": bool, "confidence": int, "reasons": [...]}
    """
    local = _local_score(text)

    # Strong local signal alone (e.g. typosquat + urgency) — don't even need AI
    if local["score"] >= 70:
        return {"is_scam": True, "confidence": local["score"], "reasons": local["flags"]}

    # Borderline: link present + at least one weak flag → ask AI to break the tie
    if local["has_link"] and local["flags"]:
        ai = await _ai_second_opinion(text)
        if ai.get("is_scam") and ai.get("confidence", 0) >= 60:
            reasons = local["flags"] + [ai.get("reason", "AI flagged as likely scam")]
            return {"is_scam": True, "confidence": ai["confidence"], "reasons": reasons}

    return {"is_scam": False, "confidence": local["score"], "reasons": local["flags"]}
