"""Retry helpers for transient Gemini generate_content failures."""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from typing import Any

from radulov import FALLBACK_MODEL

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


def _model_chain(
    primary: Any,
    fallback_models: Sequence[str] | None,
) -> list[str]:
    """Build an ordered unique model list: primary first, then fallbacks."""
    models: list[str] = []
    if primary:
        models.append(str(primary))
    extras = FALLBACK_MODEL if fallback_models is None else fallback_models
    if isinstance(extras, str):
        extras = (extras,)
    for model in extras:
        if model and model not in models:
            models.append(str(model))
    if not models:
        raise ValueError("generate_content_with_retry requires a model")
    return models


def generate_content_with_retry(
    client: Any,
    *,
    max_attempts: int = 3,
    backoff_sec: float = 1.0,
    sleeper: Any = None,
    fallback_models: Sequence[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Call client.models.generate_content with retries and optional model fallback.

    Retries transient 5xx/UNAVAILABLE on the current model. When those attempts
    are exhausted, tries the next model in the fallback chain (default:
    ``FALLBACK_MODEL``). Quota ``429`` errors are not retried and do not
    trigger fallback.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    sleep_fn = sleeper or time.sleep
    models = _model_chain(kwargs.get("model"), fallback_models)
    last_err: BaseException | None = None

    for model_index, model in enumerate(models):
        call_kwargs = dict(kwargs)
        call_kwargs["model"] = model
        if model_index > 0:
            sys.stderr.write(
                f"NOTICE: Falling back to Gemini model {model} after "
                f"{models[model_index - 1]} exhausted retries.\n"
            )

        for attempt in range(1, max_attempts + 1):
            try:
                return client.models.generate_content(**call_kwargs)
            except Exception as err:
                last_err = err
                retryable = is_retryable_gemini_error(err)
                if not retryable:
                    raise
                if attempt < max_attempts:
                    delay = backoff_sec * (2 ** (attempt - 1))
                    code = getattr(err, "code", "?")
                    status = getattr(err, "status", "UNAVAILABLE")
                    sys.stderr.write(
                        f"NOTICE: Gemini {code} {status}; "
                        f"retry {attempt}/{max_attempts - 1} "
                        f"on {model} in {delay:.1f}s.\n"
                    )
                    sleep_fn(delay)
                    continue
                # Attempts exhausted on this model; try next fallback if any.
                if model_index < len(models) - 1:
                    break
                raise

    assert last_err is not None
    raise last_err
