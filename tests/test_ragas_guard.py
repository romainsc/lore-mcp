"""Tests for E10.19: RAGAS bidirectional guard."""

import logging
from unittest.mock import patch

import pytest


class TestRagasGuardWarning:
    def test_warn_judge_without_ragas_metrics(self, caplog):
        """Judge configured but no RAGAS metrics → warning."""
        from lore_mcp.eval import check_ragas_guard
        with caplog.at_level(logging.WARNING):
            check_ragas_guard(
                metrics=["score_spread", "mrr"],
                judge_url="http://localhost:11434/v1",
                judge_model="granite-8b",
            )
        assert "judge" in caplog.text.lower()

    def test_no_warn_without_judge(self, caplog):
        """No judge, no RAGAS metrics → no warning."""
        from lore_mcp.eval import check_ragas_guard
        with caplog.at_level(logging.WARNING):
            check_ragas_guard(
                metrics=["score_spread"],
                judge_url="",
                judge_model="",
            )
        assert "judge" not in caplog.text.lower()


class TestRagasGuardError:
    def test_error_ragas_metrics_without_judge(self):
        """RAGAS metrics requested without judge → error."""
        from lore_mcp.eval import check_ragas_guard
        with pytest.raises(ValueError, match="judge"):
            check_ragas_guard(
                metrics=["faithfulness"],
                judge_url="",
                judge_model="",
            )

    def test_error_ragas_not_installed(self):
        """RAGAS metrics with judge but ragas not installed → error."""
        from lore_mcp.eval import check_ragas_guard
        with patch.dict("sys.modules", {"ragas": None}):
            with pytest.raises(ImportError, match="ragas"):
                check_ragas_guard(
                    metrics=["faithfulness"],
                    judge_url="http://localhost/v1",
                    judge_model="granite-8b",
                )

    def test_ok_ragas_metrics_with_judge(self):
        """RAGAS metrics with judge and ragas installed → OK."""
        from lore_mcp.eval import check_ragas_guard
        check_ragas_guard(
            metrics=["score_spread", "mrr"],
            judge_url="http://localhost/v1",
            judge_model="granite-8b",
        )

    def test_error_judge_unreachable(self):
        """RAGAS metrics with unreachable judge → ConnectionError."""
        from lore_mcp.eval import check_ragas_guard, _apply_ragas_stub
        _apply_ragas_stub()
        with pytest.raises(ConnectionError, match="unreachable"):
            check_ragas_guard(
                metrics=["faithfulness"],
                judge_url="http://192.0.2.1:9999/v1",
                judge_model="granite-8b",
            )


class TestRagasGuardInOptimize:
    def test_optimize_calls_guard(self):
        """run_optimize must call check_ragas_guard when RAGAS metrics requested."""
        from lore_mcp.eval import run_optimize
        with patch("lore_mcp.eval.check_ragas_guard") as mock_guard:
            mock_guard.side_effect = ConnectionError("judge unreachable")
            with pytest.raises(ConnectionError):
                run_optimize(
                    embedder=None,
                    embedders={"test": object()},
                    metrics=["faithfulness"],
                    judge_url="http://192.0.2.1:9999/v1",
                    judge_model="granite-8b",
                )
