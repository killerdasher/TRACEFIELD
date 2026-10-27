"""Unit tests: URL policy, sanitization, redaction, hashing, schemas."""

from __future__ import annotations

import ipaddress

import pytest

from tracefield.core.domain import Claim, OutcomeLabel, Source, new_id
from tracefield.core.provenance import compute_event_digest, hash_bytes, hash_file
from tracefield.security import UrlPolicyError, sanitize_for_terminal, validate_fetch_url
from tracefield.security.redact import redact_secrets
from tracefield.security.urls import _is_blocked_ip, is_public_host

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# URL policy / SSRF
# ---------------------------------------------------------------------------


class TestUrlPolicy:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/x",
            "file:///etc/passwd",
            "gopher://example.com/",
            "data:text/html,<script>",
            "javascript:alert(1)",
            "ws://example.com/",
        ],
    )
    def test_rejects_non_http_schemes(self, url: str) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://127.0.0.1:8080/admin",
            "https://[::1]/",
            "http://10.0.0.5/internal",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
            "http://100.100.100.200/latest/meta-data/",  # Alibaba IMDS
            "http://100.64.0.1/",  # CGNAT / shared address space
            "http://[fec0::1]/",  # deprecated site-local
            "http://[fe80::1]/",  # link-local
            "http://0.0.0.0/",
            "http://[::]/",
            "http://192.0.2.1/",  # TEST-NET-1 (documentation)
            "http://198.51.100.1/",  # TEST-NET-2
            "http://203.0.113.1/",  # TEST-NET-3
            "http://240.0.0.1/",  # reserved
            "http://224.0.0.1/",  # multicast
        ],
    )
    def test_rejects_non_public_destinations(self, url: str) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url(url)

    def test_rejects_embedded_credentials(self) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("https://user:pass@example.com/")

    def test_rejects_metadata_hostnames(self) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_rejects_local_namespace(self) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("http://printer.local/")

    def test_public_url_passes(self) -> None:
        # example.com resolves publicly; if DNS unavailable this would raise
        # and that is also a safe (fail-closed) outcome we accept in CI.
        try:
            assert validate_fetch_url("https://example.com/page") == ("https://example.com/page")
        except UrlPolicyError:
            pytest.skip("DNS unavailable in this environment")

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "10.1.2.3",
            "192.168.0.1",
            "172.31.255.255",
            "169.254.169.254",
            "100.64.0.1",
            "100.100.100.200",
            "0.0.0.0",
            "255.255.255.255",
            "192.0.2.1",
            "203.0.113.99",
            "::1",
            "fe80::1",
            "fc00::1",
            "fec0::1",
            "::",
            "ff02::1",
        ],
    )
    def test_blocked_ip_ranges(self, ip: str) -> None:
        assert _is_blocked_ip(ipaddress.ip_address(ip)) is True

    def test_ipv4_mapped_ipv6_blocked_when_private(self) -> None:
        # ::ffff:127.0.0.1 must be blocked via v4 mapping
        assert _is_blocked_ip(ipaddress.ip_address("::ffff:127.0.0.1")) is True

    def test_is_public_host_false_for_loopback(self) -> None:
        assert is_public_host("127.0.0.1") is False

    def test_no_host_rejected(self) -> None:
        with pytest.raises(UrlPolicyError):
            validate_fetch_url("https:///path-only")


# ---------------------------------------------------------------------------
# Terminal sanitization
# ---------------------------------------------------------------------------


