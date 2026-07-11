"""
services/scan_card.py — Renders the /scan and /z image card.

Layout (top to bottom): banner -> name/ticker -> stats grid -> socials+lore
-> security section -> quick-links -> quick-buy row -> (optional) caller info
-> footer. Same visual language as the original mockup (navy/gold/plum/
forest-green, hand-drawn flat icons, Poppins).

This module only draws. All data gathering / API calls live in
services/scan_data.py — generate_scan_card() takes one plain dict so it can
be unit-tested with fixtures, no network needed.
"""

import io
import random

from PIL import Image, ImageDraw, ImageFont

FACTOR = 3
W = 860

NAVY_DARK = (13, 22, 38)
NAVY_MID = (19, 32, 56)
NAVY_PANEL2 = (17, 28, 49)   # slightly lighter than NAVY_DARK — alternating section bg
PLUM = (72, 43, 71)
GOLD = (214, 178, 110)
GOLD_BRIGHT = (232, 200, 140)
FOREST = (88, 150, 110)
RED_MUTED = (176, 90, 90)     # used sparingly — "sold" / negative, not pure red
CREAM = (238, 234, 224)
MUTED = (138, 147, 168)
BORDER = (38, 50, 74)

FONT_DIR = "/usr/share/fonts/truetype/google-fonts/"


def _f(name, size):
    return ImageFont.truetype(FONT_DIR + name, size * FACTOR)


F_WORDMARK = _f("Poppins-Bold.ttf", 50)
F_TAG = _f("Poppins-Medium.ttf", 19)
F_NAME = _f("Poppins-Bold.ttf", 32)
F_TICKER = _f("Poppins-Bold.ttf", 32)
F_RANK = _f("Poppins-Bold.ttf", 16)
F_SECTION = _f("Poppins-Bold.ttf", 19)
F_LABEL = _f("Poppins-Medium.ttf", 16)
F_VALUE = _f("Poppins-Bold.ttf", 26)
F_VALUE_SM = _f("Poppins-Bold.ttf", 20)
F_SMALL = _f("Poppins-Regular.ttf", 16)
F_PILL = _f("Poppins-Bold.ttf", 15)
F_LORE = _f("Poppins-Regular.ttf", 16)
F_LINK = _f("Poppins-Bold.ttf", 16)
F_FOOTER = _f("Poppins-Regular.ttf", 14)

PAD = 50
SPAD = PAD * FACTOR


# ── shared low-level helpers (same approach as the original mockup) ────────

def _tw(draw, txt, fnt):
    return draw.textlength(txt, font=fnt)


