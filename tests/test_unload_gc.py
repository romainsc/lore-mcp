"""Tests for E10.16: gc.collect in unload."""

from unittest.mock import patch, MagicMock
import pytest

from lore_mcp.embedder import Embedder


class TestUnloadGarbageCollection:
    def test_gc_collect_called_before_empty_cache(self):
        """gc.collect must run before torch.cuda.empty_cache."""
        emb = Embedder(mode="builtin:cpu")
        emb._model = MagicMock()

        call_order = []
        with patch("lore_mcp.embedder.gc") as mock_gc, \
             patch("lore_mcp.embedder.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            mock_gc.collect.side_effect = lambda: call_order.append("gc")
            mock_torch.cuda.empty_cache.side_effect = lambda: call_order.append("cache")

            emb.unload()

            assert call_order == ["gc", "cache"]

    def test_model_none_after_unload(self):
        emb = Embedder(mode="builtin:cpu")
        emb._model = MagicMock()
        emb.unload()
        assert emb._model is None

    def test_api_dim_cleared(self):
        emb = Embedder(mode="api", api_url="http://localhost/v1/embeddings")
        emb._api_dim = 768
        emb.unload()
        assert emb._api_dim is None
