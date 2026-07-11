"""
services/narrative.py — AI-generated token narrative (/nar)
Uses Claude to generate a punchy, degen-style narrative for any token.
"""

from openai import AsyncOpenAI
from config import GROQ_API_KEY, AI_MODEL

client = AsyncOpenAI(api_key=GROQ_API_KEY or "unset", base_url="https://api.groq.com/openai/v1")


NARRATIVE_PROMPT = """You are a crypto degen copywriter. Given token data, write a SHORT punchy narrative (3-5 sentences max).
Style: hype but honest, degen slang, based energy. Include what the token is about, the vibe, and a one-line risk note.
Format exactly like this:
🧬 *Narrative*
<the narrative here>

⚠️ _NFA DYOR ser._

Do NOT use markdown headers or bullet points. Just flowing text. Keep it under 80 words."""


async def generate_narrative(
    name: str,
    symbol: str,
    chain: str,
    price_usd: str,
    market_cap: str,
    volume_24h: str,
    price_change_24h: str,
    liquidity: str,
    dex: str,
    ca: str,
) -> str:
    token_info = f"""
Token: {name} (${symbol})
Chain: {chain}
DEX: {dex}
Price: {price_usd}
Market Cap: {market_cap}
24h Volume: {volume_24h}
24h Change: {price_change_24h}%
Liquidity: {liquidity}
Contract: {ca}
"""

    try:
        response = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=200,
            messages=[
                {"role": "system", "content": NARRATIVE_PROMPT},
                {"role": "user",   "content": f"Write a narrative for this token:\n{token_info}"},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Narrative generation failed: {type(e).__name__}"
