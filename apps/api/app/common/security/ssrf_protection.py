"""
SSRF Protection Utility
=======================
Validates outbound URL targets to prevent Server-Side Request Forgery attacks.

Blocks:
  - Loopback (127.0.0.0/8, ::1)
  - Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  - Link-local (169.254.0.0/16, fe80::/10)
  - Metadata endpoints (AWS 169.254.169.254, GCP 169.254.169.254, Azure 169.254.169.254)
  - Non-HTTP(S) schemes
  - Missing or invalid hostnames

Used by:
  - CRM adapter outbound calls
  - Webhook dispatcher
  - Public API webhook registration
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ─── Private / Reserved IP Ranges ────────────────────────────────────────────

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),       # link-local / AWS metadata
    ipaddress.ip_network("100.64.0.0/10"),         # shared address space (RFC 6598)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("240.0.0.0/4"),           # reserved
    ipaddress.ip_network("::1/128"),               # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),              # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),             # IPv6 link-local
    ipaddress.ip_network("2001:db8::/32"),         # documentation
]

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.aws.internal",
}


class SSRFError(ValueError):
    """Raised when an outbound URL target is blocked by SSRF protection."""
    pass


def validate_outbound_url(
    url: str,
    allowed_schemes: tuple[str, ...] = ("https", "http"),
    require_https: bool = False,
) -> str:
    """
    Validates that `url` is safe to use as an outbound HTTP target.
    Raises SSRFError if the URL is blocked.
    Returns the URL unchanged if valid.

    Args:
        url: The URL to validate.
        allowed_schemes: Acceptable URL schemes. Defaults to https + http.
        require_https: If True, only https:// is permitted.

    Raises:
        SSRFError: If the URL is unsafe.
        ValueError: If the URL is malformed.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL must be a non-empty string.")

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise SSRFError(f"Malformed URL: {exc}") from exc

    # ── Scheme check ─────────────────────────────────────────────────────────
    scheme = (parsed.scheme or "").lower()
    if require_https and scheme != "https":
        raise SSRFError(f"Only HTTPS URLs are permitted. Got scheme='{scheme}'.")
    if scheme not in allowed_schemes:
        raise SSRFError(
            f"URL scheme '{scheme}' is not allowed. Permitted: {allowed_schemes}."
        )

    # ── Hostname check ────────────────────────────────────────────────────────
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL must include a hostname.")

    hostname_lower = hostname.lower()
    if hostname_lower in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"Hostname '{hostname}' is blocked (SSRF protection).")

    # ── IP resolution + range check ───────────────────────────────────────────
    try:
        # Direct IP address
        ip = ipaddress.ip_address(hostname)
        _check_ip_blocked(ip, hostname)
    except ValueError:
        # Not a literal IP — resolve to check
        try:
            addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            for _fam, _type, _proto, _canon, sockaddr in addr_infos:
                ip_str = sockaddr[0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    _check_ip_blocked(ip, hostname)
                except SSRFError:
                    raise
                except ValueError:
                    pass  # skip non-IP results
        except SSRFError:
            raise
        except (socket.gaierror, OSError):
            # DNS resolution failure — allow (let the HTTP client fail naturally)
            pass

    logger.debug(f"[SSRF] URL passed validation: {url}")
    return url


def _check_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    """Raises SSRFError if the IP falls in any blocked range."""
    for network in _BLOCKED_NETWORKS:
        try:
            if ip in network:  # type: ignore[operator]
                raise SSRFError(
                    f"URL resolves to a blocked IP address ({ip}) in network "
                    f"{network}. SSRF protection triggered for host='{hostname}'."
                )
        except TypeError:
            # IP version mismatch (IPv4 vs IPv6 network) — skip
            pass
