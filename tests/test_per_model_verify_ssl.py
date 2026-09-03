"""Tests for E10.25: per-model verify_ssl in embedding config."""

import pytest
from unittest.mock import patch


class TestEmbedderVerifySsl:
    def test_default_verify_ssl_true(self):
        from lore_mcp.embedder import Embedder
        emb = Embedder(model_name="test", mode="api",
                       api_url="http://localhost:8081/v1/embeddings")
        assert emb.api_verify is True

    def test_verify_ssl_false_from_constructor(self):
        from lore_mcp.embedder import Embedder
        emb = Embedder(model_name="test", mode="api",
                       api_url="https://tei.internal/v1/embeddings",
                       verify_ssl=False)
        assert emb.api_verify is False

    def test_verify_ssl_overrides_env(self):
        from lore_mcp.embedder import Embedder
        with patch.dict("os.environ", {"LORE_API_VERIFY": "true"}):
            emb = Embedder(model_name="test", mode="api",
                           api_url="https://tei.internal/v1/embeddings",
                           verify_ssl=False)
            assert emb.api_verify is False


class TestConfigVerifySsl:
    def test_verify_ssl_in_yaml(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "config.yaml"
        f.write_text("""
embedding:
  - name: model-a
    mode: api
    api_url: https://tei.internal/v1/embeddings
    verify_ssl: false
  - name: model-b
    mode: api
    api_url: http://localhost:8082/v1/embeddings
""")
        configs = parse_model_configs(str(f))
        assert configs[0].get("verify_ssl") is False
        assert configs[1].get("verify_ssl") is None


class TestEmbedderLoading:
    def test_load_embedders_respects_verify_ssl(self):
        from lore_mcp.embedder import Embedder
        configs = [
            {"name": "model-a", "mode": "api",
             "api_url": "https://tei.internal/v1/embeddings",
             "verify_ssl": False},
            {"name": "model-b", "mode": "api",
             "api_url": "http://localhost:8082/v1/embeddings"},
        ]
        embedders = {}
        for cfg in configs:
            emb = Embedder(
                model_name=cfg["name"],
                mode=cfg.get("mode", "builtin"),
                api_url=cfg.get("api_url"),
                verify_ssl=cfg.get("verify_ssl"),
            )
            embedders[cfg["name"]] = emb

        assert embedders["model-a"].api_verify is False
        assert embedders["model-b"].api_verify is True
