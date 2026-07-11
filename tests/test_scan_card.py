"""
tests/test_scan_card.py
"""

from services.scan_card import generate_scan_card


FULL_DATA = {
    "name": "Burnie Boden Pnut", "symbol": "BBP", "trending_rank": 15,
    "price_usd": 0.04044, "price_change_pct": 35.0,
    "mc": 40000, "vol_1h": 162600, "liq": 7300,
    "supply_circ": 988700000, "supply_total": 988700000,
    "age_label": "18m", "buys_1h": 1000, "sells_1h": 901,
    "ath_mc": 51300, "ath_pct_off": -22.0, "ath_time_label": "29s",
    "socials_age_label": "8m", "twitter_url": "https://x.com/example",
    "lore": "A community-driven meme experiment. NFA DYOR.",
    "security_available": True,
    "fresh_1d": 5.1, "fresh_7d": 15.0,
    "top10_pct": 26.0, "total_holders": 418,
    "top_breakdown": [4.5, 3.8, 3.5, 2.6, 2.5],
    "dev_sold": "holding", "dex_paid": True,
    "mint_renounced": True, "freeze_renounced": True,
    "risk_score": 28,
    "caller_username": "KINGSYCO9", "caller_mc": 42300,
    "caller_pct_change": -6.0, "caller_time_label": "59s",
}


class TestGenerateScanCard:
    def test_full_data_renders_a_valid_png(self):
        img_bytes = generate_scan_card(FULL_DATA)
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(img_bytes) > 5000

    def test_sparse_data_does_not_crash(self):
        sparse = {"name": "Mystery Coin", "symbol": "MYST", "price_usd": 0.0012, "mc": 12000}
        img_bytes = generate_scan_card(sparse)
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_empty_dict_does_not_crash(self):
        img_bytes = generate_scan_card({})
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_security_unavailable_path(self):
        data = dict(FULL_DATA, security_available=False)
        img_bytes = generate_scan_card(data)
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_no_caller_info_path(self):
        data = {k: v for k, v in FULL_DATA.items() if not k.startswith("caller_")}
        img_bytes = generate_scan_card(data)
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_long_lore_text_gets_wrapped_not_overflowed(self):
        data = dict(FULL_DATA, lore="word " * 200)  # absurdly long description
        img_bytes = generate_scan_card(data)
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_long_name_gets_truncated(self):
        data = dict(FULL_DATA, name="A" * 80)
        img_bytes = generate_scan_card(data)
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"
