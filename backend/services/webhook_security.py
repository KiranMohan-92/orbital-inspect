"""Outbound webhook URL validation and SSRF guardrails."""

import ipaddress
import socket
from urllib.parse import urlparse

from config import settings

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _strict_webhook_security() -> bool:
    return settings.APP_ENV in {"staging", "production"} and not settings.DEMO_MODE


def _is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return True
    return any(address in network for network in _BLOCKED_NETWORKS)


def resolve_webhook_targets(hostname: str, port: int | None) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Webhook host could not be resolved: {hostname}") from exc

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        raw_address = info[4][0]
        address = ipaddress.ip_address(raw_address)
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError(f"Webhook host did not resolve to an IP address: {hostname}")
    return addresses


def validate_webhook_url(url: str, *, resolve_dns: bool = True) -> None:
    """Validate an outbound webhook URL before storage or dispatch."""
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Webhook URL must use HTTP(S)")
    if _strict_webhook_security() and parsed.scheme != "https":
        raise ValueError("Webhook URL must use HTTPS in staging and production")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("Webhook URL must include a hostname")
    if hostname in _BLOCKED_HOSTS:
        raise ValueError("Internal hosts are not allowed")

    allowlist = {host.lower() for host in settings.WEBHOOK_ALLOWED_HOSTS}
    if allowlist and hostname not in allowlist:
        raise ValueError("Webhook host is not in WEBHOOK_ALLOWED_HOSTS")

    if not resolve_dns and not _strict_webhook_security():
        return

    for address in resolve_webhook_targets(hostname, parsed.port):
        if _is_blocked_address(address):
            raise ValueError("Private/internal webhook targets are not allowed")
