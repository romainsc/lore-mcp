"""Tests for E3.09 MVP1: MCP tools for lint and state management."""

import json
import pytest


class TestLintTool:
    """lint_source MCP tool."""

    def test_returns_verdict(self, tmp_path):
        from lore_mcp.server import lint_source

        doc = tmp_path / "doc.md"
        doc.write_text("## Title\n\nGood content here with enough text.\n")

        result = lint_source(str(doc))
        assert "verdict" in result.lower() or "good" in result.lower() or "density" in result.lower()

    def test_missing_file(self, tmp_path):
        from lore_mcp.server import lint_source

        result = lint_source(str(tmp_path / "nonexistent.md"))
        assert "not found" in result.lower() or "error" in result.lower()


class TestListStateTool:
    """list_pipeline_state MCP tool."""

    def test_returns_format(self):
        from lore_mcp.server import list_pipeline_state

        result = list_pipeline_state()
        assert isinstance(result, str)

    def test_with_state(self, tmp_path):
        from lore_mcp.checkpoint import Checkpoint
        import yaml

        manifest = tmp_path / "m.yaml"
        manifest.write_text(yaml.dump({"collection": "test-mcp-tool", "sources": []}))
        cp = Checkpoint(str(manifest))
        cp.mark_phase_done("phase1")

        from lore_mcp.server import list_pipeline_state
        result = list_pipeline_state()
        assert "phase" in result.lower() or "state" in result.lower()


class TestPurgeStateTool:
    """purge_pipeline_state MCP tool."""

    def test_purge_nonexistent(self):
        from lore_mcp.server import purge_pipeline_state

        result = purge_pipeline_state(hash="nonexistent123456")
        assert "not found" in result.lower()

    def test_purge_all(self):
        from lore_mcp.server import purge_pipeline_state

        result = purge_pipeline_state(purge_all=True)
        assert "purged" in result.lower() or "0" in result
