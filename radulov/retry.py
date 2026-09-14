"""Retry helpers for transient Gemini generate_content failures."""

from __future__ import annotations

import sys
import time
from typing import Any

RETRYABLE_CODES = {500, 502, 503, 504}
RETRYABLE_STATUSES = {"UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED"}


def is_retryable_gemini_error(err: BaseException) -> bool:
    """Return True for transient Gemini HTTP failures such as 503 UNAVAILABLE."""
    code = getattr(err, "code", None)
    if isinstance(code, int) and code in RETRYABLE_CODES:
        return True
    status = str(getattr(err, "status", "") or "").upper()
    if status in RETRYABLE_STATUSES:
        return True
    text = str(err)
    return "503" in text and "UNAVAILABLE" in text


def generate_content_with_retry(
    client: Any,
    *,
    max_attempts: int = 3,
    backoff_sec: float = 1.0,
    sleeper: Any = None,
    **kwargs: Any,
) -> Any:
    """Call client.models.generate_content, retrying transient 5xx/UNAVAILABLE."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    sleep_fn = sleeper or time.sleep
    last_err: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.models.generate_content(**kwargs)
        except Exception as err:
            last_err = err
            if attempt >= max_attempts or not is_retryable_gemini_error(err):
                raise
            delay = backoff_sec * (2 ** (attempt - 1))
            code = getattr(err, "code", "?")
            status = getattr(err, "status", "UNAVAILABLE")
            sys.stderr.write(
                f"NOTICE: Gemini {code} {status}; retry {attempt}/{max_attempts - 1} "
                f"in {delay:.1f}s.\n"
            )
            sleep_fn(delay)
    assert last_err is not None
    raise last_err
