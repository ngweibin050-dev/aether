"""Validation of user-provided overall lengths for the current vehicle builder."""
from __future__ import annotations

import math

REFERENCE_LENGTH_MM = 4500.0
MIN_LENGTH_MM = 500.0
MAX_LENGTH_MM = 20000.0


def length_decision(value):
    """Record the source of scale; a user-supplied dimension is not independently verified."""
    if value is None:
        return {"value": REFERENCE_LENGTH_MM, "provenance": "assumed",
                "note": "Placeholder: overall length was not supplied; drawing dimensions are not automatically read."}
    if isinstance(value, bool):
        raise ValueError("overall length must be a finite number between 500 and 20000 mm")
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError("overall length must be a finite number between 500 and 20000 mm") from None
    if not math.isfinite(n) or not MIN_LENGTH_MM <= n <= MAX_LENGTH_MM:
        raise ValueError("overall length must be a finite number between 500 and 20000 mm")
    return {"value": n, "provenance": "user_confirmed",
            "note": "Overall length supplied by the user; not independently verified."}