"""Attachment download with caching and rate limiting."""

import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Rate limit: min delay between requests per domain (seconds)
_RATE_LIMIT_DELAY = 1.0
_last_request_by_domain: dict[str, float] = {}


def _domain_from_url(url: str) -> str:
    """Extract domain for rate limiting."""
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"


def _url_to_filename(url: str) -> str:
    """Derive cache filename from URL."""
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    if url.lower().endswith(".pdf"):
        return f"{h}.pdf"
    return f"{h}.bin"


def fetch_attachment(
    url: str,
    cache_dir: Path,
    *,
    client: httpx.Client | None = None,
    skip_existing: bool = True,
) -> tuple[Path | None, str | None]:
    """
    Download attachment to cache. Returns (local_path, error_message).
    On success, error_message is None.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = _url_to_filename(url)
    local_path = cache_dir / filename

    if skip_existing and local_path.exists():
        return (local_path, None)

    domain = _domain_from_url(url)
    global _last_request_by_domain
    now = time.monotonic()
    if domain in _last_request_by_domain:
        elapsed = now - _last_request_by_domain[domain]
        if elapsed < _RATE_LIMIT_DELAY:
            time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_by_domain[domain] = time.monotonic()

    client = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)
        return (local_path, None)
    except httpx.HTTPStatusError as e:
        return (None, f"HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        return (None, str(e))
    except OSError as e:
        return (None, str(e))
