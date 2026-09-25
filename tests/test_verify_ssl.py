"""Tests for E10.25: verify_ssl propagation to all API call points."""

import ssl
from unittest.mock import patch, MagicMock
import pytest


class TestFetchApiVerifySsl:
    """_fetch_api passes verify_ssl to urlopen context."""

    def test_verify_ssl_false_creates_unverified_context(self):
        """verify_ssl=False → urlopen called with unverified SSL context."""
        from lore_mcp.preprocess.parse import _fetch_api
        import urllib.request

        req = urllib.request.Request("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            _fetch_api(req, 10, verify_ssl=False)

            mock_open.assert_called_once()
            call_kwargs = mock_open.call_args.kwargs
            ctx = call_kwargs.get("context")
            assert ctx is not None, "SSL context should be passed"
            assert ctx.check_hostname is False
            assert ctx.verify_mode == ssl.CERT_NONE

    def test_verify_ssl_true_no_custom_context(self):
        """verify_ssl=True (default) → no custom SSL context."""
        from lore_mcp.preprocess.parse import _fetch_api
        import urllib.request

        req = urllib.request.Request("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            _fetch_api(req, 10)

            mock_open.assert_called_once()
            assert "context" not in mock_open.call_args.kwargs


class TestCallLlmVerifySsl:
    """_call_llm passes verify_ssl to urlopen."""

    def test_verify_ssl_false_passed(self):
        """_call_llm with verify_ssl=False creates unverified context."""
        from lore_mcp.preprocess.enrich import _call_llm

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "test"}}]}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            _call_llm("test prompt", "https://example.com/v1/chat/completions",
                       "model", verify_ssl=False)

            mock_open.assert_called_once()
            ctx = mock_open.call_args.kwargs.get("context")
            assert ctx is not None
            assert ctx.check_hostname is False

    def test_verify_ssl_default_true(self):
        """_call_llm default → no custom SSL context."""
        from lore_mcp.preprocess.enrich import _call_llm

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "test"}}]}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            _call_llm("test prompt", "https://example.com/v1/chat/completions", "model")

            assert "context" not in mock_open.call_args.kwargs
