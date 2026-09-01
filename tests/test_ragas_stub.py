"""Tests for E10.23: ragas import stub."""

import pytest


class TestRagasStub:
    def test_apply_stub_enables_ragas_import(self):
        """Stub allows ragas to import without crash."""
        from lore_mcp.eval import _apply_ragas_stub
        _apply_ragas_stub()
        import ragas
        assert hasattr(ragas, '__version__')

    def test_stub_idempotent(self):
        """Applying stub twice doesn't crash."""
        from lore_mcp.eval import _apply_ragas_stub
        _apply_ragas_stub()
        _apply_ragas_stub()

    def test_metrics_available_after_stub(self):
        """Faithfulness and ContextRecall accessible."""
        from lore_mcp.eval import _apply_ragas_stub
        _apply_ragas_stub()
        from ragas.metrics.collections import Faithfulness, ContextRecall
        assert Faithfulness is not None
        assert ContextRecall is not None