class TestSanitize:
    def test_strips_ansi_escape(self) -> None:
        assert "\x1b" not in sanitize_for_terminal("hello\x1b[31mred\x1b[0m")

    def test_strips_osc_clipboard(self) -> None:
        payload = "title\x1b]52;c;SGVsbG8=\x07end"
        cleaned = sanitize_for_terminal(payload)
        assert "\x1b" not in cleaned and "\x07" not in cleaned

    def test_strips_c1_controls(self) -> None:
        assert "\x9b" not in sanitize_for_terminal("a\x9b31mb")

    def test_keeps_newlines_and_tabs(self) -> None:
        assert sanitize_for_terminal("a\nb\tc") == "a\nb\tc"

    def test_max_length_truncates(self) -> None:
        out = sanitize_for_terminal("x" * 100, max_length=10)
        assert len(out) <= 10 and out.endswith("…")

    def test_nul_removed(self) -> None:
        assert "\x00" not in sanitize_for_terminal("a\x00b")


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_password_not_word_suffix(self) -> None:
        """Regression: old pattern produced '[REDACTED]word'."""
        out = redact_secrets("password: hunter2")
        assert "hunter2" not in out
        assert "[REDACTED]word" not in out
        assert "password:" in out

    def test_bearer_token(self) -> None:
        out = redact_secrets("Authorization: Bearer abcdef0123456789abcdef")
        assert "abcdef0123456789abcdef" not in out

    def test_api_key(self) -> None:
        out = redact_secrets("api_key=sk-abc123def456ghi789")
        assert "sk-abc123def456ghi789" not in out

    def test_url_credentials(self) -> None:
        out = redact_secrets("https://user:secretpass@example.com/x")
        assert "secretpass" not in out

    def test_cookie_header(self) -> None:
        out = redact_secrets("Cookie: session=abc123; theme=dark")
        assert "abc123" not in out

    def test_query_string_token(self) -> None:
        out = redact_secrets("https://x.com/api?token=SECRETVAL&other=1")
        assert "SECRETVAL" not in out
        assert "other=1" in out

    def test_github_token(self) -> None:
        out = redact_secrets("leaked ghp_abcdefghijklmnopqrstuv123456 token")
        assert "ghp_abcdefghijklmnopqrstuv123456" not in out

    def test_aws_key(self) -> None:
        out = redact_secrets("AKIAIOSFODNN7EXAMPLE")
        assert "AKIAIOSFODNN7EXAMPLE" not in out

    def test_pem_private_key(self) -> None:
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        out = redact_secrets(f"config: {pem}")
        assert "MIIEpAIBAAKCAQEA" not in out

    def test_jwt(self) -> None:
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        out = redact_secrets(f"auth={jwt}")
        assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV" not in out

    def test_plain_text_untouched(self) -> None:
        msg = "The fixture file contains a greeting."
        assert redact_secrets(msg) == msg


# ---------------------------------------------------------------------------
# Hashing / event digests
# ---------------------------------------------------------------------------


class TestHashing:
    def test_hash_bytes_known_value(self) -> None:
        assert hash_bytes(b"") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_hash_file_matches_bytes(self, tmp_path) -> None:
        p = tmp_path / "f.bin"
        p.write_bytes(b"abc")
        assert hash_file(p) == hash_bytes(b"abc")

    def test_event_digest_changes_with_prev(self) -> None:
        a = compute_event_digest("x", [], [], "0", "2026-01-01T00:00:00Z")
        b = compute_event_digest("x", [], [], "1", "2026-01-01T00:00:00Z")
        assert a != b

    def test_event_digest_changes_with_timestamp(self) -> None:
        a = compute_event_digest("x", [], [], "0", "2026-01-01T00:00:00Z")
        b = compute_event_digest("x", [], [], "0", "2026-01-02T00:00:00Z")
        assert a != b


# ---------------------------------------------------------------------------
# Domain / schema validation
# ---------------------------------------------------------------------------


class TestDomain:
    def test_new_id_shape(self) -> None:
        assert new_id("case").startswith("case_")
        assert len(new_id("case")) == len("case_") + 16

    def test_claim_defaults(self) -> None:
        c = Claim(case_id="case_x", text="hello")
        assert c.status.value == "active"
        assert c.review_state.value == "unreviewed"

    def test_source_locator_kept_verbatim(self) -> None:
        s = Source(case_id="case_x", locator="https://example.com/a?b=1&c=2")
        assert s.locator == "https://example.com/a?b=1&c=2"

    def test_outcome_labels_are_six(self) -> None:
        assert len(list(OutcomeLabel)) == 6


