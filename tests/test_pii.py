"""Tests for PII detection. See E12.05."""

from lore_mcp.preprocess.pii import detect_pii


class TestDetectPII:

    def test_detects_email(self):
        findings = detect_pii("Contact john@company.fr for info.")
        assert any(f["type"] == "email" for f in findings)

    def test_detects_ip_v4(self):
        findings = detect_pii("Server at 192.168.1.100 is down.")
        assert any(f["type"] == "ip" for f in findings)

    def test_detects_api_key_pattern(self):
        findings = detect_pii("Use key sk-abc123def456ghi789jkl012mno345p")
        assert any(f["type"] == "api_key" for f in findings)

    def test_detects_internal_domain(self):
        findings = detect_pii("See docs at wiki.internal.corp.net")
        assert any(f["type"] == "internal_domain" for f in findings)

    def test_no_false_positive_on_clean_text(self):
        findings = detect_pii(
            "This is a normal technical document about "
            "machine learning and vector databases."
        )
        assert findings == []

    def test_no_false_positive_on_example_domains(self):
        findings = detect_pii("See example.com or test@example.org")
        assert findings == []

    def test_multiple_findings(self):
        text = "Email admin@corp.internal, server 10.0.0.1"
        findings = detect_pii(text)
        assert len(findings) >= 2

    def test_returns_match_and_line(self):
        findings = detect_pii("line1\nContact user@real.com here\nline3")
        assert findings[0]["match"] == "user@real.com"
        assert findings[0]["line"] == 2
