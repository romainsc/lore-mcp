"""Tests for E3.31 MVP1: structured data to knowledge. See grooming-E3.31.md."""

import json
import pytest


class TestJsonNarration:
    """JSON array of records → markdown with headings."""

    def test_adds_collection_heading(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        data = json.dumps({"name": "World Cup 2022", "matches": [
            {"team1": "Qatar", "team2": "Ecuador", "score": "0-2"},
        ]})
        result = narrate_structured(data, "json")
        assert "## " in result or "# " in result

    def test_records_as_sections(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        data = json.dumps({"items": [
            {"name": "Alpha", "value": 1},
            {"name": "Beta", "value": 2},
        ]})
        result = narrate_structured(data, "json")
        assert "Alpha" in result
        assert "Beta" in result

    def test_flat_object_as_key_value(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        data = json.dumps({"title": "Report", "author": "Jane", "year": 2026})
        result = narrate_structured(data, "json")
        assert "Report" in result
        assert "# " in result

    def test_passthrough_non_json(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        text = "Just regular markdown text\n\n## Heading\n\nContent."
        result = narrate_structured(text, "json")
        assert result == text


class TestCsvNarration:
    """CSV/table content → markdown with headings."""

    def test_adds_heading_to_table(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        table = "| Name | Score |\n| - | - |\n| Alice | 95 |\n| Bob | 87 |"
        result = narrate_structured(table, "markitdown")
        assert "## " in result or "# " in result

    def test_preserves_table_content(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        table = "| Name | Score |\n| - | - |\n| Alice | 95 |"
        result = narrate_structured(table, "markitdown")
        assert "Alice" in result
        assert "95" in result


class TestXlsxNarration:
    """XLSX Docling output → markdown with headings."""

    def test_adds_heading_to_docling_table(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        table = "| Août 2026 Calendrier |\n| - |\n| Lundi | Mardi |"
        result = narrate_structured(table, "docling")
        assert "## " in result or "# " in result


class TestQualityGateImprovement:
    """Narrated output should pass quality gate."""

    def test_json_narrated_has_headings(self):
        from lore_mcp.preprocess.narrate import narrate_structured
        from lore_mcp.preprocess.validate import quality_gate
        import tempfile
        from pathlib import Path

        data = json.dumps({"name": "World Cup 2022", "matches": [
            {"round": "Matchday 1", "team1": "Qatar", "team2": "Ecuador",
             "score": "0-2", "date": "2022-11-20"},
            {"round": "Matchday 2", "team1": "England", "team2": "Iran",
             "score": "6-2", "date": "2022-11-21"},
        ]})
        result = narrate_structured(data, "json")
        tmp = Path(tempfile.mktemp(suffix=".md"))
        tmp.write_text(result)
        qg = quality_gate(str(tmp))
        tmp.unlink()
        assert qg["heading_count"] > 0, f"No headings: {qg}"
        assert qg["structure_score"] > 0, f"Zero structure: {qg}"
