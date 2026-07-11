"""
services/summary.py — AI group chat summarizer (/summary)
Stores recent group messages in memory, summarizes with Claude.
"""

from openai import AsyncOpenAI
from collections import defaultdict, deque
from datetime import datetime
from config import GROQ_API_KEY, AI_MODEL

client = AsyncOpenAI(api_key=GROQ_API_KEY or "unset", base_url="https://api.groq.com/openai/v1")

# In-memory message store per chat — last 100 messages
_message_store: dict[int, deque] = defaultdict(lambda: deque(maxlen=100))

SUMMARY_PROMPT = """You are Daemonbot summarizing a crypto group chat.
Given a list of messages, write a punchy summary covering:
- What tokens were discussed or called
- Any alpha or important info shared
- General sentiment (bullish/bearish/neutral)
- Any drama or notable moments

Format:
📋 *Summary*
<2-4 bullet points max, each one sentence>

🌡 *Sentiment:* <Bullish/Bearish/Mixed>

Keep it short and degen. No fluff."""


def store_message(chat_id: int, username: str, text: str):
    """Store a message for later summarization."""
    _message_store[chat_id].append({
        "user": username,
        "text": text[:200],  # cap per message
        "time": datetime.utcnow().strftime("%H:%M"),
    })


async def summarize_chat(chat_id: int, limit: int = 50) -> str:
    """Summarize last N messages in a group."""
    messages = list(_message_store[chat_id])[-limit:]

    if len(messages) < 5:
        return (
            "❌ Not enough messages to summarize yet.\n"
            "_Daemonbot needs to be active in the chat for a while first._"
        )

    # Format messages for Claude
    convo = "\n".join(
        f"[{m['time']}] {m['user']}: {m['text']}"
        for m in messages
    )

    prompt = f"Summarize these {len(messages)} group chat messages:\n\n{convo}"

    try:
        resp = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        )
        result = resp.choices[0].message.content.strip()
        return f"{result}\n\n_Last {len(messages)} messages • Daemonbot_"
    except Exception as e:
        return f"❌ Summary failed: {type(e).__name__}"
