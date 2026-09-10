"""Tests for LoreConfig LLM registry pattern (E10.32)."""

import pytest
import yaml

from lore_mcp.config import LoreConfig


class TestLLMRegistry:

    def test_old_format_backward_compat(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({
            "llm": {
                "model": "granite-3-2-8b-instruct",
                "api_url": "http://localhost:8000/v1",
                "api_key": "sk-test",
            }
        }))
        cfg = LoreConfig.from_file(str(cfg_path))
        assert len(cfg.llm_registry) == 1
        assert cfg.llm_registry[0]["name"] == "default"
        assert cfg.llm_model == "granite-3-2-8b-instruct"
        assert cfg.llm_api_url == "http://localhost:8000/v1"
        assert cfg.llm_api_key == "sk-test"

    def test_new_registry_format(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({
            "llm": [
                {"name": "granite-8b", "model": "granite-3-2-8b-instruct",
                 "api_url": "http://host/v1", "api_key": "sk-1"},
                {"name": "granite-tiny", "model": "granite-4-0-h-tiny",
                 "api_url": "http://host/v1", "api_key": "sk-2"},
            ],
            "enrich": {
                "techniques": ["context", "qa"],
                "models": ["granite-tiny"],
            },
            "judge": {
                "models": ["granite-8b"],
            },
        }))
        cfg = LoreConfig.from_file(str(cfg_path))
        assert len(cfg.llm_registry) == 2
        assert cfg.enrich_techniques == ["context", "qa"]
        assert cfg.enrich_models == ["granite-tiny"]
        assert cfg.judge_models == ["granite-8b"]

    def test_get_llm_found(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({
            "llm": [
                {"name": "a", "model": "model-a", "api_url": "http://a"},
                {"name": "b", "model": "model-b", "api_url": "http://b"},
            ],
        }))
        cfg = LoreConfig.from_file(str(cfg_path))
        entry = cfg.get_llm("b")
        assert entry["model"] == "model-b"
        assert entry["api_url"] == "http://b"

    def test_get_llm_not_found(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({
            "llm": [{"name": "a", "model": "model-a"}],
        }))
        cfg = LoreConfig.from_file(str(cfg_path))
        with pytest.raises(KeyError, match="not found"):
            cfg.get_llm("unknown")

    def test_convenience_properties_default(self):
        cfg = LoreConfig.defaults()
        assert cfg.llm_model == "granite-3-2-8b-instruct"
        assert cfg.llm_api_url == ""
        assert cfg.llm_api_key == ""

    def test_convenience_properties_from_registry(self):
        cfg = LoreConfig(llm_registry=[
            {"name": "first", "model": "my-model",
             "api_url": "http://x", "api_key": "sk-x"},
        ])
        assert cfg.llm_model == "my-model"
        assert cfg.llm_api_url == "http://x"
        assert cfg.llm_api_key == "sk-x"

    def test_empty_llm_section(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml.dump({"database": {"path": "./test.db"}}))
        cfg = LoreConfig.from_file(str(cfg_path))
        assert cfg.llm_registry == []
        assert cfg.llm_model == "granite-3-2-8b-instruct"
