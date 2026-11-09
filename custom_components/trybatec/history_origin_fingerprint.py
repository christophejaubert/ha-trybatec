"""Pure source-bound fingerprint for a user-declared estimated meter origin."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import math
from typing import Any


def origin_fingerprint(
    *, lot: str, fluid: str, serial: str, source_fingerprint: str,
    first_at: datetime, first_index: float,
    estimated_start_date: date, estimated_start_index: float,
) -> str:
    if (not all(isinstance(x, str) and x for x in (lot, fluid, serial))
            or not isinstance(source_fingerprint, str)
            or len(source_fingerprint) != 64
            or not isinstance(first_at, datetime)
            or first_at.tzinfo is None
            or first_at.utcoffset() is None
            or not isinstance(estimated_start_date, date)
            or isinstance(estimated_start_date, datetime)):
        raise ValueError("Estimated origin has incomplete source evidence")
    for number in (first_index, estimated_start_index):
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ValueError("Estimated index must be numeric")
        if not math.isfinite(number) or number < 0:
            raise ValueError("Estimated index must be finite and nonnegative")
    fields: list[Any] = [
        lot, fluid, serial, source_fingerprint, first_at.isoformat(),
        float(first_index), estimated_start_date.isoformat(),
        float(estimated_start_index),
    ]
    return sha256(json.dumps(fields, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
