"""
tests/test_ath_tracker.py
"""

import importlib


class TestAthTracker:
    async def test_first_seen_becomes_ath(self, tmp_path, monkeypatch):
        import services.ath_tracker as mod
        monkeypatch.setattr(mod, "ATH_FILE", str(tmp_path / "ath.json"))

        result = await mod.record_and_get_ath("ca1", 1000.0)
        assert result["ath_mc"] == 1000.0
        assert result["is_new_high"] is True
        assert result["pct_off_ath"] == 0.0

    async def test_lower_mc_does_not_overwrite_ath(self, tmp_path, monkeypatch):
        import services.ath_tracker as mod
        monkeypatch.setattr(mod, "ATH_FILE", str(tmp_path / "ath.json"))

        await mod.record_and_get_ath("ca2", 1000.0)
        result = await mod.record_and_get_ath("ca2", 500.0)
        assert result["ath_mc"] == 1000.0
        assert result["is_new_high"] is False
        assert result["pct_off_ath"] == -50.0

    async def test_new_high_updates_ath(self, tmp_path, monkeypatch):
        import services.ath_tracker as mod
        monkeypatch.setattr(mod, "ATH_FILE", str(tmp_path / "ath.json"))

        await mod.record_and_get_ath("ca3", 1000.0)
        result = await mod.record_and_get_ath("ca3", 1500.0)
        assert result["ath_mc"] == 1500.0
        assert result["is_new_high"] is True

    async def test_zero_or_negative_mc_is_a_noop(self, tmp_path, monkeypatch):
        import services.ath_tracker as mod
        monkeypatch.setattr(mod, "ATH_FILE", str(tmp_path / "ath.json"))

        result = await mod.record_and_get_ath("ca4", 0)
        assert result["ath_mc"] == 0
        assert result["is_new_high"] is False
