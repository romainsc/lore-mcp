"""Tests for batch size config."""

from lore_mcp.config import LoreConfig
from lore_mcp.ingest import get_batch_size


class TestBatchSizeConfig:
    def test_default(self):
        assert get_batch_size() == 64

    def test_from_config(self):
        cfg = LoreConfig(embedding_batch_size=32)
        assert get_batch_size(cfg) == 32

    def test_from_config_small(self):
        cfg = LoreConfig(embedding_batch_size=1)
        assert get_batch_size(cfg) == 1
