"""Tests for LLM enrichment. See E12.09, E12.14."""

import pytest
from unittest.mock import patch, MagicMock

from lore_mcp.preprocess.enrich import enrich_context, enrich_meta, enrich_qa, _call_llm


class TestCallLLM:

    def test_missing_url_raises(self):
        with pytest.raises(ValueError, match="LORE_LLM_URL"):
            _call_llm("prompt", llm_url="", llm_model="test")

    def test_calls_openai_compatible(self, monkeypatch):
        mock_urlopen = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices":[{"message":{"content":"response"}}]}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        import lore_mcp.preprocess.enrich as mod
        monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **kw: mock_resp)

        result = _call_llm("test prompt", llm_url="http://fake/v1/chat/completions", llm_model="test")
        assert result == "response"


class TestEnrichContext:

    def test_adds_context_paragraph(self, monkeypatch):
        import lore_mcp.preprocess.enrich as mod
        monkeypatch.setattr(mod, "_call_llm", lambda *a, **kw: "This section covers authentication setup.")

        text = "## Authentication\n\nConfigure SSO with LDAP."
        result = enrich_context(text, llm_url="http://fake", llm_model="test")

        assert "This section covers authentication setup." in result
        assert "Configure SSO with LDAP." in result

    def test_empty_text_unchanged(self, monkeypatch):
        import lore_mcp.preprocess.enrich as mod
        monkeypatch.setattr(mod, "_call_llm", lambda *a, **kw: "")

        result = enrich_context("", llm_url="http://fake", llm_model="test")
        assert result == ""


class TestEnrichQA:

    def test_appends_questions(self, monkeypatch):
        import lore_mcp.preprocess.enrich as mod
        monkeypatch.setattr(mod, "_call_llm", lambda *a, **kw: "Q: How to configure SSO?\nQ: What is LDAP?")

        text = "## Authentication\n\nConfigure SSO with LDAP."
        result = enrich_qa(text, llm_url="http://fake", llm_model="test")

        assert "How to configure SSO?" in result
        assert "Configure SSO with LDAP." in result


class TestEnrichMeta:

    def test_appends_summary_and_keywords(self, monkeypatch):
        import lore_mcp.preprocess.enrich as mod
        monkeypatch.setattr(
            mod, "_call_llm",
            lambda *a, **kw: "Summary: This section explains SSO configuration.\nKeywords: SSO, LDAP, authentication, config",
        )

        text = "## Authentication\n\nConfigure SSO with LDAP."
        result = enrich_meta(text, llm_url="http://fake", llm_model="test")

        assert "Summary: This section explains SSO configuration." in result
        assert "Keywords: SSO, LDAP" in result
        assert "Configure SSO with LDAP." in result

    def test_empty_text_unchanged(self, monkeypatch):
        import lore_mcp.preprocess.enrich as mod
        monkeypatch.setattr(mod, "_call_llm", lambda *a, **kw: "")

        result = enrich_meta("", llm_url="http://fake", llm_model="test")
        assert result == ""
