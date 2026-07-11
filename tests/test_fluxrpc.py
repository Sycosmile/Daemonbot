"""
tests/test_fluxrpc.py
"""

from unittest.mock import AsyncMock, patch

from services.fluxrpc import check_dev_sold, is_wallet_fresh, fresh_wallet_pct


class TestCheckDevSold:
    async def test_no_creator_is_unknown(self):
        assert await check_dev_sold("", "mint", []) == "unknown"

    async def test_creator_found_in_holders_with_balance_is_holding(self):
        holders = [{"address": "Dev1", "pct": 5.0}]
        result = await check_dev_sold("Dev1", "mint", holders)
        assert result == "holding"

    async def test_creator_found_with_near_zero_balance_is_sold(self):
        holders = [{"address": "Dev1", "pct": 0.001}]
        result = await check_dev_sold("Dev1", "mint", holders)
        assert result == "sold"

    async def test_creator_not_in_holders_falls_back_to_rpc_balance(self):
        with patch("services.fluxrpc.get_wallet_token_balance", AsyncMock(return_value=0.0)):
            result = await check_dev_sold("DevNotListed", "mint", [{"address": "Other", "pct": 10}])
            assert result == "sold"

    async def test_rpc_failure_is_unknown_not_sold(self):
        # Important: an RPC failure must never be reported as "sold" — that
        # would be a false rug-flag against a token we simply couldn't check.
        with patch("services.fluxrpc.get_wallet_token_balance", AsyncMock(return_value=None)):
            result = await check_dev_sold("DevNotListed", "mint", [])
            assert result == "unknown"


class TestFreshWallet:
    async def test_rpc_failure_returns_none(self):
        with patch("services.fluxrpc._rpc", AsyncMock(return_value=None)):
            assert await is_wallet_fresh("addr", 1) is None

    async def test_wallet_with_full_page_of_sigs_is_not_fresh(self):
        sigs = [{"blockTime": 1} for _ in range(50)]
        with patch("services.fluxrpc._rpc", AsyncMock(return_value=sigs)):
            assert await is_wallet_fresh("addr", 1) is False

    async def test_wallet_with_recent_only_sigs_is_fresh(self):
        import time
        sigs = [{"blockTime": time.time() - 60}]
        with patch("services.fluxrpc._rpc", AsyncMock(return_value=sigs)):
            assert await is_wallet_fresh("addr", window_days=1) is True

    async def test_empty_addresses_returns_none(self):
        assert await fresh_wallet_pct([], 1) is None
