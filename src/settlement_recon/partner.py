"""Bounded partner HTTP ingestion. Operators configure allowed hosts explicitly."""

import time
from urllib.parse import urlsplit

import httpx

from settlement_recon.domain import MAX_BYTES, DomainError, Reconciler


def pull_partner(
    service: Reconciler,
    url: str,
    token: str,
    allowed_hosts: set[str],
    client: httpx.Client | None = None,
    sleep=time.sleep,
) -> dict:
    target = urlsplit(url)
    local = target.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        target.hostname not in allowed_hosts
        or target.username
        or target.password
        or target.fragment
        or (target.scheme != "https" and not (local and target.scheme == "http"))
    ):
        raise DomainError("Partner URL must use HTTPS and an explicitly allowed host")
    if not token or "\n" in token or "\r" in token:
        raise DomainError("Invalid partner credential configuration")
    owned = client is None
    client = client or httpx.Client(timeout=5, follow_redirects=False, trust_env=False)
    try:
        for attempt in range(3):
            try:
                with client.stream(
                    "GET",
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                    follow_redirects=False,
                ) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.TransportError("Transient upstream failure")
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        if len(content) + len(chunk) > MAX_BYTES:
                            raise DomainError("Partner payload exceeds maximum size", "size")
                        content.extend(chunk)
                    return service.ingest("payments", "partner-api", bytes(content))
            except httpx.TransportError:
                if attempt == 2:
                    raise OSError("Partner unavailable after three attempts") from None
                sleep(0.25 * 2**attempt)
            except httpx.HTTPStatusError:
                raise OSError("Partner rejected request") from None
    finally:
        if owned:
            client.close()
    raise OSError("Partner ingestion failed")
