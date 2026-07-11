"""
services/pnl_card.py — Daemonbot PNL Card v3

Design language: original flat-geometric "daemon" mark (horns + glowing
slit eyes — a brand mark, not a character illustration) on an ember-particle
navy/plum atmosphere, with a huge focal PNL%% as the hero element. Structural
DNA borrowed from the Rick/Phanes genre (mascot accent + ticker/call-price +
giant %% + caller/time + reached-since-call + footer) — none of their actual
(copyrighted) character art is used or referenced.

NOTE: this card shows market cap (call_mc / reached_mc), not raw token
price — meme-coin prices are tiny fractions that read poorly at a glance;
mcap is what the reference bots in this genre show too. mcap is derived from
the live pair's current mcap and the price ratio, since we only persist
price history, not historical mcap (see _price_to_mcap below).
"""

import io
import random
import time
from datetime import datetime, timezone

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FACTOR = 3
W, H = 860, 600

NAVY_DARK = (11, 18, 32)
NAVY_MID = (18, 30, 52)
PLUM = (58, 32, 58)
GOLD = (214, 178, 110)
GOLD_BRIGHT = (240, 200, 130)
EMBER = (224, 140, 80)
FOREST = (96, 168, 122)
RED_MUTED = (196, 92, 84)
CREAM = (240, 236, 226)
MUTED = (140, 149, 170)
BORDER = (40, 52, 76)

import os
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts") + "/"


def _f(name, size):
    return ImageFont.truetype(FONT_DIR + name, size * FACTOR)


F_BRAND = _f("Poppins-Bold.ttf", 17)
F_SUB = _f("Poppins-Medium.ttf", 12)
F_CHAIN = _f("Poppins-Bold.ttf", 13)
F_TICKER = _f("Poppins-Bold.ttf", 34)
F_CALLPRICE = _f("Poppins-Medium.ttf", 16)
F_PNL = _f("Poppins-Bold.ttf", 104)
F_PNLLABEL = _f("Poppins-Bold.ttf", 16)
F_CALLER = _f("Poppins-Bold.ttf", 20)
F_TIME = _f("Poppins-Regular.ttf", 17)
F_REACHED = _f("Poppins-Medium.ttf", 18)
F_FOOTER = _f("Poppins-Regular.ttf", 14)
F_CTA = _f("Poppins-Bold.ttf", 15)


def _tw(draw, txt, fnt):
    return draw.textlength(txt, font=fnt)


def _gradient_bg(w, h, top, bottom):
    """Tiny diagonal-gradient base, upscaled with LANCZOS — no numpy needed."""
    base_n = 24
    base = Image.new("RGB", (base_n, base_n))
    for by in range(base_n):
        for bx in range(base_n):
            t = by / (base_n - 1) * 0.8 + bx / (base_n - 1) * 0.2
            base.putpixel((bx, by), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return base.resize((w, h), Image.LANCZOS)


ASH = (108, 104, 118)  # dim, cool-toned — used for the "rough" mood's glow/embers


def _ember_field(w, h, n=40, seed=3, mood="content"):
    if mood == "blazing":
        n, palette, alpha_range = int(n * 1.5), [EMBER, GOLD_BRIGHT, GOLD_BRIGHT], (160, 255)
    elif mood == "rough":
        n, palette, alpha_range = max(10, n // 2), [ASH, ASH, EMBER], (60, 130)
    else:
        n, palette, alpha_range = n, [EMBER, EMBER, GOLD_BRIGHT], (120, 220)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.choice([2, 3, 3, 4, 5]) * FACTOR
        a = rnd.randint(*alpha_range)
        col = rnd.choice(palette)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*col, a))
    return layer.filter(ImageFilter.GaussianBlur(radius=2 * FACTOR))