def _rrect(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def _icon_canvas(size):
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _paste_icon(canvas, icon_img, x, y, size):
    resized = icon_img.resize((size, size), Image.LANCZOS)
    canvas.paste(resized, (x, y), resized)


def icon_coin(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    m = size * 0.08
    d.ellipse([m, m, size - m, size - m], outline=color, width=max(2, int(size * 0.07)))
    d.ellipse([size * 0.32, size * 0.32, size * 0.68, size * 0.68], outline=color, width=max(2, int(size * 0.05)))
    return im


def icon_calendar(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    top = size * 0.22
    d.rounded_rectangle([size * 0.12, top, size * 0.88, size * 0.88], radius=size * 0.08,
                         outline=color, width=max(2, int(size * 0.07)))
    d.line([size * 0.12, top + size * 0.16, size * 0.88, top + size * 0.16], fill=color, width=max(2, int(size * 0.06)))
    d.line([size * 0.30, size * 0.10, size * 0.30, top + size * 0.10], fill=color, width=max(2, int(size * 0.07)))
    d.line([size * 0.70, size * 0.10, size * 0.70, top + size * 0.10], fill=color, width=max(2, int(size * 0.07)))
    return im


def icon_money(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([size * 0.08, size * 0.26, size * 0.92, size * 0.74], radius=size * 0.1,
                         outline=color, width=max(2, int(size * 0.07)))
    d.ellipse([size * 0.38, size * 0.36, size * 0.62, size * 0.64], outline=color, width=max(2, int(size * 0.06)))
    return im


def icon_droplet(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    d.ellipse([size * 0.18, size * 0.38, size * 0.82, size * 0.92], fill=color)
    d.polygon([(size * 0.5, size * 0.06), (size * 0.78, size * 0.5), (size * 0.22, size * 0.5)], fill=color)
    return im


def icon_bars(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    base = size * 0.86
    bw = size * 0.16
    for i, h in enumerate([0.34, 0.56, 0.78]):
        x0 = size * 0.14 + i * (bw + size * 0.1)
        d.rounded_rectangle([x0, base - size * h, x0 + bw, base], radius=bw * 0.3, fill=color)
    return im


def icon_supply(size, color):
    """Stacked-coins glyph for circulating/total supply."""
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    for dy in [0.62, 0.46, 0.30]:
        d.ellipse([size * 0.2, size * dy, size * 0.8, size * dy + size * 0.22],
                  outline=color, width=max(2, int(size * 0.06)))
    return im


def icon_peak(size, color):
    """Mountain-peak glyph for ATH."""
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    d.polygon([(size * 0.5, size * 0.12), (size * 0.88, size * 0.82), (size * 0.12, size * 0.82)],
              outline=color, width=max(2, int(size * 0.07)))
    d.polygon([(size * 0.5, size * 0.12), (size * 0.62, size * 0.34), (size * 0.42, size * 0.34)], fill=color)
    return im


def icon_shield(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    pts = [
        (size * 0.5, size * 0.08), (size * 0.86, size * 0.22), (size * 0.86, size * 0.52),
        (size * 0.5, size * 0.92), (size * 0.14, size * 0.52), (size * 0.14, size * 0.22),
    ]
    d.polygon(pts, outline=color, width=max(2, int(size * 0.06)))
    d.line([size * 0.34, size * 0.5, size * 0.46, size * 0.62], fill=color, width=max(2, int(size * 0.08)))
    d.line([size * 0.46, size * 0.62, size * 0.68, size * 0.36], fill=color, width=max(2, int(size * 0.08)))
    return im


def icon_users(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    for cx in (size * 0.36, size * 0.64):
        d.ellipse([cx - size * 0.14, size * 0.16, cx + size * 0.14, size * 0.44], outline=color, width=max(2, int(size * 0.06)))
    d.arc([size * 0.08, size * 0.5, size * 0.62, size * 0.95], 200, 340, fill=color, width=max(2, int(size * 0.06)))
    d.arc([size * 0.38, size * 0.5, size * 0.92, size * 0.95], 200, 340, fill=color, width=max(2, int(size * 0.06)))
    return im


def icon_lock(size, color, locked=True):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    body = [size * 0.22, size * 0.46, size * 0.78, size * 0.88]
    d.rounded_rectangle(body, radius=size * 0.06, outline=color, width=max(2, int(size * 0.07)))
    if locked:
        d.arc([size * 0.3, size * 0.16, size * 0.7, size * 0.56], 180, 360, fill=color, width=max(2, int(size * 0.07)))
    else:
        d.arc([size * 0.22, size * 0.12, size * 0.62, size * 0.52], 180, 360, fill=color, width=max(2, int(size * 0.07)))
    return im


def icon_link(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([size * 0.10, size * 0.36, size * 0.56, size * 0.64], radius=size * 0.12, outline=color, width=max(2, int(size * 0.08)))
    d.rounded_rectangle([size * 0.44, size * 0.36, size * 0.90, size * 0.64], radius=size * 0.12, outline=color, width=max(2, int(size * 0.08)))
    return im


def icon_bolt(size, color):
    im = _icon_canvas(size)
    d = ImageDraw.Draw(im)
    d.polygon([(size * 0.58, size * 0.06), (size * 0.26, size * 0.56), (size * 0.46, size * 0.56),
               (size * 0.40, size * 0.94), (size * 0.76, size * 0.42), (size * 0.54, size * 0.42)],
              fill=color)
    return im


def _banner_placeholder(w, h):
    """Gradient + stars placeholder, used only when we have no real banner
    image to paste (pump.fun/DexScreener gave us nothing). Built from a tiny
    diagonal-gradient base image upscaled with LANCZOS — avoids pulling in
    numpy just for a two-colour gradient."""
    base_n = 24
    base = Image.new("RGB", (base_n, base_n))
    for by in range(base_n):
        for bx in range(base_n):
            t = (bx / (base_n - 1)) * 0.55 + (by / (base_n - 1)) * 0.45
            base.putpixel((bx, by), tuple(
                int(NAVY_MID[i] + (PLUM[i] - NAVY_MID[i]) * t) for i in range(3)
            ))
    img = base.resize((w, h), Image.LANCZOS).convert("RGBA")

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    rnd = random.Random(7)
    for _ in range(60):
        sx, sy = rnd.randint(0, w), rnd.randint(0, int(h * 0.7))
        r = rnd.choice([1, 1, 2, 2, 3]) * FACTOR
        a = rnd.randint(70, 200)
        od.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(*GOLD_BRIGHT, a))
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")


def _fit_image_cover(img, w, h):
    """Resize+crop an arbitrary banner/logo image to exactly fill w x h."""
    src_ratio = img.width / img.height
    tgt_ratio = w / h
    if src_ratio > tgt_ratio:
        new_h = h
        new_w = int(new_h * src_ratio)
    else:
        new_w = w
        new_h = int(new_w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _wrap_lore(draw, text, fnt, max_width, max_lines=3):
    if not text:
        return []
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if _tw(draw, trial, fnt) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    # Ellipsis if we truncated more words than fit
    consumed = sum(len(l.split()) for l in lines)
    if consumed < len(words) and lines:
        last = lines[-1]
        while _tw(draw, last + "…", fnt) > max_width and len(last) > 1:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _pct_color(pct):
    if pct is None:
        return MUTED
    return FOREST if pct >= 0 else RED_MUTED


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


def generate_scan_card(data: dict) -> bytes:
    """data is a plain dict assembled by services/scan_data.py — see that
    module's docstring for the exact keys expected. Every key is read with
    .get() and a sane default so a partially-filled dict (degraded 3rd-party
    API) still renders a usable card instead of crashing."""

    BANNER_H = 340
    rows = []  # (kind, payload) — sized + drawn in a second pass once we
               # know the total canvas height (variable due to lore wrapping)

    # We draw in one pass using a scratch Draw bound to a generously-tall
    # temp canvas, track the cursor, then crop to the real height at the end.
    MAX_H = 2400
    canvas = Image.new("RGB", (W * FACTOR, MAX_H * FACTOR), NAVY_DARK)
    draw = ImageDraw.Draw(canvas)
    y = 0  # final-px cursor (not supersampled)

    def Y():
        return y * FACTOR

    # ── Banner ───────────────────────────────────────────────────────────
    banner_bytes = data.get("banner_image_bytes")
    banner_img = None
    if banner_bytes:
        try:
            banner_img = Image.open(io.BytesIO(banner_bytes)).convert("RGB")
            banner_img = _fit_image_cover(banner_img, W * FACTOR, BANNER_H * FACTOR)
        except Exception:
            banner_img = None
    if banner_img is None:
        banner_img = _banner_placeholder(W * FACTOR, BANNER_H * FACTOR)
    canvas.paste(banner_img, (0, 0))

    # Darken bottom third of banner so name/ticker overlay stays legible
    fade = Image.new("RGBA", (W * FACTOR, BANNER_H * FACTOR), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    fstart = int(BANNER_H * 0.55)
    for fy in range(fstart, BANNER_H):
        a = int((fy - fstart) / (BANNER_H - fstart) * 200)
        fd.line([(0, fy * FACTOR), (W * FACTOR, fy * FACTOR)], fill=(*NAVY_DARK, a), width=FACTOR)
    canvas.paste(Image.alpha_composite(canvas.crop((0, 0, W * FACTOR, BANNER_H * FACTOR)).convert("RGBA"), fade).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(canvas)

    # Trending-rank badge, top-right of banner
    rank = data.get("trending_rank")
    if rank:
        rank_txt = f"#{rank} TRENDING"
        rb_w = _tw(draw, rank_txt, F_RANK) + 28 * FACTOR
        _rrect(draw, [W * FACTOR - SPAD - rb_w, 20 * FACTOR, W * FACTOR - SPAD, 20 * FACTOR + 40 * FACTOR],
               14 * FACTOR, fill=(*NAVY_DARK, 220))
        draw.text((W * FACTOR - SPAD - rb_w + 14 * FACTOR, 28 * FACTOR), rank_txt, font=F_RANK, fill=GOLD)

    # Name + ticker overlay near banner bottom
    name = data.get("name", "Unknown")
    symbol = data.get("symbol", "?")
    name_disp = name if len(name) <= 30 else name[:29] + "…"
    nb_w = _tw(draw, name_disp.upper(), F_WORDMARK)
    draw.text(((W * FACTOR - nb_w) / 2, BANNER_H * FACTOR * 0.68), name_disp.upper(), font=F_WORDMARK, fill=(252, 248, 240))
    tag = f"${symbol.upper()}"
    tb_w = _tw(draw, tag, F_TAG)
    draw.text(((W * FACTOR - tb_w) / 2, BANNER_H * FACTOR * 0.68 + 64 * FACTOR), tag, font=F_TAG, fill=GOLD_BRIGHT)

    draw.rectangle([0, BANNER_H * FACTOR - 3 * FACTOR, W * FACTOR, BANNER_H * FACTOR], fill=GOLD)
    y = BANNER_H

    def panel_bg(y0, y1, color=NAVY_DARK):
        draw.rectangle([0, y0 * FACTOR, W * FACTOR, y1 * FACTOR], fill=color)

    def divider(yy):
        draw.line([SPAD, yy * FACTOR, W * FACTOR - SPAD, yy * FACTOR], fill=BORDER, width=max(1, FACTOR))

    def section_header(label, yy):
        draw.text((SPAD, yy * FACTOR), label, font=F_SECTION, fill=GOLD)
        return yy + 38

    def icon_at(name_, x, yy, size_px, color=GOLD):
        fn = {"coin": icon_coin, "calendar": icon_calendar, "money": icon_money,
              "droplet": icon_droplet, "bars": icon_bars, "supply": icon_supply,
              "peak": icon_peak, "shield": icon_shield, "users": icon_users,
              "lock": icon_lock, "link": icon_link, "bolt": icon_bolt}[name_]
        _paste_icon(canvas, fn(size_px * FACTOR, color), int(x), int(yy * FACTOR), size_px * FACTOR)

    # ── Background for the whole stats/security body ───────────────────
    panel_bg(BANNER_H, MAX_H)
    draw = ImageDraw.Draw(canvas)
    icon_sz = 28

    # ── Name/ticker row + risk badge ────────────────────────────────────
    y += 36
    icon_at("coin", SPAD, y - 2, icon_sz)
    tx = PAD + icon_sz + 16
    draw.text((tx * FACTOR, Y()), name_disp, font=F_NAME, fill=CREAM)
    nm_w = _tw(draw, name_disp, F_NAME) / FACTOR
    sep = "   ·   "
    draw.text(((tx + nm_w) * FACTOR, Y()), sep, font=F_NAME, fill=MUTED)
    sep_w = _tw(draw, sep, F_NAME) / FACTOR
    draw.text(((tx + nm_w + sep_w) * FACTOR, Y()), f"${symbol.upper()}", font=F_TICKER, fill=GOLD)

    risk_score = data.get("risk_score")
    if risk_score is not None:
        rs_txt = f"RISK {risk_score}/100"
        rs_w = _tw(draw, rs_txt, F_PILL) + 24 * FACTOR
        rs_col = FOREST if risk_score < 35 else (GOLD if risk_score < 65 else RED_MUTED)
        rx = W * FACTOR - SPAD - rs_w
        _rrect(draw, [rx, Y() + 2 * FACTOR, rx + rs_w, Y() + 36 * FACTOR], 12 * FACTOR, outline=rs_col, width=max(2, FACTOR))
        draw.text((rx + 12 * FACTOR, Y() + 8 * FACTOR), rs_txt, font=F_PILL, fill=rs_col)

    y += 56
    divider(y)
    y += 26

    # ── Stats grid (2 columns) ───────────────────────────────────────────
    col_w = (W - PAD * 2 - 30) / 2
    col_x = [PAD, PAD + col_w + 30]

    def stat_cell(col, label, value, icon_name, value_color=CREAM, sub=""):
        x = col_x[col]
        icon_at(icon_name, x * FACTOR, y, 24)
        lx = x + 24 + 14
        draw.text((lx * FACTOR, Y()), label, font=F_LABEL, fill=MUTED)
        draw.text((lx * FACTOR, (y + 22) * FACTOR), value, font=F_VALUE_SM, fill=value_color)
        if sub:
            vw = _tw(draw, value, F_VALUE_SM) / FACTOR
            draw.text(((lx + vw + 10) * FACTOR, (y + 27) * FACTOR), sub, font=F_SMALL, fill=MUTED)

    price = data.get("price_usd", 0) or 0
    price_str = f"${price:.8f}" if price and price < 0.01 else f"${price:.6f}" if price else "—"
    chg = data.get("price_change_pct")
    chg_str = f"({'+' if (chg or 0) >= 0 else ''}{chg:.1f}%)" if chg is not None else ""
    stat_cell(0, "PRICE", price_str, "coin", _pct_color(chg) if chg is not None else CREAM, chg_str)
    stat_cell(1, "MARKET CAP", _money(data.get("mc")), "money", GOLD)
    y += 60

    stat_cell(0, "VOLUME (1H)", _money(data.get("vol_1h")), "bars")
    stat_cell(1, "LIQUIDITY", _money(data.get("liq")), "droplet")
    y += 60

    supply_c = data.get("supply_circ")
    supply_t = data.get("supply_total")
    supply_str = "—"
    if supply_c is not None and supply_t is not None:
        supply_str = f"{supply_c/1e6:.1f}M/{supply_t/1e6:.1f}M" if supply_t >= 1e6 else f"{supply_c:,.0f}/{supply_t:,.0f}"
    stat_cell(0, "SUPPLY", supply_str, "supply")
    stat_cell(1, "AGE", data.get("age_label", "—"), "calendar")
    y += 64

    divider(y)
    y += 22

    # ── 1H buys/sells + ATH highlight row ───────────────────────────────
    buys, sells = data.get("buys_1h"), data.get("sells_1h")
    draw.text((SPAD, Y()), "1H ACTIVITY", font=F_LABEL, fill=MUTED)
    if buys is not None and sells is not None:
        dot_d = 14 * FACTOR   # dot diameter
        gap = 8 * FACTOR
        buys_txt, sells_txt = f"{buys:,}", f"{sells:,}"
        buys_w = _tw(draw, buys_txt, F_VALUE_SM)
        sells_w = _tw(draw, sells_txt, F_VALUE_SM)
        block_w = dot_d + gap + buys_w + 28 * FACTOR + dot_d + gap + sells_w
        bx = W * FACTOR - SPAD - block_w
        by = Y() + 6 * FACTOR
        draw.ellipse([bx, by, bx + dot_d, by + dot_d], fill=FOREST)
        draw.text((bx + dot_d + gap, Y() - 4 * FACTOR), buys_txt, font=F_VALUE_SM, fill=CREAM)
        sx = bx + dot_d + gap + buys_w + 28 * FACTOR
        draw.ellipse([sx, by, sx + dot_d, by + dot_d], fill=RED_MUTED)
        draw.text((sx + dot_d + gap, Y() - 4 * FACTOR), sells_txt, font=F_VALUE_SM, fill=CREAM)
    else:
        draw.text((W * FACTOR - SPAD - _tw(draw, "—", F_VALUE_SM), Y() - 4 * FACTOR), "—", font=F_VALUE_SM, fill=MUTED)
    y += 38

    ath_mc = data.get("ath_mc")
    ath_pct = data.get("ath_pct_off")
    ath_time = data.get("ath_time_label", "")
    icon_at("peak", SPAD, y - 2, 24)
    draw.text(((PAD + 24 + 14) * FACTOR, Y()), "ATH", font=F_LABEL, fill=MUTED)
    if ath_mc:
        ath_str = f"{_money(ath_mc)}"
        if ath_pct is not None and ath_time:
            sub = f"({ath_pct:+.0f}% / {ath_time})"
        elif ath_pct is not None:
            sub = f"({ath_pct:+.0f}%)"
        else:
            sub = ""
        draw.text(((PAD + 24 + 14 + 50) * FACTOR, Y()), ath_str, font=F_VALUE_SM, fill=CREAM)
        if sub:
            aw = _tw(draw, ath_str, F_VALUE_SM) / FACTOR
            draw.text(((PAD + 24 + 14 + 50 + aw + 10) * FACTOR, Y() + 4 * FACTOR), sub, font=F_SMALL, fill=MUTED)
    else:
        draw.text(((PAD + 24 + 14 + 50) * FACTOR, Y()), "—", font=F_VALUE_SM, fill=MUTED)
    y += 50

    divider(y)
    y += 16
    y = section_header("SOCIALS", y)

    age_lbl = data.get("socials_age_label", "—")
    twitter_url = data.get("twitter_url")
    soc_txt = f"Account age: {age_lbl}"
    draw.text((SPAD, Y()), soc_txt, font=F_SMALL, fill=MUTED)
    if twitter_url:
        x_txt = "X (verified)"
        xw = _tw(draw, x_txt, F_SMALL)
        draw.text((W * FACTOR - SPAD - xw, Y()), x_txt, font=F_SMALL, fill=GOLD)
    y += 30

    lore = data.get("lore", "")
    if lore:
        lines = _wrap_lore(draw, lore, F_LORE, (W - PAD * 2) * FACTOR, max_lines=3)
        for line in lines:
            draw.text((SPAD, Y()), line, font=F_LORE, fill=CREAM)
            y += 26
        y += 6
    else:
        draw.text((SPAD, Y()), "No description provided.", font=F_LORE, fill=MUTED)
        y += 30

    y += 12
    divider(y)
    y += 16
    y = section_header("SECURITY", y)

    sec = data
    if not data.get("security_available", True):
        draw.text((SPAD, Y()), "Couldn't reach RugCheck for this token — security data unavailable.", font=F_SMALL, fill=MUTED)
        y += 36
    else:
        fresh_1d, fresh_7d = data.get("fresh_1d"), data.get("fresh_7d")
        f1 = f"{fresh_1d:.1f}%" if fresh_1d is not None else "—"
        f7 = f"{fresh_7d:.1f}%" if fresh_7d is not None else "—"
        icon_at("users", SPAD, y - 2, 24)
        draw.text(((PAD + 38) * FACTOR, Y()), "FRESH WALLETS", font=F_LABEL, fill=MUTED)
        draw.text(((PAD + 38) * FACTOR, (y + 22) * FACTOR), f"{f1} (1D)   {f7} (7D)", font=F_VALUE_SM, fill=CREAM)
        y += 58

        top10 = data.get("top10_pct")
        total_h = data.get("total_holders")
        t10_str = f"{top10:.1f}%" if top10 is not None else "—"
        th_str = f"{total_h:,}" if total_h is not None else "—"
        icon_at("shield", SPAD, y - 2, 24)
        draw.text(((PAD + 38) * FACTOR, Y()), "TOP 10 HOLDERS", font=F_LABEL, fill=MUTED)
        draw.text(((PAD + 38) * FACTOR, (y + 22) * FACTOR), t10_str, font=F_VALUE_SM,
                   fill=(RED_MUTED if (top10 or 0) > 50 else CREAM))
        sub_x = (PAD + 38) * FACTOR + _tw(draw, t10_str, F_VALUE_SM) + 12 * FACTOR
        draw.text((sub_x, (y + 27) * FACTOR), f"({th_str} holders total)", font=F_SMALL, fill=MUTED)
        y += 58

        breakdown = data.get("top_breakdown") or []
        if breakdown:
            bd_str = "  |  ".join(f"{b:.1f}%" for b in breakdown)
            draw.text((SPAD, Y()), "Top 5 individually:", font=F_LABEL, fill=MUTED)
            draw.text((SPAD, (y + 22) * FACTOR), bd_str, font=F_SMALL, fill=CREAM)
            y += 52

        dev_sold = data.get("dev_sold", "unknown")
        dev_map = {"sold": ("DEV SOLD", RED_MUTED), "holding": ("DEV HOLDING", FOREST), "unknown": ("DEV STATUS UNKNOWN", MUTED)}
        dev_lbl, dev_col = dev_map.get(dev_sold, dev_map["unknown"])
        dpw = _tw(draw, dev_lbl, F_PILL) + 24 * FACTOR
        _rrect(draw, [SPAD, Y(), SPAD + dpw, Y() + 32 * FACTOR], 12 * FACTOR, fill=dev_col)
        text_col = (20, 32, 24) if dev_col == FOREST else ((40, 20, 20) if dev_col == RED_MUTED else (30, 34, 44))
        draw.text((SPAD + 12 * FACTOR, Y() + 5 * FACTOR), dev_lbl, font=F_PILL, fill=text_col)

        dex_paid = data.get("dex_paid")
        paid_lbl = "DEX PAID" if dex_paid else ("NOT PAID" if dex_paid is False else "DEX PAID UNKNOWN")
        paid_col = FOREST if dex_paid else (RED_MUTED if dex_paid is False else MUTED)
        ppw = _tw(draw, paid_lbl, F_PILL) + 24 * FACTOR
        px = SPAD + dpw + 14 * FACTOR
        _rrect(draw, [px, Y(), px + ppw, Y() + 32 * FACTOR], 12 * FACTOR, outline=paid_col, width=max(2, FACTOR))
        draw.text((px + 12 * FACTOR, Y() + 5 * FACTOR), paid_lbl, font=F_PILL, fill=paid_col)
        y += 46

        mint_r = data.get("mint_renounced")
        freeze_r = data.get("freeze_renounced")
        icon_at("lock", SPAD, y - 2, 22, GOLD)
        mint_txt = f"Mint: {'renounced' if mint_r else 'ACTIVE' if mint_r is False else 'unknown'}"
        draw.text(((PAD + 34) * FACTOR, Y()), mint_txt, font=F_SMALL,
                   fill=(FOREST if mint_r else (RED_MUTED if mint_r is False else MUTED)))
        mw = _tw(draw, mint_txt, F_SMALL) / FACTOR
        freeze_txt = f"Freeze: {'renounced' if freeze_r else 'ACTIVE' if freeze_r is False else 'unknown'}"
        draw.text(((PAD + 34 + mw + 30) * FACTOR, Y()), freeze_txt, font=F_SMALL,
                   fill=(FOREST if freeze_r else (RED_MUTED if freeze_r is False else MUTED)))
        y += 38

    y += 10
    divider(y)
    y += 22

    # ── Optional caller info bar ─────────────────────────────────────────
    caller = data.get("caller_username")
    if caller:
        bar_h = 56
        _rrect(draw, [SPAD, Y(), W * FACTOR - SPAD, (y + bar_h) * FACTOR], 14 * FACTOR, fill=NAVY_MID, outline=BORDER, width=FACTOR)
        c_mc = data.get("caller_mc")
        c_pct = data.get("caller_pct_change")
        c_time = data.get("caller_time_label", "")
        dot_d = 16 * FACTOR
        dot_x, dot_y = (PAD + 16) * FACTOR, (y + 18) * FACTOR
        draw.ellipse([dot_x, dot_y, dot_x + dot_d, dot_y + dot_d], fill=GOLD)
        ctxt = caller
        draw.text((dot_x + dot_d + 12 * FACTOR, (y + 14) * FACTOR), ctxt, font=F_VALUE_SM, fill=GOLD)
        cw = (dot_d + 12 * FACTOR + _tw(draw, ctxt, F_VALUE_SM)) / FACTOR
        detail = f"@ {_money(c_mc)}" if c_mc else ""
        if c_pct is not None:
            detail += f"  [{c_pct:+.0f}%]"
        if c_time:
            detail += f"  ({c_time})"
        draw.text(((PAD + 16 + cw + 16) * FACTOR, (y + 18) * FACTOR), detail, font=F_SMALL, fill=CREAM)
        y += bar_h + 18

    # ── Footer ───────────────────────────────────────────────────────────
    y += 6
    foot = "Daemonbot  ·  NFA DYOR"
    fw = _tw(draw, foot, F_FOOTER)
    draw.text((W * FACTOR - SPAD - fw, Y()), foot, font=F_FOOTER, fill=GOLD)
    y += 36

    final_h = min(y, MAX_H)
    cropped = canvas.crop((0, 0, W * FACTOR, final_h * FACTOR))
    out = cropped.resize((W, final_h), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
