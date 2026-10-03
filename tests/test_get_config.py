"""Tests for get_config MCP tool. See grooming-E3.40.md."""

import yaml

from lore_mcp.config import LoreConfig
from lore_mcp.server import _build_config_yaml


class TestBuildConfigYaml:
    def test_returns_valid_yaml(self):
        config = LoreConfig()
        result = _build_config_yaml(config)
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_includes_main_sections(self):
        config = LoreConfig()
        parsed = yaml.safe_load(_build_config_yaml(config))
        for section in ("database", "embedding", "chunking", "search"):
            assert section in parsed, f"Missing section: {section}"

    def test_masks_api_keys(self):
        config = LoreConfig(
            llm_registry=[{
                "name": "test",
                "model": "granite-3-8b",
                "api_url": "http://localhost:8080/v1/chat/completions",
                "api_key": "sk-secret-123456",
            }],
            reranking_api_key="rk-secret-789",
        )
        result = _build_config_yaml(config)
        assert "sk-secret-123456" not in result
        assert "rk-secret-789" not in result
        assert "***" in result

    def test_embedding_fields(self):
        config = LoreConfig(
            embedding_model="nomic-ai/nomic-embed-text-v2-moe",
            embedding_mode="builtin:gpu",
            embedding_batch_size=32,
        )
        parsed = yaml.safe_load(_build_config_yaml(config))
        emb = parsed["embedding"]
        assert emb["model"] == "nomic-ai/nomic-embed-text-v2-moe"
        assert emb["mode"] == "builtin:gpu"
        assert emb["batch_size"] == 32

    def test_chunking_fields(self):
        config = LoreConfig(chunk_size=512, chunk_overlap=64)
        parsed = yaml.safe_load(_build_config_yaml(config))
        assert parsed["chunking"]["chunk_size"] == 512
        assert parsed["chunking"]["chunk_overlap"] == 64

    def test_llm_registry(self):
        config = LoreConfig(llm_registry=[
            {"name": "ollama", "model": "granite:8b", "api_url": "http://localhost:11434"},
        ])
        parsed = yaml.safe_load(_build_config_yaml(config))
        assert "llm" in parsed
        assert len(parsed["llm"]) == 1
        assert parsed["llm"][0]["name"] == "ollama"

    def test_enrich_section(self):
        config = LoreConfig(enrich_techniques=["context", "meta"])
        parsed = yaml.safe_load(_build_config_yaml(config))
        assert parsed["enrich"]["techniques"] == ["context", "meta"]

    def test_parse_section(self):
        config = LoreConfig(ocr_engine="tesseract", ocr_lang=["fra"])
        parsed = yaml.safe_load(_build_config_yaml(config))
        assert parsed["parse"]["ocr_engine"] == "tesseract"
        assert parsed["parse"]["ocr_lang"] == ["fra"]

    def test_parse_caption_fields(self):
        config = LoreConfig(
            ocr_engine="tesseract",
            caption_additional=["granite-vision", "molmo"],
            caption_selection="judge",
            caption_judge="granite-judge",
            video_frame_strategy="ocr",
            video_frame_interval=60,
        )
        parsed = yaml.safe_load(_build_config_yaml(config))
        p = parsed["parse"]
        assert p["caption_additional"] == ["granite-vision", "molmo"]
        assert p["caption_selection"] == "judge"
        assert p["caption_judge"] == "granite-judge"
        assert p["video_frame_strategy"] == "ocr"
        assert p["video_frame_interval"] == 60

    def test_parse_defaults_omitted(self):
        config = LoreConfig(ocr_engine="tesseract")
        parsed = yaml.safe_load(_build_config_yaml(config))
        p = parsed["parse"]
        assert "caption_selection" not in p
        assert "video_frame_strategy" not in p
        assert "video_frame_interval" not in p

    def test_omits_runtime_flags(self):
        config = LoreConfig(force=True, output_level="debug")
        result = _build_config_yaml(config)
        parsed = yaml.safe_load(result)
        for section in parsed.values():
            if isinstance(section, dict):
                assert "force" not in section
                assert "output_level" not in section

    def test_empty_sections_omitted(self):
        config = LoreConfig()
        parsed = yaml.safe_load(_build_config_yaml(config))
        if "llm" in parsed:
            assert len(parsed["llm"]) > 0 or "llm" not in parsed
