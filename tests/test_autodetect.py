"""
tests/test_autodetect.py — Pure regex/parsing logic, no network calls.
"""

import pytest
from handlers.autodetect import _extract_candidate, _classify_detail


class TestExtractCandidate:
    def test_evm_address_detected(self):
        kind, value = _extract_candidate("check this 0x1234567890123456789012345678901234567890")
        assert kind == "ca"
        assert value == "0x1234567890123456789012345678901234567890"

    def test_real_solana_usdc_address_detected(self):
        # Real USDC mint on Solana — known-good base58, no 0/O/I/l chars
        kind, value = _extract_candidate("check out EPjFWdd5AufqSSqeM2qN1xzybapTVG4itwzodS5BJ3Si")
        assert kind == "ca"
        assert value == "EPjFWdd5AufqSSqeM2qN1xzybapTVG4itwzodS5BJ3Si"

    def test_cashtag_detected(self):
        kind, value = _extract_candidate("bros have you seen $BONK today")
        assert kind == "ticker"
        assert value == "BONK"

    def test_dollar_amount_not_treated_as_ticker(self):
        # "$50" should NOT match — cashtag regex requires letters, not digits
        kind, value = _extract_candidate("I spent $50 on coffee this morning")
        assert kind is None
        assert value is None

    def test_plain_chat_has_no_match(self):
        kind, value = _extract_candidate("just chatting, nothing here")
        assert kind is None

    def test_evm_takes_priority_over_cashtag(self):
        kind, value = _extract_candidate("0x1234567890123456789012345678901234567890 aka $TOKEN")
        assert kind == "ca"


class TestClassifyDetail:
    def test_trailing_comma_is_detailed(self):
        assert _classify_detail("$WIF,") == "detailed"

    def test_trailing_period_is_compact(self):
        assert _classify_detail("$WIF.") == "compact"

    def test_no_suffix_is_default(self):
        assert _classify_detail("$WIF") == "default"

    def test_whitespace_is_stripped_before_checking(self):
        assert _classify_detail("$WIF,   ") == "detailed"
