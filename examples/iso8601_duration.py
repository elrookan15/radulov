"""
Minimalist Pre-Compiled Regex ISO-8601 Duration Parser.
Converts ISO-8601 duration strings into total integer seconds.
"""

import re
from typing import Final

# Maximum allowed string length to prevent ReDoS / memory exhaustion
MAX_DURATION_LENGTH: Final[int] = 64

# Pre-compiled linear regex for ISO 8601 durations
# Format: P[n]Y[n]M[n]W[n]D[T[n]H[n]M[n]S]
ISO8601_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^P"
    r"(?:(?P<years>\d+)Y)?"
    r"(?:(?P<months>\d+)M)?"
    r"(?:(?P<weeks>\d+)W)?"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?"
    r"$",
)

# Conversion constants (standard approximations)
SECONDS_PER_MINUTE: Final[int] = 60
SECONDS_PER_HOUR: Final[int] = 3600
SECONDS_PER_DAY: Final[int] = 86400
SECONDS_PER_WEEK: Final[int] = 7 * SECONDS_PER_DAY
SECONDS_PER_MONTH: Final[int] = 30 * SECONDS_PER_DAY
SECONDS_PER_YEAR: Final[int] = 365 * SECONDS_PER_DAY


def parse_iso8601_duration(duration_str: str) -> int:
    """
    Parse an ISO-8601 duration string into total integer seconds.

    Args:
        duration_str: The ISO-8601 duration string (e.g., 'PT1H2M3S', 'P1DT4H').

    Returns:
        Total duration in integer seconds.

    Raises:
        TypeError: If duration_str is not a string.
        ValueError: If duration_str is empty, exceeds max length, or is malformed.
    """
    if not isinstance(duration_str, str):
        raise TypeError(f"Expected string input, got {type(duration_str).__name__}")

    if not duration_str:
        raise ValueError("Duration string cannot be empty.")

    if len(duration_str) > MAX_DURATION_LENGTH:
        raise ValueError(
            f"Duration string exceeds maximum allowed length of {MAX_DURATION_LENGTH} characters."
        )

    match = ISO8601_REGEX.match(duration_str)
    if not match:
        raise ValueError(f"Invalid ISO-8601 duration format: '{duration_str}'")

    groups = match.groupdict()
    if all(v is None for v in groups.values()):
        raise ValueError(f"Invalid ISO-8601 duration format (no components found): '{duration_str}'")

    years = int(groups["years"]) if groups["years"] else 0
    months = int(groups["months"]) if groups["months"] else 0
    weeks = int(groups["weeks"]) if groups["weeks"] else 0
    days = int(groups["days"]) if groups["days"] else 0
    hours = int(groups["hours"]) if groups["hours"] else 0
    minutes = int(groups["minutes"]) if groups["minutes"] else 0
    seconds = int(groups["seconds"]) if groups["seconds"] else 0

    total_seconds = (
        years * SECONDS_PER_YEAR
        + months * SECONDS_PER_MONTH
        + weeks * SECONDS_PER_WEEK
        + days * SECONDS_PER_DAY
        + hours * SECONDS_PER_HOUR
        + minutes * SECONDS_PER_MINUTE
        + seconds
    )

    return total_seconds


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            result = parse_iso8601_duration(sys.argv[1])
            print(f"Total seconds: {result}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
