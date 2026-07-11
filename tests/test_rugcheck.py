"""
tests/test_rugcheck.py
"""

from services.rugcheck import parse_security, fresh_wallet_pct_estimate


class TestParseSecurity:
    def test_unavailable_on_none(self):
        assert parse_security(None) == {"available": False}

    def test_top_holder_breakdown(self):
        report = {
            "creator": "Dev111",
            "topHolders": [
                {"address": "Dev111", "pct": 4.5},
                {"address": "H2", "pct": 3.8},
                {"address": "H3", "pct": 3.5},
                {"address": "H4", "pct": 2.6},
                {"address": "H5", "pct": 2.5},
            ],
            "totalHolders": 418,
            "mintAuthority": None,
            "freezeAuthority": None,
        }
        result = parse_security(report)
        assert result["available"] is True
        assert result["top10_pct"] == 16.9
        assert result["top_breakdown"] == [4.5, 3.8, 3.5, 2.6, 2.5]
        assert result["total_holders"] == 418
        assert result["mint_renounced"] is True
        assert result["freeze_renounced"] is True

    def test_active_authorities_not_renounced(self):
        report = {"mintAuthority": "SomeWallet111", "freezeAuthority": "SomeWallet222"}
        result = parse_security(report)
        assert result["mint_renounced"] is False
        assert result["freeze_renounced"] is False

    def test_pct_normalises_0_to_1_scale(self):
        # Some schema versions report a 0-1 'percent' instead of 0-100 'pct'
        report = {"topHolders": [{"address": "A", "percent": 0.045}]}
        result = parse_security(report)
        assert result["top10_pct"] == 4.5

    def test_lore_pulled_from_filemeta_description(self):
        report = {"fileMeta": {"description": "Some lore text"}}
        result = parse_security(report)
        assert result["lore"] == "Some lore text"

    def test_missing_fields_degrade_to_safe_defaults(self):
        # A non-empty report missing most fields should still parse cleanly.
        # (A literally empty dict is falsy and correctly treated the same as
        # None — see test_unavailable_on_none.)
        result = parse_security({"rugged": False})
        assert result["available"] is True
        assert result["top10_pct"] == 0
        assert result["top_breakdown"] == []
        assert result["lore"] == ""


class TestFreshWalletEstimate:
    def test_none_when_no_dates(self):
        assert fresh_wallet_pct_estimate([], 1) is None

    def test_computes_percentage(self):
        import time
        now = time.time()
        dates = [now, now, now - 30 * 86400]  # 2 of 3 are "now" (fresh)
        result = fresh_wallet_pct_estimate(dates, window_days=7)
        assert result == 66.7
