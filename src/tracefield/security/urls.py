"""Fetch-time URL safety policy.

Only http/https are allowed. Destinations must resolve exclusively to
*globally routable* addresses: loopback, private, link-local, CGNAT,
multicast, reserved, unspecified, documentation, benchmark, and cloud
metadata ranges are all rejected via ``ipaddress.is_global`` (which is
strictly stronger than ``is_private``). DNS is resolved and every address
must pass; the caller re-validates each redirect. Fails closed.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

# Cloud metadata endpoints that must never be contacted, by hostname.
BLOCKED_HOSTNAMES = frozenset(
    {
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
        "instance-data",
    }
)

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UrlPolicyError(ValueError):
    """Raised when a URL violates the fetch safety policy."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Fail closed: only globally routable unicast addresses pass.

    Explicit deny first — ``ipaddress.is_global`` alone misses some
    categories (it reports multicast 224.0.0.1 / ff02::1 and deprecated
    IPv6 site-local fec0::/10 as "global"), so those are checked
    directly, then ``is_global`` closes the remaining set: loopback,
    private (RFC1918/ULA), link-local, CGNAT (100.64/10), reserved,
    unspecified, documentation, benchmark, shared-address — covering
    cloud metadata ranges like 169.254.169.254 and 100.100.100.200.
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if isinstance(ip, ipaddress.IPv6Address) and ip.sixtofour is not None:
        ip = ip.sixtofour
    if isinstance(ip, ipaddress.IPv6Address) and ip.teredo is not None:
        return True  # do not trust tunneled Teredo destinations
    try:
        if (
            ip.is_multicast
            or ip.is_unspecified
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_private
        ):
            return True
        if isinstance(ip, ipaddress.IPv6Address) and ip in ipaddress.IPv6Network("fec0::/10"):
            return True  # deprecated site-local; is_global misses it
        return not ip.is_global
    except Exception:
        return True


def resolve_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve ``host`` to a list of IP addresses. Raises UrlPolicyError on
    failure so callers fail closed rather than guessing."""
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UrlPolicyError(f"DNS resolution failed for host {host!r}") from exc
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        if not isinstance(ip_str, str):
            continue
        if ip_str in seen:
            continue
        seen.add(ip_str)
        try:
            addrs.append(ipaddress.ip_address(ip_str))
        except ValueError as ip_err:
            raise UrlPolicyError(f"unparseable address {ip_str!r} for {host!r}") from ip_err
    if not addrs:
        raise UrlPolicyError(f"No addresses resolved for host {host!r}")
    return addrs


def validate_host(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Validate a hostname and return its resolved public addresses.

    Raises UrlPolicyError if the host is blocked, resolves to a non-public
    address, or fails to resolve. Fails closed.
    """
    host_l = host.lower().rstrip(".")
    if not host_l:
        raise UrlPolicyError("URL has no host")
    if host_l in BLOCKED_HOSTNAMES:
        raise UrlPolicyError(f"Host {host!r} is a blocked metadata endpoint")
    if host_l.endswith(".local") or host_l.endswith(".internal"):
        raise UrlPolicyError(f"Host {host!r} resolves to a non-public namespace")
    addrs = resolve_addresses(host_l)
    for ip in addrs:
        if _is_blocked_ip(ip):
            raise UrlPolicyError(
                f"Host {host!r} resolves to a non-public address ({ip}); refusing to fetch"
            )
    return addrs


def validate_fetch_url(url: str) -> str:
    """Validate ``url`` against the fetch policy; return it unchanged if safe.

    Raises :class:`UrlPolicyError` on any violation. Fails closed when the
    destination cannot be determined with confidence.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UrlPolicyError(
            f"Scheme {parts.scheme!r} is not permitted; only http and https are allowed"
        )
    if parts.username or parts.password:
        raise UrlPolicyError("URLs embedding credentials are not permitted")
    host = parts.hostname
    if not host:
        raise UrlPolicyError("URL has no host")
    validate_host(host)
    return url


def is_public_host(host: str) -> bool:
    """True when every resolved address for ``host`` is a public IP."""
    try:
        validate_host(host)
        return True
    except UrlPolicyError:
        return False
