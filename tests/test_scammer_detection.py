"""
tests/test_scammer_detection.py — Only the local heuristic pass (_local_score).
The AI second-opinion path needs a live API call, so it's out of scope for
unit tests; this covers the fast no-network layer that runs on every message.
"""

from services.scammer_detection import _local_score


class TestLocalScore:
    def test_normal_trading_chat_is_not_flagged(self):
        result = _local_score("yo this token is looking bullish, check the chart on dexscreener.com")
        assert result["score"] < 70

    def test_ip_literal_url_is_flagged(self):
        result = _local_score("claim your tokens at http://192.168.1.1/claim")
        assert result["score"] >= 40
        assert any("IP" in f for f in result["flags"])

    def test_urgency_claim_phrasing_is_flagged(self):
        result = _local_score("Congratulations! Your wallet has been selected, connect your wallet to claim now")
        assert result["score"] >= 35

    def test_typosquat_domain_is_flagged(self):
        result = _local_score("verify your account at metamask-support.com immediately")
        assert result["score"] >= 40

    def test_combined_signals_score_high_enough_to_skip_ai(self):
        # typosquat + urgency together should clear the 70-point auto-flag bar
        result = _local_score("connect your wallet to claim at phantom-verify.com now, limited time")
        assert result["score"] >= 70

    def test_plain_link_with_no_other_signal_is_low_risk(self):
        result = _local_score("check this out https://twitter.com/someuser/status/12345")
        assert result["score"] < 40
        assert result["has_link"] is True
