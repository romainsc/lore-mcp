"""Tests for inference service lifecycle. See E12.25."""

from lore_mcp.preprocess.service import (
    start_service, stop_service, check_service,
    _health_url, _models_url,
)


class TestStartService:

    def test_no_start_command_is_noop(self):
        start_service({"api_url": "http://localhost:9999"})

    def test_empty_entry_is_noop(self):
        start_service({})


    def test_start_command_failure_raises_immediately(self):
        """E12.149: bad start command must fail fast, not wait for timeout."""
        import pytest
        entry = {
            "start": "/nonexistent/script/that/does/not/exist.sh",
            "api_url": "http://127.0.0.1:19998",
        }
        with pytest.raises(RuntimeError, match="Start command failed"):
            start_service(entry, timeout=10)

    def test_start_command_failure_includes_details(self):
        """E12.149: error message must include command and stderr."""
        import pytest
        entry = {
            "start": "echo 'startup error' >&2 && exit 1",
            "api_url": "http://127.0.0.1:19998",
        }
        with pytest.raises(RuntimeError, match="startup error"):
            start_service(entry, timeout=10)


class TestStopService:

    def test_no_stop_command_is_noop(self):
        stop_service({"api_url": "http://localhost:9999"})

    def test_empty_entry_is_noop(self):
        stop_service({})


class TestCheckService:

    def test_unreachable_returns_false(self):
        assert check_service({"api_url": "http://127.0.0.1:19999"}) is False

    def test_no_url_returns_false(self):
        assert check_service({}) is False

    def test_empty_url_returns_false(self):
        assert check_service({"api_url": ""}) is False


class TestUrlDerivation:

    def test_health_url_with_v1(self):
        assert _health_url("http://localhost:8090/v1") == "http://localhost:8090/health"

    def test_health_url_without_v1(self):
        assert _health_url("http://localhost:8090") == "http://localhost:8090/health"

    def test_models_url_with_v1(self):
        assert _models_url("http://localhost:8090/v1") == "http://localhost:8090/v1/models"

    def test_models_url_without_v1(self):
        assert _models_url("http://localhost:8090") == "http://localhost:8090/v1/models"

    def test_models_url_with_trailing_slash(self):
        assert _models_url("http://localhost:8090/v1/") == "http://localhost:8090/v1/models"
