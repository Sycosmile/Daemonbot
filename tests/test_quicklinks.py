"""
tests/test_quicklinks.py
"""

from services.quicklinks import analytics_links, quickbuy_links, build_keyboard_rows


class TestAnalyticsLinks:
    def test_includes_solscan_explorer(self):
        links = analytics_links("CA111", "PAIR111", "BBP", "https://dexscreener.com/x")
        assert links["EXP"] == "https://solscan.io/token/CA111"
        assert links["DS"] == "https://dexscreener.com/x"

    def test_falls_back_to_constructed_dexscreener_url(self):
        links = analytics_links("CA111", "", "BBP")
        assert links["DS"] == "https://dexscreener.com/solana/CA111"

    def test_empty_pair_address_blanks_pair_dependent_links(self):
        links = analytics_links("CA111", "", "BBP")
        assert links["DEF"] == ""
        assert links["GT"] == ""


class TestQuickbuyLinks:
    def test_omits_pair_dependent_bots_without_a_pair_address(self):
        links = quickbuy_links("CA111", pair_address="")
        assert "Photon" not in links
        assert "GMGN" in links

    def test_includes_photon_when_pair_address_given(self):
        links = quickbuy_links("CA111", pair_address="PAIR111")
        assert "Photon" in links
        assert "PAIR111" in links["Photon"]


class TestBuildKeyboardRows:
    def test_drops_empty_urls(self):
        rows = build_keyboard_rows({"A": "url1", "B": ""}, {})
        flat = [item for row in rows for item in row]
        assert ("B", "") not in flat
        assert ("A", "url1") in flat

    def test_chunks_into_rows_of_four(self):
        analytics = {f"L{i}": f"u{i}" for i in range(5)}
        rows = build_keyboard_rows(analytics, {}, row_size=4)
        assert len(rows[0]) == 4
        assert len(rows[1]) == 1
