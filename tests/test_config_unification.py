"""Tests for E10.21: unified config, embedding: key, no --models."""

import pytest


class TestEmbeddingKey:
    def test_parse_embedding_key(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "config.yaml"
        f.write_text("embedding:\n  - name: test\n    mode: builtin\n")
        configs = parse_model_configs(str(f))
        assert len(configs) == 1
        assert configs[0]["name"] == "test"

    def test_reject_models_key(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "config.yaml"
        f.write_text("models:\n  - name: test\n")
        with pytest.raises(ValueError, match="embedding"):
            parse_model_configs(str(f))

    def test_reject_embedding_models_key(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "config.yaml"
        f.write_text("embedding_models:\n  - name: test\n")
        with pytest.raises(ValueError, match="embedding"):
            parse_model_configs(str(f))


class TestBuildConfigEmbeddingKey:
    def test_accepts_embedding_key(self, tmp_path):
        from lore_mcp.build_config import BuildConfig
        f = tmp_path / "config.yaml"
        f.write_text("embedding:\n  - name: test\n    mode: builtin\n")
        config = BuildConfig.from_file(str(f))
        assert len(config.embedding_models) == 1

    def test_rejects_old_keys(self, tmp_path):
        from lore_mcp.build_config import BuildConfig
        f = tmp_path / "config.yaml"
        f.write_text("models:\n  - name: test\n")
        with pytest.raises(ValueError, match="embedding"):
            BuildConfig.from_file(str(f))