def _daemon_mark(size, glow=True, mood="content"):
    """Original flat-geometric daemon mark — horns + glowing eyes. A brand
    mark, not a character illustration (no IP reproduced).

    mood:
      "blazing" — big win (pct >= 100): eyes wide open, hot bright glow,
                  small flame flickers above the horns.
      "content" — normal gain (0 <= pct < 100): the original calm slit-eyed
                  mark.
      "rough"   — down (pct < 0): eyes drooping, dim cool-toned glow, a
                  single crack/tear under one eye.
    """
    pad = int(size * 0.3)
    canvas_sz = size + pad * 2
    im = Image.new("RGBA", (canvas_sz, canvas_sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = canvas_sz / 2, canvas_sz / 2 + size * 0.04

    glow_color = GOLD_BRIGHT if mood == "blazing" else (ASH if mood == "rough" else EMBER)
    glow_alpha = 140 if mood == "blazing" else (70 if mood == "rough" else 100)
    glow_scale = 1.25 if mood == "blazing" else (0.75 if mood == "rough" else 1.0)

    if glow:
        glow_layer = Image.new("RGBA", (canvas_sz, canvas_sz), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gr = size * 0.40 * glow_scale
        gd.ellipse([cx - gr, cy - gr * 0.7, cx + gr, cy + gr * 1.1], fill=(*glow_color, glow_alpha))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=size * 0.10))
        im = Image.alpha_composite(im, glow_layer)
        d = ImageDraw.Draw(im)

    horn_w = size * 0.16
    for side in (-1, 1):
        pts = []
        steps = 14
        for i in range(steps + 1):
            t = i / steps
            hx = cx + side * (size * 0.16 + t * size * 0.30 - (t ** 2) * size * 0.06)
            hy = cy - size * 0.10 - t * size * 0.46 + (t ** 2) * size * 0.10
            pts.append((hx, hy))
        outline = []
        for i, (hx, hy) in enumerate(pts):
            w_ = horn_w * (1 - i / len(pts)) ** 1.3 + size * 0.02
            outline.append((hx, hy - w_ / 2))
        for hx, hy in reversed(pts):
            w_ = horn_w * (1 - pts.index((hx, hy)) / len(pts)) ** 1.3 + size * 0.02
            outline.append((hx, hy + w_ / 2))
        d.polygon(outline, fill=GOLD)

        # blazing-only: a small flame flicker above each horn tip
        if mood == "blazing":
            tip = pts[-1]
            flick = [
                (tip[0], tip[1] - size * 0.16),
                (tip[0] - size * 0.05, tip[1] - size * 0.04),
                (tip[0] + size * 0.05, tip[1] - size * 0.04),
            ]
            d.polygon(flick, fill=GOLD_BRIGHT)

    # eye geometry varies by mood: content = gentle inward tilt (calm),
    # blazing = wide open with an upward fierce flick, rough = narrow with
    # drooping outer corners (tired/sad)
    if mood == "blazing":
        eye_w, eye_h = size * 0.24, size * 0.075
    elif mood == "rough":
        eye_w, eye_h = size * 0.20, size * 0.04
    else:
        eye_w, eye_h = size * 0.22, size * 0.055

    eye_color = (255, 246, 225) if mood == "blazing" else (GOLD_BRIGHT if mood == "content" else (170, 165, 178))

    for side in (-1, 1):
        ex = cx + side * size * 0.18
        ey = cy - size * 0.02
        glow_layer = Image.new("RGBA", (canvas_sz, canvas_sz), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.ellipse([ex - eye_w * 0.75, ey - eye_h * 1.6, ex + eye_w * 0.75, ey + eye_h * 1.6],
                   fill=(*glow_color, min(255, glow_alpha + 80)))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=size * 0.035))
        im = Image.alpha_composite(im, glow_layer)
        d = ImageDraw.Draw(im)

        if mood == "blazing":
            tilt = side * size * 0.035   # outer corners flick UP — fierce
        elif mood == "rough":
            tilt = -side * size * 0.045  # outer corners droop DOWN — tired
        else:
            tilt = -side * size * 0.025  # gentle inward tilt — calm

        d.polygon([
            (ex - eye_w / 2, ey + tilt), (ex - eye_w * 0.1, ey - eye_h / 2),
            (ex + eye_w / 2, ey - tilt), (ex + eye_w * 0.1, ey + eye_h / 2),
        ], fill=eye_color)

        # rough-only: a single thin crack/tear under the inner eye
        if mood == "rough" and side == 1:
            d.line([ex - eye_w * 0.1, ey + eye_h, ex - eye_w * 0.18, ey + size * 0.10],
                   fill=(*ASH, 220), width=max(1, int(size * 0.012)))

    return im


