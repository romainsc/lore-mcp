"""Tests for lore_mcp.collections. See docs/architecture.md."""


class TestCollectionPath:
    def test_collection_db_path(self, tmp_path):
        from lore_mcp.collections import collection_db_path

        path = collection_db_path(str(tmp_path), "docs-libre")
        assert path.endswith("docs-libre.db")
