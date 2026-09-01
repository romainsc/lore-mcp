"""Tests for E10.21: YAML key consistency."""

import pytest


class TestModelConfigKeys:
    def test_accepts_models_key(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "models.yaml"
        f.write_text("models:\n  - name: test\n    mode: builtin\n")
        configs = parse_model_configs(str(f))
        assert len(configs) == 1

    def test_accepts_embedding_models_key(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "models.yaml"
        f.write_text("embedding_models:\n  - name: test\n    mode: builtin\n")
        configs = parse_model_configs(str(f))
        assert len(configs) == 1

    def test_embedding_models_takes_precedence(self, tmp_path):
        from lore_mcp.eval import parse_model_configs
        f = tmp_path / "models.yaml"
        f.write_text("models:\n  - name: old\nembedding_models:\n  - name: new\n")
        configs = parse_model_configs(str(f))
        assert configs[0]["name"] == "new"


class TestBuildConfigKeys:
    def test_accepts_embedding_models_key(self, tmp_path):
        from lore_mcp.build_config import BuildConfig
        f = tmp_path / "config.yaml"
        f.write_text("embedding_models:\n  - name: test\n    mode: builtin\n")
        config = BuildConfig.from_file(str(f))
        assert len(config.embedding_models) == 1

    def test_accepts_models_key(self, tmp_path):
        from lore_mcp.build_config import BuildConfig
        f = tmp_path / "config.yaml"
        f.write_text("models:\n  - name: test\n    mode: builtin\n")
        config = BuildConfig.from_file(str(f))
        assert len(config.embedding_models) == 1
