"""
tests/test_chat.py — Pure trigger-resolution logic, no network/Telegram calls.
"""

import pytest
from handlers.chat import _resolve_trigger


class TestPrivateChat:
    def test_always_responds_in_dm(self):
        should, text = _resolve_trigger("yo what's up", "private", "Daemonbot", False)
        assert should is True
        assert text == "yo what's up"


class TestNonGroupNonPrivate:
    def test_channel_never_responds(self):
        should, _ = _resolve_trigger("Daemon any news", "channel", "Daemonbot", False)
        assert should is False


class TestMention:
    def test_mention_anywhere_triggers(self):
        should, text = _resolve_trigger("check this token @Daemonbot pls", "group", "Daemonbot", False)
        assert should is True
        assert text == "check this token  pls"

    def test_mention_case_insensitive_and_stripped(self):
        should, text = _resolve_trigger("@DAEMONBOT is this a rug", "group", "Daemonbot", False)
        assert should is True
        assert text == "is this a rug"


class TestNameTrigger:
    def test_bare_name_at_start_triggers(self):
        should, text = _resolve_trigger("Daemon, is this a rug?", "group", "Daemonbot", False)
        assert should is True
        assert text == "is this a rug?"

    def test_bot_username_at_start_triggers(self):
        should, text = _resolve_trigger("Daemonbot what's the price of doge", "group", "Daemonbot", False)
        assert should is True
        assert text == "what's the price of doge"

    def test_similar_word_does_not_trigger(self):
        # Regression test: "daemonology"/"daemonic" must NOT match "daemon"
        should, _ = _resolve_trigger("Daemonology alert: token X looks legit", "group", "Daemonbot", False)
        assert should is False

    def test_name_mid_message_does_not_trigger(self):
        should, _ = _resolve_trigger("lol daemon that's a rug", "group", "Daemonbot", False)
        assert should is False

    def test_markdown_wrapped_name_still_strips_cleanly(self):
        should, text = _resolve_trigger("**Daemon** what do you think", "group", "Daemonbot", False)
        assert should is True
        assert text == "what do you think"


class TestReplyToBot:
    def test_reply_to_bot_triggers(self):
        should, text = _resolve_trigger("interesting take", "group", "Daemonbot", True)
        assert should is True
        assert text == "interesting take"

    def test_unrelated_group_message_is_silent(self):
        should, _ = _resolve_trigger("just chatting, nothing here", "group", "Daemonbot", False)
        assert should is False


class TestNoBotUsername:
    def test_generic_aliases_still_work_without_live_username(self):
        should, text = _resolve_trigger("daemon you up?", "group", None, False)
        assert should is True
        assert text == "you up?"
