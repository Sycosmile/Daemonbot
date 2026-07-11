"""
services/ai.py — Groq (free) AI integration for Daemonbot personality.
Uses the OpenAI-compatible Groq API. Sign up free at console.groq.com.
"""

from openai import AsyncOpenAI
from config import GROQ_API_KEY, AI_MODEL, BOT_PERSONA

client = AsyncOpenAI(
    api_key=GROQ_API_KEY or "unset",
    base_url="https://api.groq.com/openai/v1",
)

# Per-chat conversation history (in-memory, resets on restart)
_histories: dict[int, list[dict]] = {}
MAX_HISTORY = 10


def get_history(chat_id: int) -> list[dict]:
    return _histories.get(chat_id, [])


def append_history(chat_id: int, role: str, content: str):
    if chat_id not in _histories:
        _histories[chat_id] = []
    _histories[chat_id].append({"role": role, "content": content})
    if len(_histories[chat_id]) > MAX_HISTORY * 2:
        _histories[chat_id] = _histories[chat_id][-MAX_HISTORY * 2:]


def clear_history(chat_id: int):
    _histories.pop(chat_id, None)


async def chat(chat_id: int, user_message: str) -> str:
    """Send a message to Groq with full conversation context."""
    append_history(chat_id, "user", user_message)
    history = get_history(chat_id)

    try:
        response = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=300,
            messages=[{"role": "system", "content": BOT_PERSONA}, *history],
        )
        reply = response.choices[0].message.content.strip()
        append_history(chat_id, "assistant", reply)
        return reply
    except Exception as e:
        return f"My brain glitched ser. Try again. ({type(e).__name__})"


# ── Reply-triggered AI tools (/eli5, /explain, /fact, /translate) ────────────
REPLY_TOOL_PROMPTS = {
    "eli5": (
        "Explain the following message like you're explaining it to a curious "
        "5-year-old. Keep it short, simple, and a little fun. No jargon."
    ),
    "explain": (
        "Explain the following message clearly, with any relevant context a "
        "reader might be missing. 2-4 sentences, plain language."
    ),
    "fact": (
        "Fact-check the following claim. State clearly whether it's true, "
        "false, or unclear/disputed, then briefly say why in 1-3 sentences. "
        "Be direct — don't hedge more than the actual uncertainty warrants."
    ),
    "translate": (
        "Translate the following text to English. If it's already in "
        "English, instead rewrite it in clear, simplified English. "
        "Return ONLY the translation/rewrite, nothing else."
    ),
}


async def reply_tool(action: str, text: str) -> str:
    """Stateless one-shot AI tool — no conversation history."""
    system_prompt = REPLY_TOOL_PROMPTS.get(action)
    if not system_prompt:
        return "❌ Unknown AI tool."
    if not text.strip():
        return "❌ Nothing to work with — reply to a message that has text."
    try:
        response = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=250,
            messages=[
                {"role": "system",  "content": system_prompt},
                {"role": "user",    "content": text[:2000]},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ AI tool failed: {type(e).__name__}"