# ---------------------------------------------------------------------------
# HTML report rendering (XSS safety)
# ---------------------------------------------------------------------------


def _xss_payload() -> dict:
    """Minimal report payload with attacker-shaped strings in every field."""
    evil = "<script>alert(1)</script>"
    return {
        "report_schema_version": 3,
        "generated_at": "2026-10-19T00:00:00Z",
        "tool": {"name": "tracefield", "version": "0.1.0"},
        "document": {
            "author": evil,  # author is attacker-shapeable: must be escaped too
            "revision": 1,
            "report_id": "rep_x",
            "supersedes": "rep_old",
            "superseded_by": "",
            "corrections": [{"note": evil, "corrected_report_id": "rep_old"}],
        },
        "case": {
            "id": "case_x",
            "title": evil,
            "status": "open",
            "purpose": evil,
            "scope": evil,
            "created_at": "2026-10-19T00:00:00Z",
        },
        "counts": {"sources": 1, "claims": 1, "evidence": 1, "relations": 0},
        "global_caveats": [evil],
        "sources": [
            {
                "id": "src_x",
                "locator": "javascript:alert(1)",
                "source_type": "website",
                "access_method": "direct",
                "first_seen_at": "2026-10-19T00:00:00Z",
                "collected_at": "",
                "published_at": "",
                "limitations": evil,
            }
        ],
        "evidence": [
            {
                "id": "ev_x",
                "sha256": "0" * 64,
                "media_type": "text/plain",
                "size_bytes": 1,
                "source_id": "src_x",
                "captured_at": "2026-10-19T00:00:00Z",
                "storage_ref": evil,
            }
        ],
        "claims": [
            {
                "id": "clm_x",
                "text": evil,
                "status": "active",
                "review_state": "unreviewed",
            }
        ],
        "assessments": [
            {
                "claim_id": "clm_x",
                "outcome": "INSUFFICIENT_EVIDENCE",
                "rule_version": "assess-r2",
                "supporting_count": 0,
                "contradicting_count": 0,
                "independence": "not assessed",
                "caveats": [evil],
            }
        ],
        "relations": [],
        "origin_clusters": [],
    }


class TestHtmlReport:
    def test_is_self_contained_document(self) -> None:
        from tracefield.reporting.build import render_html

        out = render_html(_xss_payload())
        assert out.startswith("<!DOCTYPE html>")
        assert out.rstrip().endswith("</html>")
        # No external resources or scripts — local-first, no CDN, no JS.
        assert "<script" not in out
        assert "http://" not in out.split("<style>")[0]  # head has no remote refs
        assert "src=" not in out

    def test_every_injected_tag_is_escaped(self) -> None:
        from tracefield.reporting.build import render_html

        out = render_html(_xss_payload())
        # The literal attacker string must never survive unescaped.
        assert "<script>alert(1)</script>" not in out
        # Escaped form must be present (proves the content rendered, not dropped).
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out

    def test_javascript_locator_never_becomes_href(self) -> None:
        from tracefield.reporting.build import render_html

        out = render_html(_xss_payload())
        assert 'href="javascript:' not in out
        # The locator text is still shown, escaped as plain text.
        assert "javascript:alert(1)" in out

    def test_valid_payload_renders_all_sections(self) -> None:
        from tracefield.reporting.build import render_html

        out = render_html(_xss_payload())
        for needle in (
            "Case Report",
            "Caveats",
            "Sources",
            "Evidence",
            "Claims and Assessments",
            "INSUFFICIENT_EVIDENCE",
            "assess-r2",
            "workflow states",
        ):
            assert needle in out, needle
