import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional, Tuple
import httpx

from app.core.exceptions import SSRFSecurityException

# Blocked IP Networks for SSRF Prevention
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),       # Link-local / AWS metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),          # Multicast
    ipaddress.ip_network("240.0.0.0/4"),          # Reserved
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6 blocks
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),              # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),             # Unique local address
    ipaddress.ip_network("fe80::/10"),            # Link-local
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "instance-data",
}

MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 Megabytes limit
DEFAULT_TIMEOUT = 10.0  # seconds


def validate_url_safety(url: str) -> Tuple[str, str]:
    """
    Validates that a URL is safe to fetch:
    1. HTTP/HTTPS schemes only
    2. Hostname is not in blocked list
    3. Resolved IP is not private, loopback, or cloud metadata
    Returns (cleaned_url, hostname)
    Raises SSRFSecurityException on any violation.
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityException("Empty or invalid URL provided.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise SSRFSecurityException(f"Unsupported protocol scheme '{parsed.scheme}'. Only HTTP/HTTPS allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityException("URL is missing a valid hostname.")

    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        raise SSRFSecurityException(f"Access to blocked host '{hostname}' is forbidden.")

    # Try resolving hostname to IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFSecurityException(f"DNS resolution failed for '{hostname}': {str(e)}")

    for info in addr_info:
        ip_str = info[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFSecurityException(f"Invalid resolved IP '{ip_str}'")

        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
            raise SSRFSecurityException(f"Target host '{hostname}' resolves to private/internal IP {ip_str}.")

        for net in BLOCKED_NETWORKS:
            if ip_obj in net:
                raise SSRFSecurityException(f"Target host resolves to restricted IP range {net}.")

    return url.strip(), hostname_lower


async def safe_fetch_url(
    url: str,
    timeout_seconds: float = DEFAULT_TIMEOUT,
    follow_redirects: bool = True,
    max_redirects: int = 3,
) -> Tuple[int, str, dict, float]:
    """
    Safely fetches a web page with:
    - SSRF pre-check
    - Timeout protection
    - Max response size cap
    - Safe redirect verification
    Returns (status_code, html_content, headers, response_time_ms)
    """
    clean_url, _ = validate_url_safety(url)

    transport = httpx.AsyncHTTPTransport(retries=1)
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(timeout_seconds),
        verify=False,  # Allow sites with self-signed certs for business inspection
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 LeadIntelligenceBot/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    ) as client:
        import time
        start_time = time.time()

        # Follow redirects manually up to max_redirects to check SSRF at each step
        current_url = clean_url
        response = None
        for _ in range(max_redirects + 1):
            validate_url_safety(current_url)
            req = client.build_request("GET", current_url)
            resp = await client.send(req, stream=True)

            if resp.is_redirect and follow_redirects and "location" in resp.headers:
                location = resp.headers["location"]
                from urllib.parse import urljoin
                current_url = urljoin(current_url, location)
                await resp.aclose()
                continue
            else:
                response = resp
                break

        if not response:
            raise SSRFSecurityException("Too many redirects.")

        elapsed_ms = (time.time() - start_time) * 1000.0

        try:
            content_bytes = bytearray()
            async for chunk in response.aiter_bytes():
                content_bytes.extend(chunk)
                if len(content_bytes) > MAX_RESPONSE_SIZE:
                    break  # Truncate rather than crash
            
            # Decode response text
            encoding = response.encoding or "utf-8"
            html_text = content_bytes.decode(encoding, errors="replace")
            headers_dict = dict(response.headers)
            status_code = response.status_code
        finally:
            await response.aclose()

        return status_code, html_text, headers_dict, elapsed_ms
