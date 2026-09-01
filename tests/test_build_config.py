"""Tests for E10.13: unified build config."""

import os
from unittest.mock import patch

import pytest


class TestBuildConfigFromFile:
    def test_parse_full_config(self, tmp_path):
        from lore_mcp.build_config import BuildConfig
        config_path = tmp_path / "build-config.yaml"
        config_path.write_text("""
embedding:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: builtin
  - name: ibm-granite/granite-embedding-311m-multilingual-r2
    mode: api
    api_url: http://localhost:8082/v1/embeddings

judge:
  model: ibm-granite/granite-3.3-8b-instruct
  api_url: http://localhost:11434/v1
  verify_ssl: false

metrics:
  - score_spread
  - source_diversity
  - mrr

optimize:
  chunk_sizes: [512, 1024]
  chunk_overlaps: [64]
  top_ks: [3, 5]
  num_questions: 30
""")
        config = BuildConfig.from_file(str(config_path))
        assert len(config.embedding_models) == 2
        assert config.judge_model == "ibm-granite/granite-3.3-8b-instruct"
        assert config.judge_api_url == "http://localhost:11434/v1"
        assert config.judge_verify_ssl is False
        assert "mrr" in config.metrics
        assert config.chunk_sizes == [512, 1024]
        assert config.num_questions == 30

    def test_parse_minimal_config(self, tmp_path):
        from lore_mcp.build_config import BuildConfig
        config_path = tmp_path / "minimal.yaml"
        config_path.write_text("""
embedding:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: builtin
""")
        config = BuildConfig.from_file(str(config_path))
        assert len(config.embedding_models) == 1
        assert config.chunk_sizes == [512, 1024, 2048]
        assert config.num_questions == 50


class TestBuildConfigFromEnv:
    def test_reads_env_vars(self):
        from lore_mcp.build_config import BuildConfig
        with patch.dict(os.environ, {
            "LORE_LLM_URL": "http://localhost:11434/v1",
            "LORE_LLM_MODEL": "granite-8b",
        }):
            config = BuildConfig.from_env()
            assert config.judge_api_url == "http://localhost:11434/v1"
            assert config.judge_model == "granite-8b"
