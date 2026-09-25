"""Tests for configurable enrichment prompts. See E12.74."""

import yaml
import pytest

from lore_mcp.config import LoreConfig
from lore_mcp.preprocess.enrich import _get_prompt


class TestPromptCascade:
    """E12.74: prompt resolution follows config → file → default → fallback."""

    def test_default_prompts_loaded(self):
        """Without config, distributed prompts.yaml FR/EN are used."""
        result = _get_prompt("en", "context", "## Title", "Body text")
        assert "RAG indexing" in result
        assert "Title" in result

    def test_default_prompts_fr(self):
        """FR prompts load from distributed file."""
        result = _get_prompt("fr", "context", "## Titre", "Contenu")
        assert "indexation RAG" in result.lower() or "RAG" in result
        assert "Titre" in result

    def test_inline_override(self):
        """Config with enrich_prompts overrides default."""
        cfg = LoreConfig(enrich_prompts={
            "en": {"context": "CUSTOM: {heading} | {body}"}
        })
        result = _get_prompt("en", "context", "H1", "B1", config=cfg)
        assert result == "CUSTOM: H1 | B1"

    def test_custom_file(self, tmp_path):
        """Config with enrich_prompts_file loads from file."""
        custom = tmp_path / "custom-prompts.yaml"
        custom.write_text(yaml.dump({
            "en": {"context": "FROM FILE: {heading} — {body}"}
        }))
        cfg = LoreConfig(enrich_prompts_file=str(custom))
        result = _get_prompt("en", "context", "H1", "B1", config=cfg)
        assert result == "FROM FILE: H1 — B1"

    def test_cascade_inline_wins_over_file(self, tmp_path):
        """Inline config takes precedence over custom file."""
        custom = tmp_path / "custom-prompts.yaml"
        custom.write_text(yaml.dump({
            "en": {"context": "FROM FILE: {heading}"}
        }))
        cfg = LoreConfig(
            enrich_prompts={"en": {"context": "INLINE: {heading} {body}"}},
            enrich_prompts_file=str(custom),
        )
        result = _get_prompt("en", "context", "H", "B", config=cfg)
        assert result.startswith("INLINE:")

    def test_fallback_unknown_language(self):
        """Unknown language falls back to EN."""
        result = _get_prompt("de", "context", "## Titel", "Inhalt")
        assert "Titel" in result
        # Should contain the EN template with a language hint or raw EN template
        assert len(result) > 10

    def test_all_techniques_available(self):
        """All 4 techniques have prompts in default config."""
        for technique in ["context", "qa", "meta", "stt_fix"]:
            result = _get_prompt("en", technique, "## H", "body")
            assert len(result) > 20, f"Missing prompt for {technique}"

    def test_body_truncated(self):
        """Body is truncated to 500 chars in the prompt."""
        long_body = "x" * 1000
        result = _get_prompt("en", "context", "## H", long_body)
        assert "x" * 501 not in result
