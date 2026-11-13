"""Explicit backend write gate for #88, shared by native admin and HA routes.

A new reviewed source change and independently qualified #36/#37 contracts
are required before considering activation. This is intentionally NOT a
configuration option, browser field, HA helper, or runtime environment toggle.
"""
from __future__ import annotations

NATIVE_ENERGY_BULK_WRITES_ENABLED_88 = False
