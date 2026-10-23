"""Explicit, bounded, SSRF-guarded source fetching.

Every request: validated URL (public hosts only), DNS resolved to public
IPs, connection **pinned** to a pre-validated IP (closes the DNS-rebinding
TOCTOU: the socket connects to the IP we validated, while Host header and
TLS SNI still carry the original hostname), redirect targets re-validated
**and re-pinned per hop** (no separate validate-then-reconnect window),
timeout, size cap, scheme allowlist, no credential leaks, TLS verification
on. Never crawls. Never submits case data anywhere.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urljoin

import httpx

from tracefield.config import Settings
from tracefield.core.domain import AccessMethod, Source, SourceType, utcnow
from tracefield.core.provenance import hash_bytes
from tracefield.security import UrlPolicyError, validate_fetch_url
from tracefield.security.redact import redact_secrets
from tracefield.security.urls import validate_host

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class FetchError(Exception):
    """A fetch failed safely; the caller must preserve the URL + error."""


def _pinned_url_and_extensions(
    url: str,
) -> tuple[str, dict[str, str], list[str]]:
    """Resolve ``url``'s host, validate every address is public, and return
    a rewritten URL that connects to the first validated IP while preserving
    the original hostname for the Host header and TLS SNI.

    Returns (url_with_ip_host, extensions, candidate_ips). Raises
    UrlPolicyError or FetchError.
    """
    parts = httpx.URL(url)
    host = parts.host
    if not host:
        raise UrlPolicyError("URL has no host")
    addrs = validate_host(host)  # raises on any non-public address
    ip = addrs[0]
    ip_host = f"[{ip}]" if isinstance(ip, ipaddress.IPv6Address) else str(ip)
    # Rebuild URL with the IP as the connect target.
    port = parts.port
    pinned = str(parts.copy_with(host=ip_host, port=port))
    extensions: dict[str, str] = {"sni_hostname": host}
    candidates = [str(a) for a in addrs]
    return pinned, extensions, candidates


def _headers_for(host: str) -> dict[str, str]:
    return {
        "Host": host,
        "User-Agent": "tracefield/0.1 (+https://github.com/killerdasher/TRACEFIELD)",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }


def _iter_public_addrs(hostname: str) -> list[str]:
    try:
        return [str(a) for a in validate_host(hostname)]
    except UrlPolicyError:
        return []


def fetch_source(source: Source, settings: Settings) -> Source:
    """Fetch ``source.locator`` and return a new Source with collection
    metadata. Never fabricates a snapshot on failure — raises FetchError.

    The caller (CLI) is responsible for preserving the original source
    record with the error note.
    """
    original_url = validate_fetch_url(source.locator)  # raises if bad
    hostname = httpx.URL(original_url).host or ""
    if not hostname:
        raise FetchError("URL has no host")

    # Redirects are handled manually (client follow_redirects=False) so that
    # EVERY hop is re-validated by the URL policy and re-pinned to a freshly
    # validated IP in the same call that connects to it. A redirect to a
    # private/metadata/CGNAT target, or to a hostname that now resolves
    # non-public, raises UrlPolicyError exactly like hop 1. This removes the
    # validate-then-connect DNS-rebinding window that existed on redirect
    # hops when httpx re-resolved DNS itself after our hook had finished
    # (audit finding F1; risk A3 residual).
    max_hops = max(1, settings.max_redirects)
    hop_url = original_url
    hop_host = hostname
    status = 0
    content_type = ""
    body = b""
    final_url = original_url

    try:
        with httpx.Client(
            follow_redirects=False,  # we re-pin each hop ourselves
            timeout=settings.max_fetch_timeout_s,
            trust_env=False,  # do not inherit ambient proxy settings/credentials
        ) as client:
            for _hop in range(max_hops + 1):
                # Resolve + pin this hop: the socket will connect to an IP
                # validated right here, not to whatever DNS says later.
                pinned_url, extensions, _candidates = _pinned_url_and_extensions(hop_url)
                with client.stream(
                    "GET",
                    pinned_url,
                    extensions=extensions,
                    headers=_headers_for(hop_host),
                ) as resp:
                    status = resp.status_code
                    if status in _REDIRECT_STATUSES:
                        location = resp.headers.get("location", "")
                        if not location:
                            raise FetchError(f"redirect without Location (HTTP {status})")
                        # Validate + normalise the redirect target through
                        # the same policy as the original URL before we
                        # spend a connection on it.
                        hop_url = validate_fetch_url(urljoin(hop_url, location))
                        hop_host = httpx.URL(hop_url).host or hop_host
                        continue
                    # Terminal response: classify, then stream with cap.
                    if status in (429, 403):
                        raise FetchError(
                            f"provider refused access (HTTP {status}); "
                            "not retrying, not circumventing"
                        )
                    if status >= 500:
                        raise FetchError(f"provider error (HTTP {status})")
                    if status >= 400:
                        raise FetchError(f"HTTP {status}")

                    content_type = resp.headers.get("content-type", "")
                    chunks: list[bytes] = []
                    received = 0
                    for chunk in resp.iter_bytes():
                        received += len(chunk)
                        if received > settings.max_fetch_bytes:
                            raise FetchError(
                                f"response exceeded size limit ({settings.max_fetch_bytes} bytes)"
                            )
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    final_url = hop_url
                    break
            else:
                raise FetchError("too many redirects")
    except httpx.TimeoutException as exc:
        raise FetchError("request timed out") from exc
    except httpx.HTTPError as exc:
        raise FetchError(redact_secrets(str(exc))) from exc
    except UrlPolicyError:
        raise

    title = _extract_title(body, content_type) if body else ""
    new = source.model_copy(
        update={
            "locator": final_url,
            "access_method": AccessMethod.FETCHED,
            "source_type": SourceType.WEB_PAGE,
            "collected_at": utcnow(),
            "collection_agent": "tracefield/0.1",
            "limitations": redact_secrets(
                f"final_url={final_url}; http={status}; "
                f"content_type={content_type or 'unknown'}; "
                f"sha256={hash_bytes(body)}"
            ),
        }
    )
    if title:
        new.limitations = f"title={title[:200]}; " + new.limitations
    return new


def _replace_host(url: str, host: str) -> str:
    """Replace the host portion of ``url`` (which may be a pinned IP) with
    ``host`` for display/attribution purposes."""
    parts = httpx.URL(url)
    try:
        rebuilt = parts.copy_with(host=host)
        return str(rebuilt)
    except Exception:
        return url


def _extract_title(body: bytes, content_type: str) -> str:
    """Small HTML title extractor; never executes content."""
    if "html" not in content_type.lower() and b"<html" not in body[:512].lower():
        return ""
    import re

    window = body[:200_000]
    m = re.search(rb"<title[^>]*>(.*?)</title>", window, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    title = re.sub(rb"<[^>]+>", b"", m.group(1))
    return title.decode("utf-8", errors="replace").strip()


__all__ = ["FetchError", "_iter_public_addrs", "fetch_source"]
