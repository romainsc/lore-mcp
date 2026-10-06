"""Tests for LLM enrichment. See E12.09, E12.14, E12.89."""

import pytest
from unittest.mock import patch, MagicMock

from lore_mcp.preprocess.enrich import enrich_context, enrich_meta, enrich_qa
from lore_mcp.preprocess.llm import LLMConfig, call_llm


class TestCallLLM:

    def test_missing_url_raises(self):
        config = LLMConfig(api_url="", model="test")
        with pytest.raises(ValueError, match="api_url is required"):
            call_llm(config, "prompt")

    def test_calls_openai_compatible(self, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"choices":[{"message":{"content":"response"}}]}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        import lore_mcp.preprocess.llm as llm_mod
        monkeypatch.setattr(llm_mod.urllib.request, "urlopen", lambda *a, **kw: mock_resp)

        config = LLMConfig(api_url="http://fake/v1/chat/completions", model="test")
        result = call_llm(config, "test prompt")
        assert result == "response"


class TestLLMConfig:

    def test_from_registry(self):
        entry = {
            "api_url": "http://localhost:8080/v1/chat/completions",
            "model": "test-model",
            "api_key": "sk-test",
            "verify_ssl": False,
            "concurrency": 4,
            "timeout": 120,
        }
        config = LLMConfig.from_registry(entry)
        assert config.api_url == "http://localhost:8080/v1/chat/completions"
        assert config.model == "test-model"
        assert config.api_key == "sk-test"
        assert config.verify_ssl is False
        assert config.concurrency == 4
        assert config.timeout == 120

    def test_from_registry_defaults(self):
        config = LLMConfig.from_registry({})
        assert config.api_url == ""
        assert config.concurrency == 1
        assert config.verify_ssl is True
        assert config.timeout == 60
        assert config.params == {}

    def test_from_registry_with_params(self):
        entry = {
            "api_url": "http://localhost:8080/v1/chat/completions",
            "model": "test",
            "params": {"top_p": 0.9, "seed": 42},
        }
        config = LLMConfig.from_registry(entry)
        assert config.params == {"top_p": 0.9, "seed": 42}

    def test_params_merged_into_call_llm(self, monkeypatch):
        """E12.127: params dict forwarded to JSON body."""
        import json

        captured = {}
        def mock_urlopen(req, **kwargs):
            captured["body"] = json.loads(req.data)
            class FakeResp:
                def read(self):
                    return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        monkeypatch.setattr("lore_mcp.preprocess.service.run_with_interrupt", lambda fn: fn())

        config = LLMConfig(
            api_url="http://fake/v1/chat/completions",
            model="test",
            params={"top_p": 0.9, "seed": 42},
        )
        from lore_mcp.preprocess.llm import call_llm
        call_llm(config, "hello")
        assert captured["body"]["top_p"] == 0.9
        assert captured["body"]["seed"] == 42
        assert captured["body"]["model"] == "test"

    def test_no_params_no_extra_fields(self, monkeypatch):
        """E12.127: no params → no extra fields (backward compat)."""
        import json

        captured = {}
        def mock_urlopen(req, **kwargs):
            captured["body"] = json.loads(req.data)
            class FakeResp:
                def read(self):
                    return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
        monkeypatch.setattr("lore_mcp.preprocess.service.run_with_interrupt", lambda fn: fn())

        config = LLMConfig(api_url="http://fake/v1/chat/completions", model="test")
        from lore_mcp.preprocess.llm import call_llm
        call_llm(config, "hello")
        assert "top_p" not in captured["body"]
        assert set(captured["body"].keys()) == {"model", "messages", "temperature", "max_tokens"}


class TestEnrichContext:

    def test_adds_context_paragraph(self, monkeypatch):
        import lore_mcp.preprocess.llm as llm_mod
        monkeypatch.setattr(llm_mod, "call_llm", lambda cfg, prompt: "This section covers authentication setup.")

        text = "## Authentication\n\nConfigure SSO with LDAP."
        result = enrich_context(text, llm_url="http://fake", llm_model="test")

        assert "This section covers authentication setup." in result
        assert "Configure SSO with LDAP." in result

    def test_empty_text_unchanged(self):
        result = enrich_context("", llm_url="http://fake", llm_model="test")
        assert result == ""

    def test_with_llm_config(self, monkeypatch):
        import lore_mcp.preprocess.llm as llm_mod
        monkeypatch.setattr(llm_mod, "call_llm", lambda cfg, prompt: "context added")

        config = LLMConfig(api_url="http://fake", model="test", concurrency=4)
        text = "## Title\n\nBody text."
        result = enrich_context(text, llm=config)

        assert "context added" in result


class TestEnrichQA:

    def test_appends_questions(self, monkeypatch):
        import lore_mcp.preprocess.llm as llm_mod
        monkeypatch.setattr(llm_mod, "call_llm", lambda cfg, prompt: "Q: How to configure SSO?\nQ: What is LDAP?")

        text = "## Authentication\n\nConfigure SSO with LDAP."
        result = enrich_qa(text, llm_url="http://fake", llm_model="test")

        assert "How to configure SSO?" in result
        assert "Configure SSO with LDAP." in result


class TestEnrichMeta:

    def test_adds_summary_and_keywords(self, monkeypatch):
        import lore_mcp.preprocess.llm as llm_mod
        monkeypatch.setattr(
            llm_mod, "call_llm",
            lambda cfg, prompt: "Summary: This section explains SSO configuration.\n\nKeywords: SSO, LDAP",
        )

        text = "## Authentication\n\nConfigure SSO with LDAP."
        result = enrich_meta(text, llm_url="http://fake", llm_model="test")

        assert "Summary: This section explains SSO configuration." in result
        assert "Keywords: SSO, LDAP" in result
        assert "Configure SSO with LDAP." in result

    def test_empty_text_unchanged(self):
        result = enrich_meta("", llm_url="http://fake", llm_model="test")
        assert result == ""
