"""Tests for table protection. See E12.06."""

from lore_mcp.preprocess.tables import protect_tables, TABLE_SENTINEL_START, TABLE_SENTINEL_END


class TestProtectTables:

    def test_wraps_simple_table(self):
        text = "Before.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter."
        result = protect_tables(text)
        assert TABLE_SENTINEL_START in result
        assert TABLE_SENTINEL_END in result
        assert "| A | B |" in result

    def test_no_table_unchanged(self):
        text = "Just regular text.\n\nNo tables here."
        result = protect_tables(text)
        assert result == text
        assert TABLE_SENTINEL_START not in result

    def test_multiple_tables(self):
        text = (
            "Intro.\n\n| X |\n|---|\n| 1 |\n\n"
            "Middle.\n\n| Y |\n|---|\n| 2 |\n\nEnd."
        )
        result = protect_tables(text)
        assert result.count(TABLE_SENTINEL_START) == 2
        assert result.count(TABLE_SENTINEL_END) == 2

    def test_table_with_header_separator(self):
        text = "| Name | Value |\n|------|-------|\n| foo  | bar   |"
        result = protect_tables(text)
        assert TABLE_SENTINEL_START in result

    def test_preserves_surrounding_content(self):
        text = "Before paragraph.\n\n| A |\n|---|\n| 1 |\n\nAfter paragraph."
        result = protect_tables(text)
        assert "Before paragraph." in result
        assert "After paragraph." in result
