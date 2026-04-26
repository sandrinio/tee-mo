"""URL safety helper — STORY-012-01 (EPIC-012 MCP Service Layer).

Lifted from the private ``_is_safe_url()`` in ``app/agents/agent.py`` (lines
69-94, sprint S-17). This module is the single source of truth for HTTPS +
private-IP validation across both the MCP service layer and the existing
``http_request`` agent tool.

Exports:
    is_safe_url(url: str) -> tuple[bool, str | None]

The original ``_is_safe_url`` returned ``bool``; this richer form returns
``(False, reason)`` on failure so callers can surface a human-readable message.
The ``http_request`` tool callsite adapts by ignoring the reason field when it
wants to preserve the legacy error string.

Behavioural parity guarantee (regression test in tests/core/test_url_safety.py
and tests/test_agent_factory.py):
  - All IPs blocked by the original ``_BLOCKED_NETWORKS`` list remain blocked.
  - DNS resolution logic is identical (``socket.getaddrinfo``).
  - A URL with no hostname still returns ``(False, ...)``.
  - A ``socket.gaierror`` (DNS failure) still returns ``(False, ...)``.
"""

import ipaddress
import socket
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Private CIDR block list — mirrors the one formerly in agent.py verbatim.
# ---------------------------------------------------------------------------

_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network(cidr)
    for cidr in [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fd00::/8",
        "fe80::/10",
    ]
]


def is_safe_url(url: str) -> tuple[bool, str | None]:
    """Check that a URL is safe to connect to.

    Validates:
    1. Scheme is ``https`` (not http, ftp, etc.).
    2. Hostname resolves to at least one IP address.
    3. Every resolved IP is public (not in the blocked CIDR list).

    Args:
        url: Fully-qualified URL to check.

    Returns:
        ``(True, None)`` when the URL passes all checks.
        ``(False, reason)`` where ``reason`` is a human-readable error string:
          - ``"HTTPS required"`` — scheme is not https.
          - ``"no hostname"`` — URL cannot be parsed to a hostname.
          - ``"hostname did not resolve"`` — DNS lookup failed (gaierror).
          - ``"unsafe URL: <ip> in private range"`` — resolved to a blocked IP.
    """
    parsed = urlparse(url)

    # Scheme check — MCP and http_request both require HTTPS.
    if parsed.scheme != "https":
        return False, "HTTPS required"

    hostname = parsed.hostname
    if not hostname:
        return False, "no hostname"

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, "hostname did not resolve"

    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        if any(ip in net for net in _BLOCKED_NETWORKS):
            return False, f"unsafe URL: {ip} in private range"

    return True, None