def _money(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    if n >= 1_000_000_000:
        return f"${n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"${n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"${n/1_000:.1f}K"
    return f"${n:.2f}"


def _pnl_label(pct: float) -> str:
    if pct >= 500: return "GIGACHAD MODE"
    if pct >= 200: return "WAGMI SER"
    if pct >= 100: return "2X ACHIEVED"
    if pct >= 50: return "NICE CALL"
    if pct >= 10: return "IN PROFIT"
    if pct >= 0: return "HOLDING STRONG"
    if pct >= -30: return "SHAKING A BIT"
    if pct >= -60: return "REKT SER"
    return "NGMI"


def _time_ago(iso_time: str) -> str:
    if not iso_time:
        return "—"
    try:
        then = datetime.fromisoformat(iso_time).replace(tzinfo=timezone.utc)
        secs = (datetime.now(timezone.utc) - then).total_seconds()
    except ValueError:
        return "—"
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        m, s = divmod(int(secs), 60)
        return f"{m}m {s}s ago" if m < 5 else f"{m}m ago"
    if secs < 86400:
        return f"{int(secs/3600)}h ago"
    return f"{int(secs/86400)}d ago"


def _price_to_mcap(price: float, current_price: float, current_mcap: float) -> float:
    """Derives an mcap figure for an arbitrary price using the live mcap/price
    ratio — we only persist price history, not historical mcap, but mcap
    scales linearly with price for a fixed supply, so this is exact as long
    as supply hasn't changed (true for the vast majority of tokens
    post-launch)."""
    if not current_price or not current_mcap:
        return 0.0
    return price * (current_mcap / current_price)


def _mood_for_pct(pct: float) -> str:
    if pct >= 100:
        return "blazing"   # "gaining a lot"
    if pct >= 0:
        return "content"   # "gaining"
    return "rough"          # "down"


def generate_pnl_image(
    username: str,
    token_name: str,
    symbol: str,
    entry_price: float,
    current_price: float,
    call_time: str,
    total_calls: int,
    chain: str = "SOLANA",
    pair: dict | None = None,
    peak_price: float | None = None,
) -> bytes:
    pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0
    pnl_color = FOREST if pct >= 0 else RED_MUTED
    mood = _mood_for_pct(pct)

    current_mcap = float((pair or {}).get("marketCap") or (pair or {}).get("fdv") or 0)
    call_mc = _price_to_mcap(entry_price, current_price, current_mcap)
    peak_for_reached = max(peak_price or 0, entry_price, current_price)
    reached_mc = _price_to_mcap(peak_for_reached, current_price, current_mcap)

    canvas = Image.new("RGB", (W * FACTOR, H * FACTOR), NAVY_DARK)
    bg = _gradient_bg(W * FACTOR, H * FACTOR, NAVY_MID, PLUM)
    canvas.paste(bg, (0, 0))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), _ember_field(W * FACTOR, H * FACTOR, mood=mood)).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    PAD = 48 * FACTOR

    # brand bar
    mark_small = _daemon_mark(34 * FACTOR, glow=False, mood=mood)
    canvas.paste(mark_small, (int(PAD - 34 * FACTOR * 0.3), 30 * FACTOR), mark_small)
    draw.text((PAD + 34 * FACTOR + 14 * FACTOR, 30 * FACTOR), "DAEMONBOT", font=F_BRAND, fill=CREAM)
    draw.text((PAD + 34 * FACTOR + 14 * FACTOR, 30 * FACTOR + 24 * FACTOR), "PNL CARD", font=F_SUB, fill=MUTED)

    chain_txt = chain.upper()
    chain_w = _tw(draw, chain_txt, F_CHAIN) + 28 * FACTOR
    draw.rounded_rectangle([W * FACTOR - PAD - chain_w, 32 * FACTOR, W * FACTOR - PAD, 32 * FACTOR + 34 * FACTOR],
                            12 * FACTOR, outline=GOLD, width=max(2, FACTOR))
    draw.text((W * FACTOR - PAD - chain_w + 14 * FACTOR, 39 * FACTOR), chain_txt, font=F_CHAIN, fill=GOLD)

    draw.line([PAD, 100 * FACTOR, W * FACTOR - PAD, 100 * FACTOR], fill=BORDER, width=max(1, FACTOR))

    # mascot
    mark_big = _daemon_mark(220 * FACTOR, glow=True, mood=mood)
    mx, my = int(PAD + 10 * FACTOR), int(260 * FACTOR)
    canvas.paste(mark_big, (mx - int(220 * FACTOR * 0.3), my - int(220 * FACTOR * 0.3)), mark_big)

    right_x = W * FACTOR - PAD

    name_disp = token_name if len(token_name) <= 22 else token_name[:21] + "…"
    name_w = _tw(draw, name_disp, F_CALLPRICE)
    draw.text((right_x - name_w, 112 * FACTOR), name_disp, font=F_CALLPRICE, fill=MUTED)

    ticker_txt = f"${symbol.upper()}"
    tkw = _tw(draw, ticker_txt, F_TICKER)
    draw.text((right_x - tkw, 134 * FACTOR), ticker_txt, font=F_TICKER, fill=CREAM)
    cp_txt = f"called at {_money(call_mc)}" if call_mc else "call price unavailable"
    cpw = _tw(draw, cp_txt, F_CALLPRICE)
    draw.text((right_x - cpw, 134 * FACTOR + 46 * FACTOR), cp_txt, font=F_CALLPRICE, fill=MUTED)

    pnl_txt = f"{'+' if pct >= 0 else ''}{pct:.0f}%"
    pw_ = _tw(draw, pnl_txt, F_PNL)
    draw.text((right_x - pw_, 224 * FACTOR), pnl_txt, font=F_PNL, fill=pnl_color)
    lbl_txt = _pnl_label(pct)
    lblw = _tw(draw, lbl_txt, F_PNLLABEL)
    draw.text((right_x - lblw, 224 * FACTOR + 108 * FACTOR), lbl_txt, font=F_PNLLABEL, fill=pnl_color)

    caller_txt = f"@{username}"
    ctw = _tw(draw, caller_txt, F_CALLER)
    draw.text((right_x - ctw, 365 * FACTOR), caller_txt, font=F_CALLER, fill=GOLD)
    time_txt = _time_ago(call_time)
    ttw = _tw(draw, time_txt, F_TIME)
    draw.text((right_x - ttw, 398 * FACTOR), time_txt, font=F_TIME, fill=MUTED)

    reached_txt = f"Reached {_money(reached_mc)}" if reached_mc else "Reached —"
    rtw = _tw(draw, reached_txt, F_REACHED)
    draw.text((right_x - rtw, 432 * FACTOR), reached_txt, font=F_REACHED, fill=GOLD_BRIGHT)

    y_div = 540 * FACTOR
    draw.line([PAD, y_div, W * FACTOR - PAD, y_div], fill=BORDER, width=max(1, FACTOR))

    foot = f"DAEMONBOT  ·  {total_calls} calls by this caller  ·  NFA DYOR"
    draw.text((PAD, y_div + 24 * FACTOR), foot, font=F_FOOTER, fill=GOLD)
    cta = "Share on X"
    ctaw = _tw(draw, cta, F_CTA)
    draw.text((W * FACTOR - PAD - ctaw, y_div + 22 * FACTOR), cta, font=F_CTA, fill=CREAM)

    out = canvas.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
