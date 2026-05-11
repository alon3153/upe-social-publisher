"""Shared safety utilities: token redaction + transient-error retry."""

import re
import time
import functools
import requests
from typing import Callable, Any

_ACCESS_TOKEN_PATTERN = re.compile(
    r"(access_token|page_token|token|secret)([=\":\s]+)[A-Za-z0-9_\-\.]+",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)


def scrub(text: Any) -> str:
    """Remove tokens from any string before logging or raising."""
    s = str(text)
    s = _ACCESS_TOKEN_PATTERN.sub(r"\1\2[REDACTED]", s)
    s = _BEARER_PATTERN.sub("Bearer [REDACTED]", s)
    return s


_TRANSIENT_HTTP_CODES = {429, 500, 502, 503, 504}
# Graph API transient error subcodes: rate-limit (4, 17, 32), temporary (1, 2)
_TRANSIENT_GRAPH_CODES = {1, 2, 4, 17, 32, 613}


def is_transient(response: requests.Response) -> bool:
    if response.status_code in _TRANSIENT_HTTP_CODES:
        return True
    try:
        err = response.json().get("error", {})
        if err.get("code") in _TRANSIENT_GRAPH_CODES:
            return True
    except Exception:
        pass
    return False


def with_retry(max_attempts: int = 3, base_delay: float = 2.0):
    """Decorate a callable that returns requests.Response. Retries on transient errors with exponential backoff."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> requests.Response:
            last_response = None
            for attempt in range(max_attempts):
                response = fn(*args, **kwargs)
                last_response = response
                if response.status_code == 200 or not is_transient(response):
                    return response
                if attempt < max_attempts - 1:
                    time.sleep(base_delay * (2 ** attempt))
            return last_response
        return wrapper
    return decorator
